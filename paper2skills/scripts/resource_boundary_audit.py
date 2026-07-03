"""Audit model and external-resource boundaries across build artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_RESOURCE_REFUSALS = [
    "explicit approval for model, weight, or data downloads",
    "permission, license, login, or token required by external resources",
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def rendered_contains(rendered_text: str, needles: list[str]) -> bool:
    lowered = rendered_text.lower()
    return all(needle.lower() in lowered for needle in needles)


def build_resource_boundary_audit(
    request: dict[str, Any],
    resource_inventory: dict[str, Any],
    environment_install_plan: dict[str, Any],
    child_skill_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    resource_count = int(resource_inventory.get("resource_count", 0) or 0)
    risk_counts = dict(resource_inventory.get("risk_counts", {}))
    refusals = [str(item).lower() for item in environment_install_plan.get("refusal_if_missing", [])]
    child_skill_files = child_skill_files or {}
    rendered_text = "\n".join(child_skill_files.values())

    if resource_inventory.get("status") != "pass":
        add_finding(findings, "error", "resource_inventory_failed", "Resource inventory must pass before resource boundary audit.")

    if resource_count > 0:
        if not any("model" in item or "weight" in item or "download" in item for item in refusals):
            add_finding(
                findings,
                "error",
                "install_plan_missing_resource_refusal",
                "Environment install plan must refuse execution when required model, weight, data, or download approval is missing.",
            )
        if not rendered_contains(rendered_text, ["Resource Boundaries", "Do not download"]):
            add_finding(
                findings,
                "error",
                "child_skill_missing_resource_boundaries",
                "Generated child skill references must render model/data resource boundaries.",
            )

    if risk_counts.get("permission_or_license_required") and not any("permission" in item or "license" in item or "token" in item for item in refusals):
        add_finding(
            findings,
            "error",
            "install_plan_missing_permission_refusal",
            "Environment install plan must refuse execution when resource permission, license, login, or token requirements are unresolved.",
        )

    if request.get("execution_grounded") and risk_counts.get("permission_or_license_required"):
        add_finding(
            findings,
            "warning",
            "execution_grounding_has_resource_permissions",
            "Execution grounding may require explicit resource access approval before replay can be attempted.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "resource_count": resource_count,
        "risk_counts": risk_counts,
        "required_refusal_boundaries": REQUIRED_RESOURCE_REFUSALS,
        "environment_refusal_if_missing": environment_install_plan.get("refusal_if_missing", []),
        "rendered_files_checked": sorted(child_skill_files),
        "findings": findings,
        "policy": [
            "Model, checkpoint, and data resources are execution boundaries.",
            "Resource availability cannot be inferred from source mentions.",
            "Child skills must refuse or ask for approval when required resources are missing, gated, licensed, token-protected, or likely to trigger large downloads.",
        ],
    }
