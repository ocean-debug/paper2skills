from __future__ import annotations

from typing import Any


def validate_required(data: dict[str, Any], required: list[str], label: str) -> list[str]:
    errors = []
    for key in required:
        if key not in data:
            errors.append(f"{label}: missing required key '{key}'")
    return errors


def validate_simple_schema(data: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    errors = validate_required(data, schema.get("required", []), label)
    properties = schema.get("properties", {}) or {}
    for key, rules in properties.items():
        if key not in data:
            continue
        if "required" in rules and isinstance(data[key], dict):
            errors.extend(validate_required(data[key], rules["required"], f"{label}.{key}"))
        if "enum" in rules and data[key] not in rules["enum"]:
            errors.append(f"{label}.{key}: expected one of {rules['enum']}, got {data[key]!r}")
    return errors
