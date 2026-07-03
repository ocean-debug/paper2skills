"""Plan tutorial reproduction for optional execution grounding."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def tutorial_task_hint(tutorial: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(tutorial.get("tutorial_id") or ""),
            str(tutorial.get("source_path") or ""),
            " ".join(str(step.get("summary") or "") for step in tutorial.get("steps", [])[:12]),
            " ".join(
                " ".join(str(call) for call in step.get("api_calls", [])[:8])
                for step in tutorial.get("steps", [])[:12]
            ),
        ]
    ).lower()
    return slugify(text, "tutorial")


def tutorials_for_task(task_type: str, tutorial_catalog: dict[str, Any]) -> list[dict[str, Any]]:
    task_key = task_type.replace("_", "-")
    matches = []
    for tutorial in tutorial_catalog.get("tutorials", []):
        haystack = tutorial_task_hint(tutorial)
        if task_type in haystack or task_key in haystack:
            matches.append(tutorial)
    if matches:
        return matches
    return list(tutorial_catalog.get("tutorials", []))


def dependency_hints(environment_spec: dict[str, Any]) -> list[str]:
    declared = [str(item) for item in environment_spec.get("declared_dependencies", [])[:30]]
    imports = [str(item) for item in environment_spec.get("imported_modules", [])[:30]]
    merged = []
    for item in declared + imports:
        if item and item not in merged:
            merged.append(item)
    return merged


def task_execution_boundary(execution_plan: dict[str, Any], task_type: str) -> dict[str, Any]:
    for task in execution_plan.get("tasks", []):
        if task.get("task_type") == task_type:
            return task
    return {}


def reproduction_record(
    task: dict[str, Any],
    tutorials: list[dict[str, Any]],
    environment_spec: dict[str, Any],
    execution_plan: dict[str, Any],
    missing_environment_fields: list[str],
) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    selected = tutorials[:2]
    boundary = task_execution_boundary(execution_plan, task_type)
    replay_steps = []
    for tutorial in selected:
        replay_steps.append(
            {
                "tutorial_id": tutorial.get("tutorial_id"),
                "source_evidence_id": tutorial.get("source_evidence_id"),
                "source_path": tutorial.get("source_path"),
                "step_count": tutorial.get("step_count", 0),
                "steps": tutorial.get("steps", [])[:12],
            }
        )
    status = "planned" if replay_steps else "blocked"
    return {
        "replay_id": f"reproduce:{slugify(task_type)}",
        "task_type": task_type,
        "status": status,
        "current_verification_status": task.get("verification_status"),
        "tutorial_replay_sources": replay_steps,
        "dependency_hints": dependency_hints(environment_spec),
        "environment": execution_plan.get("environment", {}),
        "missing_environment_fields": missing_environment_fields,
        "preflight_checks": boundary.get("preflight_checks", []),
        "trace_requirements": [
            "task_type",
            "status",
            "trace_ref",
            "environment",
            "inputs",
            "outputs",
            "validation_checks",
            "command_or_notebook",
            "package_versions",
            "stdout_or_log_summary",
            "stderr_or_failure_reason_if_failed",
        ],
        "success_criteria": boundary.get("success_criteria", []),
        "refusal_if_missing": boundary.get("refusal_if_missing", []),
        "policy": "Do not execute this plan unless the user explicitly approves the environment and trace capture.",
    }


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


def build_tutorial_reproduction_plan(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    environment_spec: dict[str, Any],
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    missing_environment_fields = list(execution_plan.get("missing_environment_fields", []))
    replays = []
    findings: list[dict[str, Any]] = []
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        tutorials = tutorials_for_task(task_type, tutorial_catalog)
        record = reproduction_record(task, tutorials, environment_spec, execution_plan, missing_environment_fields)
        replays.append(record)
        if record["status"] == "blocked":
            severity = "error" if request.get("execution_grounded") else "warning"
            add_finding(
                findings,
                severity,
                "task_without_tutorial_replay_source",
                "Task_type has no tutorial/example steps available for execution-grounded reproduction planning.",
                task_type,
            )

    if request.get("execution_grounded") and missing_environment_fields:
        add_finding(
            findings,
            "error",
            "execution_grounding_missing_environment_fields",
            "Execution grounding was requested but the execution environment is incomplete.",
        )
    if request.get("execution_grounded") and tutorial_catalog.get("tutorial_count", 0) == 0:
        add_finding(
            findings,
            "error",
            "execution_grounding_without_tutorial_steps",
            "Execution grounding was requested but no tutorial/example steps were mined.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "plan_only": True,
        "tutorial_count": tutorial_catalog.get("tutorial_count", 0),
        "task_count": len(replays),
        "replay_count": len(replays),
        "missing_environment_fields": missing_environment_fields,
        "replays": replays,
        "findings": findings,
        "policy": [
            "This artifact plans tutorial reproduction; it never installs packages or runs code.",
            "Only explicit execution evidence produced outside this build can mark task_type entries execution_verified.",
            "When execution_grounded is requested, missing tutorial steps or environment fields block reproduction planning.",
        ],
    }
