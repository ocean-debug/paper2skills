from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote


REDACTED_LOCAL_PATH = "<redacted-local-path>"
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
FILE_URL_RE = re.compile(r"^file://(?P<path>.+)", re.IGNORECASE)
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
UNC_ABSOLUTE_RE = re.compile(r"^\\\\")
POSIX_ABSOLUTE_RE = re.compile(r"^/(?!/)")
QUOTED_ABSOLUTE_PATH_RE = re.compile(r"(?P<quote>['\"])(?P<path>(?:file://(?:[A-Za-z]:[\\/]|\\\\|/)|[A-Za-z]:[\\/]|\\\\|/(?!/))[^'\"]+)(?P=quote)", re.IGNORECASE)
FILE_URL_TOKEN_RE = re.compile(r"file://(?:[A-Za-z]:[\\/]|\\\\|/)[^\s'\"<>`,)]+", re.IGNORECASE)
WINDOWS_ABSOLUTE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/][^\s'\"<>`,)]+|\\\\[^\s'\"<>`,)]+)")
POSIX_ABSOLUTE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_:/])/(?!/)[^\s'\"<>`,)]+")


def public_local_path(path: Path | None, base_dir: Path) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    base = base_dir.resolve()
    try:
        return str(resolved.relative_to(base)).replace("\\", "/")
    except ValueError:
        return REDACTED_LOCAL_PATH


def public_local_paths(paths: Iterable[Path], base_dir: Path) -> list[str]:
    return [value for value in (public_local_path(path, base_dir) for path in paths) if value is not None]


def public_path_string(value: str, base_dir: Path) -> str:
    file_url_path = _file_url_path(value)
    if file_url_path is not None:
        public = public_path_string(file_url_path, base_dir)
        if public != file_url_path:
            return public
        normalized = file_url_path.rstrip("\\/")
        name = re.split(r"[\\/]", normalized)[-1]
        return name or REDACTED_LOCAL_PATH
    if URL_SCHEME_RE.match(value):
        return value
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(base_dir.resolve())).replace("\\", "/")
        except (OSError, ValueError):
            return path.name or REDACTED_LOCAL_PATH
    if WINDOWS_ABSOLUTE_RE.match(value) or UNC_ABSOLUTE_RE.match(value):
        normalized = value.rstrip("\\/")
        name = re.split(r"[\\/]", normalized)[-1]
        return name or REDACTED_LOCAL_PATH
    if POSIX_ABSOLUTE_RE.match(value):
        normalized = value.rstrip("/")
        name = normalized.rsplit("/", 1)[-1]
        return name or REDACTED_LOCAL_PATH
    return value


def _file_url_path(value: str) -> str | None:
    match = FILE_URL_RE.match(value)
    if not match:
        return None
    path = unquote(match.group("path"))
    if path.startswith("/") and WINDOWS_ABSOLUTE_RE.match(path[1:]):
        path = path[1:]
    return path


def public_string(value: str, base_dir: Path) -> str:
    if URL_SCHEME_RE.match(value) and _file_url_path(value) is None:
        return value
    stripped = value.strip()
    if stripped == value and public_path_string(value, base_dir) != value:
        return public_path_string(value, base_dir)

    def replace_quoted(match: re.Match[str]) -> str:
        return "%s%s%s" % (match.group("quote"), public_path_string(match.group("path"), base_dir), match.group("quote"))

    def replace_token(match: re.Match[str]) -> str:
        return public_path_string(match.group(0), base_dir)

    value = QUOTED_ABSOLUTE_PATH_RE.sub(replace_quoted, value)
    value = FILE_URL_TOKEN_RE.sub(replace_token, value)
    value = WINDOWS_ABSOLUTE_TOKEN_RE.sub(replace_token, value)
    return POSIX_ABSOLUTE_TOKEN_RE.sub(replace_token, value)


def public_data(value: Any, base_dir: Path) -> Any:
    if isinstance(value, dict):
        return {(public_string(key, base_dir) if isinstance(key, str) else key): public_data(item, base_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [public_data(item, base_dir) for item in value]
    if isinstance(value, tuple):
        return [public_data(item, base_dir) for item in value]
    if isinstance(value, str):
        return public_string(value, base_dir)
    return value
