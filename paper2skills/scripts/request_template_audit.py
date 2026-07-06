"""Audit build request template consistency against request contracts."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from common import load_data, now_utc, read_text
from constants import SCHEMA_VERSION


REQUIRED_IDENTITY_FIELDS = {"package_name", "method_name", "repo_url"}
REQUIRED_TEMPLATE_VALUES = {
    "schema_version": SCHEMA_VERSION,
    "target_agent": "codex",
    "language_backend": "python",
    "execution_grounded": False,
    "fetch_sources": False,
    "cleanup_process_files": True,
}
FORBIDDEN_TEMPLATE_PATTERNS = [
    "".join(["192", ".168", "."]),
    "".join(["/ho", "me/"]),
    "".join(["conda", " activate"]),
    "".join(["gpu", "0"]),
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    field: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if field:
        item["field"] = field
    findings.append(item)


def literal_names(node: ast.AST) -> set[str]:
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return set()
    if isinstance(value, (set, list, tuple)):
        return {str(item) for item in value if isinstance(item, str)}
    return set()


def request_model_defaults(path: Path) -> set[str]:
    tree = ast.parse(read_text(path))
    fields: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "setdefault":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            fields.add(node.args[0].value)
    return fields


def request_audit_constant(path: Path, name: str) -> set[str]:
    tree = ast.parse(read_text(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return literal_names(node.value)
    return set()


def builder_runtime_required_fields(path: Path) -> set[str]:
    tree = ast.parse(read_text(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REQUIRED_TEMPLATE_FIELDS":
                    return literal_names(node.value)
    return set()


def build_request_template_audit(skill_dir: Path) -> dict[str, Any]:
    """Return a static audit for template, normalizer, and request-audit drift."""
    findings: list[dict[str, Any]] = []
    scripts_dir = skill_dir / "scripts"
    template_path = skill_dir / "templates" / "build_request.yaml"
    template_text = read_text(template_path) if template_path.exists() else ""
    template = load_data(template_path) if template_path.exists() else {}
    if not isinstance(template, dict):
        template = {}
        add_finding(findings, "error", "template_not_mapping", "Build request template must be a mapping.", "templates/build_request.yaml")

    template_fields = set(template)
    default_fields = request_model_defaults(scripts_dir / "request_model.py")
    list_fields = request_audit_constant(scripts_dir / "request_audit.py", "LIST_FIELDS")
    positive_int_fields = request_audit_constant(scripts_dir / "request_audit.py", "POSITIVE_INT_FIELDS")
    remote_required_fields = request_audit_constant(scripts_dir / "request_audit.py", "REMOTE_REQUIRED_FIELDS")
    runtime_required_fields = builder_runtime_required_fields(scripts_dir / "builder_runtime_audit.py")

    expected_top_level = REQUIRED_IDENTITY_FIELDS | default_fields | list_fields | positive_int_fields
    missing_template_fields = sorted(expected_top_level - template_fields)
    for field in missing_template_fields:
        add_finding(findings, "error", "template_missing_request_field", "Build request template is missing a normalized or audited request field.", field)

    missing_runtime_fields = sorted((default_fields | REQUIRED_IDENTITY_FIELDS) - runtime_required_fields)
    for field in missing_runtime_fields:
        add_finding(findings, "error", "runtime_required_fields_incomplete", "Builder runtime required template fields do not cover normalized request fields.", field)

    execution_environment = template.get("execution_environment") if isinstance(template.get("execution_environment"), dict) else {}
    missing_environment_fields = sorted(remote_required_fields - set(execution_environment))
    for field in missing_environment_fields:
        add_finding(findings, "error", "template_missing_execution_environment_field", "Execution environment template is missing a remote execution field.", f"execution_environment.{field}")

    for field in sorted(list_fields):
        if field in template and not isinstance(template[field], list):
            add_finding(findings, "error", "template_list_field_not_list", "Template field must be a list.", field)
    for field in sorted(positive_int_fields):
        value = template.get(field)
        if not isinstance(value, int) or value <= 0:
            add_finding(findings, "error", "template_positive_int_invalid", "Template numeric bound must be a positive integer.", field)
    for field, expected in REQUIRED_TEMPLATE_VALUES.items():
        if template.get(field) != expected:
            add_finding(findings, "error", "template_default_value_invalid", "Template default value does not match builder policy.", field)
    for pattern in FORBIDDEN_TEMPLATE_PATTERNS:
        if pattern.lower() in template_text.lower():
            add_finding(findings, "error", "template_contains_private_or_specific_value", "Build request template contains a private or overly specific environment value.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "skill_dir": ".",
        "template_path": "templates/build_request.yaml",
        "template_field_count": len(template_fields),
        "normalized_default_fields": sorted(default_fields),
        "request_audit_list_fields": sorted(list_fields),
        "request_audit_positive_int_fields": sorted(positive_int_fields),
        "remote_required_fields": sorted(remote_required_fields),
        "runtime_required_template_fields": sorted(runtime_required_fields),
        "missing_template_fields": missing_template_fields,
        "missing_runtime_required_fields": missing_runtime_fields,
        "missing_environment_fields": missing_environment_fields,
        "findings": findings,
        "policy": [
            "The template must expose every normalized or audited build request field.",
            "The template must stay generic and must not encode machine-specific execution details.",
            "Builder runtime required fields must cover normalized request defaults so template drift is visible.",
            "Template schema_version must match the builder artifact schema version.",
        ],
    }
