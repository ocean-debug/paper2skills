"""Common IO, serialization, and small utility helpers."""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any


class BuildError(RuntimeError):
    """Raised for user-fixable build request errors."""


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str | None, default: str = "method") -> str:
    text = (value or default).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or default


def canonical_task_type(value: str | None, default: str = "general_algorithm_use") -> str:
    """Return the stable snake_case key used for task_type records."""
    return slugify(value, default).replace("-", "_")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_child_skill_path(child_skill_dir: Path) -> str:
    """Return a run-relative child-skill path for public run artifacts."""
    if child_skill_dir.parent.name == "child_skill":
        return f"child_skill/{child_skill_dir.name}"
    return child_skill_dir.name


def public_existing_skill_path(path_value: Any) -> str | None:
    """Return a non-local existing-skill reference for public run artifacts."""
    text = str(path_value or "").strip()
    if not text:
        return None
    name = text.replace("\\", "/").rstrip("/").split("/")[-1]
    return f"existing_skill/{slugify(name, 'existing-skill')}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "None", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small build_request.yaml shape without requiring PyYAML."""
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and ":" in line and not line.startswith("- "):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                data[key] = {}
                current_key = key
            else:
                data[key] = parse_scalar(value)
                current_key = None
            continue
        if indent > 0 and current_key and ":" in line and not line.startswith("- "):
            key, value = line.split(":", 1)
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            data[current_key][key.strip()] = parse_scalar(value.strip())
            continue
        if line.startswith("- ") and current_key:
            item = parse_scalar(line[2:].strip())
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(item)
    return data


def load_data(path: Path) -> Any:
    text = read_text(path)
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        return parse_simple_yaml(text)


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if re.search(r"[:#\[\]\{\},&*!\|>'\"%@`]", text) or text.strip() != text:
        return json.dumps(text)
    if text.lower() in {"true", "false", "null", "none"}:
        return json.dumps(text)
    return text


def to_yaml(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{yaml_scalar(value)}"


def write_data(path: Path, data: Any) -> Path:
    if path.suffix.lower() == ".json":
        return write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return write_text(path, to_yaml(data) + "\n")


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def lower_join(values: list[Any]) -> str:
    return " ".join(str(item).lower() for item in values if item is not None)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    escaped_rows = []
    for row in rows:
        escaped_rows.append([str(cell).replace("\n", " ").replace("|", "\\|") for cell in row])
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in escaped_rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
