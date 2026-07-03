"""Plan optional execution grounding without running package code."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def normalize_execution_environment(request: dict[str, Any]) -> dict[str, Any]:
    raw = request.get("execution_environment")
    env = raw if isinstance(raw, dict) else {}
    return {
        "mode": env.get("mode") or ("remote" if env.get("host") else "unspecified"),
        "host": env.get("host"),
        "working_directory": env.get("working_directory"),
        "environment_name": env.get("environment_name"),
        "node": env.get("node"),
        "cores": env.get("cores"),
        "remote_only": bool(env.get("remote_only", False)),
        "notes": env.get("notes") or [],
    }


def missing_environment_fields(environment: dict[str, Any]) -> list[str]:
    if environment.get("mode") != "remote" and not environment.get("remote_only"):
        return []
    required = ["host", "working_directory", "environment_name", "node", "cores"]
    return [field for field in required if not environment.get(field)]


def task_execution_plan(task: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    status = task.get("verification_status")
    if status == "execution_verified":
        action = "record_verified_trace"
    elif status == "execution_failed":
        action = "record_failed_trace_and_keep_unverified"
    else:
        action = "source_grounded_until_trace_is_supplied"
    return {
        "task_type": task_type,
        "current_verification_status": status,
        "trace_ref": task.get("trace_ref"),
        "planned_action": action,
        "requires_user_approval": True,
        "requires_environment": True,
        "environment_mode": environment.get("mode"),
        "preflight_checks": [
            "confirm package installation command from environment.md",
            "confirm input paths and required metadata fields",
            "run only the official tutorial or minimal documented workflow for this task_type",
            "capture command, package versions, inputs, outputs, status, and error text as execution evidence",
        ],
        "success_criteria": [
            "tutorial or minimal workflow exits successfully",
            "expected output exists and can be opened by the documented reader",
            "trace includes task_type, command, environment, status, and output validation",
        ],
        "refusal_if_missing": [
            "execution environment approval",
            "input data path or required metadata",
            "official tutorial/API evidence for the selected task_type",
        ],
    }


def build_execution_plan(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    eval_plan: dict[str, Any],
) -> dict[str, Any]:
    environment = normalize_execution_environment(request)
    missing = missing_environment_fields(environment)
    plans = [task_execution_plan(task, environment) for task in task_catalog.get("tasks", [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "plan_only": True,
        "environment": environment,
        "missing_environment_fields": missing,
        "task_count": len(plans),
        "tasks": plans,
        "eval_scenario_count": eval_plan.get("scenario_count", 0),
        "policy": [
            "This artifact is a plan only; it must not install packages or execute tutorials.",
            "Only supplied successful execution evidence can change a task_type to execution_verified.",
            "Failed execution evidence is useful troubleshooting evidence but must not be labeled verified.",
        ],
    }
