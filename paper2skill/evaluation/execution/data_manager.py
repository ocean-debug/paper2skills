from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from paper2skill.common import ensure_dir


def prepare_download(
    download: dict[str, Any] | None,
    *,
    allow_download: bool = False,
    cache_dir: str | Path = "benchmarks/data_cache",
    max_download_mb: float = 0.0,
) -> dict[str, Any]:
    if not download:
        return {"status": "not_required", "path": None, "warnings": []}
    url = str(download.get("url") or "")
    cache_key = str(download.get("cache_key") or safe_cache_key(url))
    expected_size = float(download.get("expected_size_max_mb") or max_download_mb or 0.0)
    checksum = str(download.get("checksum") or "")
    target = ensure_dir(Path(cache_dir)) / cache_key
    if target.exists():
        return check_cached_file(target, expected_size, checksum)
    if not allow_download:
        return {"status": "skipped", "path": str(target), "warnings": ["download skipped because --allow-download was not set"]}
    if not url:
        return {"status": "failed", "path": str(target), "warnings": ["download url is missing"]}
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - explicit benchmark opt-in download.
        with target.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return check_cached_file(target, expected_size, checksum)


def check_cached_file(path: Path, expected_size_max_mb: float = 0.0, checksum: str = "") -> dict[str, Any]:
    warnings: list[str] = []
    status = "cached"
    if expected_size_max_mb:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > expected_size_max_mb:
            status = "failed"
            warnings.append(f"downloaded file exceeds expected size: {size_mb:.2f} MB > {expected_size_max_mb:.2f} MB")
    if checksum:
        actual = sha256(path)
        expected = checksum.removeprefix("sha256:")
        if actual != expected:
            status = "failed"
            warnings.append("download checksum mismatch")
    return {"status": status, "path": str(path), "warnings": warnings}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_cache_key(url: str) -> str:
    if not url:
        return "missing-url"
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

