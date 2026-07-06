"""Fetch or register official source material without executing it."""

from __future__ import annotations

import hashlib
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from common import as_list, ensure_dir, now_utc, slugify
from constants import DEFAULT_MAX_FETCH_BYTES, SCHEMA_VERSION


def is_http(uri: str) -> bool:
    return uri.startswith("http://") or uri.startswith("https://")


def github_archive_candidates(uri: str) -> list[str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.netloc.lower() != "github.com":
        return []
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return []
    owner, repo = parts[0], parts[1].removesuffix(".git")
    base = f"https://github.com/{owner}/{repo}/archive/refs/heads"
    return [f"{base}/main.zip", f"{base}/master.zip"]


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def safe_extract_zip(
    zip_path: Path,
    dest: Path,
    max_files: int = 2000,
    max_total_bytes: int = DEFAULT_MAX_FETCH_BYTES,
) -> dict[str, Any]:
    ensure_dir(dest)
    extracted = 0
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > max_files:
            return {"status": "skipped_too_many_files", "file_count": len(members)}
        total_size = sum(member.file_size for member in members)
        if total_size > max_total_bytes:
            return {
                "status": "skipped_too_many_uncompressed_bytes",
                "uncompressed_bytes": total_size,
                "max_uncompressed_bytes": max_total_bytes,
            }
        for member in members:
            target = (dest / member.filename).resolve()
            if not is_within(target, dest):
                return {"status": "blocked_unsafe_zip_member", "member": member.filename}
            archive.extract(member, dest)
            extracted += 1
    return {"status": "extracted", "file_count": extracted}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_path_for_uri(cache_dir: Path, uri: str, suffix: str) -> Path:
    digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:24]
    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return cache_dir / f"{digest}{safe_suffix}"


def copy_cached_source(uri: str, cache_path: Path, dest: Path, max_bytes: int) -> dict[str, Any] | None:
    if not cache_path.exists() or not cache_path.is_file():
        return None
    size = cache_path.stat().st_size
    if size > max_bytes:
        return None
    ensure_dir(dest.parent)
    shutil.copy2(cache_path, dest)
    return {
        "status": "reused_cache",
        "uri": uri,
        "local_path": str(dest),
        "bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        "cache_path": str(cache_path),
    }


def download_limited(uri: str, dest: Path, max_bytes: int, cache_path: Path | None = None) -> dict[str, Any]:
    ensure_dir(dest.parent)
    if cache_path:
        cached = copy_cached_source(uri, cache_path, dest, max_bytes)
        if cached:
            return cached
    request = urllib.request.Request(uri, headers={"User-Agent": "paper2skills/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(max_bytes + 1)
    except Exception as exc:
        return {"status": "fetch_error", "uri": uri, "error": str(exc)}
    if len(data) > max_bytes:
        return {"status": "skipped_too_large", "uri": uri, "max_bytes": max_bytes}
    dest.write_bytes(data)
    if cache_path:
        ensure_dir(cache_path.parent)
        shutil.copy2(dest, cache_path)
    return {
        "status": "downloaded",
        "uri": uri,
        "local_path": str(dest),
        "bytes": len(data),
        "sha256": sha256_file(dest),
        "cache_path": str(cache_path) if cache_path else None,
    }


def register_local_path(uri: str, dest_root: Path, evidence_id: str) -> dict[str, Any]:
    path = Path(uri).expanduser()
    if not path.exists():
        return {"status": "missing_local_path", "uri": uri}
    local_path = dest_root / slugify(evidence_id) / path.name
    ensure_dir(local_path.parent)
    if path.is_dir():
        if local_path.exists():
            shutil.rmtree(local_path)
        shutil.copytree(path, local_path)
        return {"status": "registered_local_directory", "uri": uri, "local_path": str(local_path)}
    shutil.copy2(path, local_path)
    return {
        "status": "registered_local_file",
        "uri": uri,
        "local_path": str(local_path),
        "bytes": local_path.stat().st_size,
        "sha256": sha256_file(local_path),
    }


def fetch_one_source(
    source: dict[str, Any],
    out: Path,
    fetch_enabled: bool,
    max_bytes: int,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    evidence_id = str(source["evidence_id"])
    uri = str(source.get("uri") or "")
    dest_root = out / "sources"
    record = {
        "evidence_id": evidence_id,
        "type": source.get("type"),
        "uri": uri,
        "official": source.get("official", False),
    }
    if not is_http(uri):
        record.update(register_local_path(uri, dest_root, evidence_id))
        return record
    if not fetch_enabled:
        record.update({"status": "skipped_fetch_disabled"})
        return record
    if source.get("type") == "repository":
        for candidate in github_archive_candidates(uri):
            archive_path = dest_root / "repositories" / f"{slugify(evidence_id)}.zip"
            candidate_cache = cache_path_for_uri(cache_dir, candidate, ".zip") if cache_dir else None
            result = download_limited(candidate, archive_path, max_bytes, candidate_cache)
            if result["status"] in {"downloaded", "reused_cache"}:
                extract_dir = dest_root / "repositories" / slugify(evidence_id)
                extract_result = safe_extract_zip(archive_path, extract_dir, max_total_bytes=max_bytes)
                record.update(result)
                record.update({"resolved_uri": candidate, "extract_path": str(extract_dir), "extract": extract_result})
                return record
            if result["status"] == "fetch_error":
                record.setdefault("fetch_errors", []).append(result)
        record.update({"status": "unsupported_repository_fetch", "reason": "Only GitHub archive URLs are supported by the safe fetcher."})
        return record
    parsed = urllib.parse.urlparse(uri)
    suffix = Path(parsed.path).suffix or ".txt"
    dest = dest_root / "documents" / f"{slugify(evidence_id)}{suffix}"
    document_cache = cache_path_for_uri(cache_dir, uri, suffix) if cache_dir else None
    record.update(download_limited(uri, dest, max_bytes, document_cache))
    return record


def fetch_sources(request: dict[str, Any], sources: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    fetch_enabled = bool(request.get("fetch_sources", False))
    max_bytes = int(request.get("max_fetch_bytes") or DEFAULT_MAX_FETCH_BYTES)
    cache_enabled = bool(request.get("reuse_fetched_sources", True))
    requested_cache_dir = Path(str(request.get("source_cache_dir") or out / ".source_cache")).expanduser() if cache_enabled else None
    cache_dir = requested_cache_dir
    cache_boundary = "disabled"
    if cache_dir:
        default_cache_dir = out / ".source_cache"
        if is_within(cache_dir, out):
            cache_boundary = "run_bounded"
        else:
            cache_dir = default_cache_dir
            cache_boundary = "rewritten_to_run_bounded_default"
    records = [fetch_one_source(source, out, fetch_enabled, max_bytes, cache_dir) for source in sources]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "fetch_enabled": fetch_enabled,
        "cache_enabled": cache_enabled,
        "source_cache_dir": str(cache_dir) if cache_dir else None,
        "requested_source_cache_dir": str(requested_cache_dir) if requested_cache_dir else None,
        "source_cache_boundary": cache_boundary,
        "max_fetch_bytes": max_bytes,
        "sources": records,
        "notes": [
            "Fetching never executes source code.",
            "Remote downloads are skipped unless fetch_sources is true.",
            "Successful fetched sources are cached when reuse_fetched_sources is true and reused before a fresh network request.",
            "Repository archives are extracted with path traversal checks.",
        ],
    }
