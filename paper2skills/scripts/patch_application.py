"""Audit agent-driven review patch plans and their application."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def patch_record(iteration: dict[str, Any]) -> dict[str, Any]:
    patch = iteration.get("patch", {})
    patch_plan = iteration.get("patch_plan", {})
    patch_actions = patch.get("actions", [])
    plan_actions = patch_plan.get("actions", [])
    planned_artifacts = sorted({str(action.get("artifact")) for action in plan_actions if action.get("artifact")})
    applied_artifacts = sorted({str(action.get("artifact")) for action in patch_actions if action.get("artifact")})
    planned_action_keys = {
        (str(action.get("artifact")), str(action.get("task_type")), str(action.get("action")))
        for action in plan_actions
    }
    applied_action_keys = {
        (str(action.get("artifact")), str(action.get("task_type")), str(action.get("action")))
        for action in patch_actions
    }
    missing_apply = sorted(planned_action_keys.difference(applied_action_keys))
    return {
        "iteration": iteration.get("iteration"),
        "changed": bool(patch.get("changed")),
        "finding_count": patch.get("finding_count", 0),
        "patch_summary": patch.get("patch_summary"),
        "planned_action_count": len(plan_actions),
        "applied_action_count": len(patch_actions),
        "planned_artifacts": planned_artifacts,
        "applied_artifacts": applied_artifacts,
        "missing_apply_count": len(missing_apply),
        "missing_apply": [
            {
                "artifact": artifact,
                "task_type": None if task_type == "None" else task_type,
                "action": action,
            }
            for artifact, task_type, action in missing_apply
        ],
        "actions": patch_actions,
    }


def build_patch_application(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    records = [patch_record(item) for item in review_result.get("iterations", [])]
    findings = []
    for record in records:
        if record["missing_apply_count"]:
            findings.append(
                {
                    "severity": "error",
                    "code": "planned_patch_not_applied",
                    "message": "Patch plan contains actions that are absent from the applied patch record.",
                    "iteration": record.get("iteration"),
                }
            )
        if record["changed"] and record["applied_action_count"] == 0:
            findings.append(
                {
                    "severity": "error",
                    "code": "changed_patch_without_actions",
                    "message": "Patch claims changes but records no applied actions.",
                    "iteration": record.get("iteration"),
                }
            )
    changed_iterations = [record for record in records if record["changed"]]
    changed_artifacts = sorted(
        {
            artifact
            for record in records
            for artifact in record.get("applied_artifacts", [])
        }
    )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "iteration_count": len(records),
        "changed_iteration_count": len(changed_iterations),
        "changed_artifacts": changed_artifacts,
        "records": records,
        "findings": findings,
        "policy": [
            "Patch application is an audit artifact for bounded agent-driven review patches.",
            "It records planned and applied actions but does not mutate files by itself.",
        ],
    }
