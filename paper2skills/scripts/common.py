"""Shared filesystem, YAML, naming, and event helpers for Paper2Skills."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REQUEST_SCHEMA = "paper2skills.request.v1"
SKILLIR_SCHEMA = "paper2skills.skillir.v1"
PATCH_SCHEMA = "paper2skills.patch.v1"
STATE_SCHEMA = "paper2skills.state.v1"
VALIDATION_SCHEMA = "paper2skills.validation.v1"


class Paper2SkillsError(RuntimeError):
    """Raised for actionable user-facing builder errors."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load one YAML mapping and reject missing or non-mapping documents."""

    source = Path(path)
    if not source.is_file():
        raise Paper2SkillsError(f"YAML file does not exist: {source}")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Paper2SkillsError(f"Expected a YAML mapping: {source}")
    return data


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dump_yaml(path: str | Path, data: dict[str, Any]) -> None:
    """Write stable, readable YAML atomically."""

    rendered = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    _atomic_write(Path(path), rendered)


def write_text(path: str | Path, content: str) -> None:
    """Write UTF-8 text atomically with a trailing newline."""

    normalized = content.rstrip() + "\n"
    _atomic_write(Path(path), normalized)


def slugify(value: str) -> str:
    """Normalize a name to a Codex-compatible lowercase hyphenated slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise Paper2SkillsError(f"Cannot derive a skill name from {value!r}")
    if len(slug) > 63:
        slug = slug[:63].rstrip("-")
    return slug


def stable_id(prefix: str, *parts: object) -> str:
    """Return a stable evidence/event suffix for the supplied provenance."""

    joined = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def as_list(value: Any) -> list[Any]:
    """Normalize absent or scalar values to a list."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def unique_strings(values: Iterable[Any]) -> list[str]:
    """Return non-empty string values in first-seen order."""

    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolve_run_dir(path: str | Path) -> Path:
    """Resolve a run directory without requiring it to exist."""

    return Path(path).expanduser().resolve()


def ensure_within(parent: Path, child: Path, label: str) -> Path:
    """Reject a path that escapes its declared parent directory."""

    parent_resolved = parent.resolve()
    child_resolved = child.resolve()
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise Paper2SkillsError(
            f"{label} must stay inside {parent_resolved}: {child_resolved}"
        ) from exc
    return child_resolved


def timestamp() -> str:
    """Return an RFC 3339 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def append_event(run_dir: Path, event: str, **details: Any) -> None:
    """Append a compact JSON event to the run-local timeline."""

    record = {"time": timestamp(), "event": event, **details}
    path = run_dir / "timeline.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def require_schema(document: dict[str, Any], expected: str, label: str) -> None:
    """Require an exact document schema version."""

    actual = document.get("schema_version")
    if actual != expected:
        raise Paper2SkillsError(
            f"{label} schema_version must be {expected!r}; got {actual!r}"
        )
