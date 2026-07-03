"""Backend support contracts for Python-first builds and extension points."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def build_backend_contract(request: dict[str, Any]) -> dict[str, Any]:
    backend = str(request.get("language_backend") or "python").lower()
    supported = backend == "python"
    findings = []
    if not supported:
        findings.append(
            {
                "severity": "error",
                "code": "backend_not_implemented",
                "message": "Only the Python backend is implemented; other backends are reserved extension points.",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "requested_backend": backend,
        "status": "supported" if supported else "extension_reserved",
        "implemented_backends": ["python"],
        "reserved_backends": ["r"],
        "execution_policy": {
            "install_dependencies": "never_silent",
            "execute_tutorials": "only_with_explicit_execution_grounding_and_user_environment",
            "mark_verified": "only_successful_trace_for_same_task_type",
        },
        "refusal_boundary": {
            "reason_key": "backend_not_implemented",
            "refusal_type": "unsupported",
            "when": "The requested package or workflow requires a backend that is not implemented.",
        },
        "findings": findings,
    }
