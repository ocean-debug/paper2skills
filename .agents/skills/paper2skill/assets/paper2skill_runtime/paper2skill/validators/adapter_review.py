from __future__ import annotations

import os
import re
import shlex
from typing import Any


ALLOWED_COMMAND_PLACEHOLDERS = {"manifest", "out", "root", "example_id"}
COMMAND_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
PYTHON_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def missing_explicit_adapter_mapping(spec: dict[str, Any], review: dict[str, Any]) -> list[str]:
    adapter_type = spec.get("adapter_type")
    if adapter_type == "python_api":
        required = ["adapter_type", "entrypoint", "module", "function"]
    elif adapter_type in {"cli", "workflow_engine"}:
        required = ["adapter_type", "entrypoint", "command"]
    elif adapter_type in {"notebook", "r_script"}:
        required = ["adapter_type", "entrypoint", "command"]
    else:
        required = ["adapter_type"]
    return [key for key in required if missing_adapter_review_mapping_value(key, review.get(key))]


def missing_adapter_review_mapping_value(key: str, value: Any) -> bool:
    if key == "command":
        tokens, error = command_tokens(value)
        return error is not None or not tokens
    return not isinstance(value, str) or value == ""


def adapter_review_mismatches(spec: dict[str, Any], review: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    if review.get("adapter_type") != spec.get("adapter_type"):
        mismatches.append("adapter_type")
    for key in ["entrypoint", "module", "function"]:
        expected = spec.get(key)
        approved = review.get(key)
        if expected and approved and expected != approved:
            mismatches.append(key)
    module = review.get("module")
    if module and not safe_python_name(str(module)):
        mismatches.append("module")
    function = review.get("function")
    if function and not safe_python_name(str(function)):
        mismatches.append("function")
    mismatches.extend(f"command:{error}" for error in command_refinement_errors(spec.get("command"), review.get("command")))
    return mismatches


def adapter_review_matches(spec: dict[str, Any], review: dict[str, Any]) -> bool:
    return not adapter_review_mismatches(spec, review)


def command_refinement_errors(expected: Any, approved: Any) -> list[str]:
    errors: list[str] = []
    errors.extend(command_placeholder_errors(approved))
    expected_tokens, expected_error = command_tokens(expected)
    approved_tokens, approved_error = command_tokens(approved)
    if expected_error:
        errors.append(f"expected_{expected_error}")
    if approved_error:
        errors.append(f"approved_{approved_error}")
    if expected_tokens and approved_tokens and not prefix_compatible(expected_tokens, approved_tokens):
        errors.append("not_prefix_compatible")
    return errors


def command_tokens(value: Any) -> tuple[list[str], str | None]:
    if value in (None, ""):
        return [], None
    if isinstance(value, list):
        tokens = [str(item) for item in value if str(item)]
        return tokens, None if tokens else "empty"
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            return [], "contains_newline"
        try:
            tokens = shlex.split(value, posix=os.name != "nt")
        except ValueError:
            return [], "parse_error"
        return tokens, None if tokens else "empty"
    return [], "unsupported_type"


def command_placeholder_errors(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    errors: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        for name in COMMAND_PLACEHOLDER_RE.findall(item):
            if name not in ALLOWED_COMMAND_PLACEHOLDERS:
                errors.append(f"unsupported_placeholder:{name}")
    return errors


def prefix_compatible(expected_tokens: list[str], approved_tokens: list[str]) -> bool:
    if len(approved_tokens) < len(expected_tokens):
        return False
    return approved_tokens[: len(expected_tokens)] == expected_tokens


def safe_python_name(value: str) -> bool:
    return bool(PYTHON_NAME_RE.match(value))
