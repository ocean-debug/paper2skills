"""Stable build-request fingerprinting without storing request secrets."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


CONTROL_FIELDS = [
    "target_agent",
    "language_backend",
    "execution_grounded",
    "fetch_sources",
    "max_fetch_bytes",
    "max_index_files",
    "max_index_bytes",
    "review_iterations",
    "review_min_score_ratio",
    "agent_review_proposals",
]
IDENTIFIER_FIELDS = [
    "package_name",
    "method_name",
    "repo_url",
    "paper_dois",
    "api_names",
    "requested_task_types",
]
SENSITIVE_FIELD_NAMES = {
    "host",
    "token",
    "api_key",
    "password",
    "secret",
    "working_directory",
    "private_key",
}
REDACTED_VALUE = "<redacted>"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def field_digest(request: dict[str, Any], fields: list[str]) -> str:
    return sha256_text(canonical_json({field: request.get(field) for field in fields}))


def sensitive_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            next_prefix = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in SENSITIVE_FIELD_NAMES:
                paths.append(next_prefix)
            paths.extend(sensitive_paths(item, next_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(sensitive_paths(item, f"{prefix}[{index}]"))
    return paths


def redacted_copy(value: Any) -> Any:
    """Return a request-shaped copy with sensitive values replaced by a marker."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_FIELD_NAMES:
                redacted[key] = REDACTED_VALUE
            else:
                redacted[key] = redacted_copy(item)
        return redacted
    if isinstance(value, list):
        return [redacted_copy(item) for item in value]
    return value


def build_request_fingerprint(request: dict[str, Any], request_audit: dict[str, Any]) -> dict[str, Any]:
    """Return non-secret request identity metadata for reproducible build runs."""
    redacted_request = redacted_copy(request)
    canonical = canonical_json(redacted_request)
    request_keys = sorted(str(key) for key in request)
    sensitive = sorted(set(sensitive_paths(request)))
    findings: list[dict[str, Any]] = []

    if request_audit.get("status") == "fail":
        findings.append(
            {
                "severity": "error",
                "code": "request_audit_failed",
                "message": "Request fingerprint requires a passing request audit.",
            }
        )
    if not request_keys:
        findings.append(
            {
                "severity": "error",
                "code": "empty_request",
                "message": "Normalized request has no fields.",
            }
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "request_hash": sha256_text(canonical),
        "identifier_hash": field_digest(request, IDENTIFIER_FIELDS),
        "control_hash": field_digest(request, CONTROL_FIELDS),
        "request_key_count": len(request_keys),
        "request_keys": request_keys,
        "identifier_fields": IDENTIFIER_FIELDS,
        "control_fields": CONTROL_FIELDS,
        "sensitive_field_paths": sensitive,
        "redacted_sensitive_value_count": len(sensitive),
        "stores_raw_request": False,
        "request_audit_status": request_audit.get("status"),
        "findings": findings,
        "policy": [
            "Request fingerprint is a run artifact for reproducibility and does not store the raw build request.",
            "request_hash is computed from a request-shaped copy with sensitive values redacted before hashing.",
            "Sensitive field paths are recorded by name only so private host, path, token, or key values are not copied into public child skills.",
        ],
    }
