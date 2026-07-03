"""Audit Python-first backend support and reserved backend extension boundaries."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


IMPLEMENTED_BACKENDS = {"python"}
RESERVED_BACKENDS = {"r"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        finding["task_type"] = task_type
    findings.append(finding)


def refusal_reasons(task: dict[str, Any]) -> set[str]:
    return {
        str(item.get("reason_key"))
        for item in task.get("refusal_boundaries", [])
        if item.get("reason_key")
    }


def build_backend_extension_audit(
    request: dict[str, Any],
    backend_contract: dict[str, Any],
    environment_install_plan: dict[str, Any],
    task_catalog: dict[str, Any],
    source_parsing_audit: dict[str, Any],
) -> dict[str, Any]:
    """Check that backend support and extension reservations are explicit."""
    findings: list[dict[str, Any]] = []
    requested_backend = str(request.get("language_backend") or "python").lower()
    implemented = {str(item).lower() for item in backend_contract.get("implemented_backends", [])}
    reserved = {str(item).lower() for item in backend_contract.get("reserved_backends", [])}
    backend_status = str(backend_contract.get("status") or "")

    if implemented != IMPLEMENTED_BACKENDS:
        add_finding(
            findings,
            "error",
            "implemented_backend_set_changed",
            "The current builder must declare Python as the only implemented backend.",
        )
    if not RESERVED_BACKENDS.issubset(reserved):
        add_finding(
            findings,
            "error",
            "missing_reserved_r_backend",
            "The backend contract must reserve R as an explicit extension point.",
        )
    if requested_backend == "python" and backend_status != "supported":
        add_finding(
            findings,
            "error",
            "python_backend_not_supported",
            "Python backend requests must be marked supported.",
        )
    if requested_backend != "python" and backend_status != "extension_reserved":
        add_finding(
            findings,
            "error",
            "extension_backend_not_reserved",
            "Non-Python backend requests must be represented as extension_reserved.",
        )

    refusal = backend_contract.get("refusal_boundary") or {}
    if refusal.get("reason_key") != "backend_not_implemented":
        add_finding(
            findings,
            "error",
            "missing_backend_refusal_contract",
            "Backend extension reservations must expose a backend_not_implemented refusal boundary.",
        )

    install_strategy = str(environment_install_plan.get("install_strategy") or "")
    if requested_backend == "python" and install_strategy == "backend_extension_reserved":
        add_finding(
            findings,
            "error",
            "python_install_marked_extension_reserved",
            "Python backend installs must not use the extension-reserved install strategy.",
        )
    if requested_backend != "python":
        if install_strategy != "backend_extension_reserved":
            add_finding(
                findings,
                "error",
                "extension_backend_install_not_reserved",
                "Non-Python backend install planning must use backend_extension_reserved.",
            )
        if environment_install_plan.get("plan_only") is not True:
            add_finding(
                findings,
                "error",
                "extension_backend_install_not_plan_only",
                "Backend extension install planning must remain plan-only.",
            )
        for task in task_catalog.get("tasks", []):
            task_type = str(task.get("task_type") or "")
            if "backend_not_implemented" not in refusal_reasons(task):
                add_finding(
                    findings,
                    "error",
                    "task_missing_backend_refusal",
                    "Non-Python backend task_type must include backend_not_implemented refusal boundary.",
                    task_type,
                )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "requested_backend": requested_backend,
        "backend_contract_status": backend_status,
        "environment_install_plan_status": environment_install_plan.get("status"),
        "install_strategy": install_strategy,
        "implemented_backends": sorted(implemented),
        "reserved_backends": sorted(reserved),
        "r_source_count": source_parsing_audit.get("r_file_count", 0),
        "task_count": len(task_catalog.get("tasks", [])),
        "findings": findings,
        "policy": [
            "Python is the only implemented backend in the current builder.",
            "R is reserved as a backend extension and must not be silently installed or executed.",
            "Non-Python backend requests require a backend_not_implemented refusal boundary until an extension is implemented.",
        ],
    }
