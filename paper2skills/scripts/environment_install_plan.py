"""Plan environment installation for optional execution grounding."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def unique(values: list[str]) -> list[str]:
    seen = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def dependency_hints(environment_spec: dict[str, Any]) -> list[str]:
    declared = [str(item) for item in environment_spec.get("declared_dependencies", [])]
    imports = [str(item) for item in environment_spec.get("imported_modules", [])]
    return unique(declared + imports)[:80]


def install_strategy(request: dict[str, Any], environment_spec: dict[str, Any]) -> str:
    if str(request.get("language_backend") or "python").lower() != "python":
        return "backend_extension_reserved"
    dep_sources = environment_spec.get("dependency_sources", [])
    file_names = {str(source.get("file_name") or "").lower() for source in dep_sources}
    if any(name in file_names for name in {"environment.yml", "environment.yaml", "conda.yml", "conda.yaml"}):
        return "conda_environment_file"
    if "pyproject.toml" in file_names:
        return "python_project_install"
    if any(name.startswith("requirements") for name in file_names):
        return "pip_requirements"
    if dependency_hints(environment_spec):
        return "dependency_hint_install"
    return "manual_environment_required"


def planned_steps(strategy: str, environment_spec: dict[str, Any]) -> list[str]:
    if strategy == "conda_environment_file":
        return [
            "Review the detected conda environment file and confirm the target environment name.",
            "Create or update the environment only after explicit approval.",
            "Record package versions after installation.",
        ]
    if strategy == "python_project_install":
        return [
            "Review pyproject.toml dependency and Python-version hints.",
            "Create an isolated Python environment after explicit approval.",
            "Install the project using the documented package-manager path and record versions.",
        ]
    if strategy == "pip_requirements":
        return [
            "Review requirements file dependency hints.",
            "Create an isolated Python environment after explicit approval.",
            "Install requirements and record package versions.",
        ]
    if strategy == "dependency_hint_install":
        deps = ", ".join(dependency_hints(environment_spec)[:12])
        return [
            f"Review mined dependency/import hints: {deps}.",
            "Ask the user to confirm the authoritative install command.",
            "Install only after explicit approval and record package versions.",
        ]
    if strategy == "backend_extension_reserved":
        return [
            "Do not install or execute this backend in the current implementation.",
            "Return the backend_not_implemented refusal boundary unless an extension backend is added.",
        ]
    return [
        "Ask the user for an authoritative installation command or environment file.",
        "Do not create or mutate an environment until that command is supplied and approved.",
    ]


def build_environment_install_plan(
    request: dict[str, Any],
    environment_spec: dict[str, Any],
    backend_contract: dict[str, Any],
    execution_plan: dict[str, Any],
    resource_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    environment = execution_plan.get("environment", {})
    missing_fields = list(execution_plan.get("missing_environment_fields", []))
    strategy = install_strategy(request, environment_spec)
    resource_inventory = resource_inventory or {}
    resource_count = int(resource_inventory.get("resource_count", 0) or 0)
    risk_counts = dict(resource_inventory.get("risk_counts", {}))
    findings = []
    if backend_contract.get("status") != "supported":
        findings.append(
            {
                "severity": "error",
                "code": "backend_not_supported_for_install",
                "message": "Environment installation cannot proceed for an unimplemented backend.",
            }
        )
    if request.get("execution_grounded") and missing_fields:
        findings.append(
            {
                "severity": "error",
                "code": "execution_grounding_missing_environment_fields",
                "message": "Execution grounding was requested but required environment fields are missing.",
            }
        )
    if strategy == "manual_environment_required":
        findings.append(
            {
                "severity": "warning",
                "code": "no_install_source_detected",
                "message": "No dependency manifest or dependency hints were found; installation needs user-supplied instructions.",
            }
        )
    if risk_counts.get("permission_or_license_required"):
        findings.append(
            {
                "severity": "warning",
                "code": "resource_permission_or_license_required",
                "message": "Detected model or data resources may require permission, license review, login, or tokens before execution.",
            }
        )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "environment": environment,
        "missing_environment_fields": missing_fields,
        "backend_status": backend_contract.get("status"),
        "install_strategy": strategy,
        "dependency_sources": environment_spec.get("dependency_sources", []),
        "dependency_hints": dependency_hints(environment_spec),
        "python_requires": environment_spec.get("python_requires", []),
        "gpu_hints": environment_spec.get("gpu_hints", []),
        "resource_count": resource_count,
        "resource_risk_counts": risk_counts,
        "requires_user_approval": True,
        "planned_steps": planned_steps(strategy, environment_spec),
        "refusal_if_missing": [
            "explicit user approval for environment mutation",
            "authoritative install command or dependency manifest",
            "explicit approval for model, weight, or data downloads",
            "permission, license, login, or token required by external resources",
            "required remote execution fields when remote_only or mode is remote",
            "implemented backend support",
        ],
        "trace_requirements_after_install": [
            "environment name or path",
            "package versions",
            "install command summary",
            "status",
            "stderr or failure reason if failed",
        ],
        "findings": findings,
        "policy": [
            "This artifact plans installation only; it must not install packages.",
            "Environment mutation requires explicit user approval and the requested execution environment.",
            "Installation success does not verify any task_type until a matching successful execution trace is supplied.",
        ],
    }
