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


def safe_extract_zip(zip_path: Path, dest: Path, max_files: int = 2000) -> dict[str, Any]:
    ensure_dir(dest)
    extracted = 0
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > max_files:
            return {"status": "skipped_too_many_files", "file_count": len(members)}
        for member in members:
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest.resolve())):
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


def download_limited(uri: str, dest: Path, max_bytes: int) -> dict[str, Any]:
    ensure_dir(dest.parent)
    request = urllib.request.Request(uri, headers={"User-Agent": "Papert2Skills/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(max_bytes + 1)
    except Exception as exc:
        return {"status": "fetch_error", "uri": uri, "error": str(exc)}
    if len(data) > max_bytes:
        return {"status": "skipped_too_large", "uri": uri, "max_bytes": max_bytes}
    dest.write_bytes(data)
    return {
        "status": "downloaded",
        "uri": uri,
        "local_path": str(dest),
        "bytes": len(data),
        "sha256": sha256_file(dest),
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
            result = download_limited(candidate, archive_path, max_bytes)
            if result["status"] == "downloaded":
                extract_dir = dest_root / "repositories" / slugify(evidence_id)
                extract_result = safe_extract_zip(archive_path, extract_dir)
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
    record.update(download_limited(uri, dest, max_bytes))
    return record


def fetch_sources(request: dict[str, Any], sources: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    fetch_enabled = bool(request.get("fetch_sources", False))
    max_bytes = int(request.get("max_fetch_bytes") or DEFAULT_MAX_FETCH_BYTES)
    records = [fetch_one_source(source, out, fetch_enabled, max_bytes) for source in sources]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "fetch_enabled": fetch_enabled,
        "max_fetch_bytes": max_bytes,
        "sources": records,
        "notes": [
            "Fetching never executes source code.",
            "Remote downloads are skipped unless fetch_sources is true.",
            "Repository archives are extracted with path traversal checks.",
        ],
    }
