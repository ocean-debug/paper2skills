"""Build reviewable child-skill draft candidate artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def task_api_refs(api_grounding: dict[str, Any], task_type: str, limit: int = 12) -> list[str]:
    bucket = api_grounding.get("by_task_type", {}).get(task_type, {})
    return list(bucket.get("api_candidates", []))[:limit]


def task_interface_refs(interface_grounding: dict[str, Any] | None, task_type: str, limit: int = 12) -> list[str]:
    if not interface_grounding:
        return []
    bucket = interface_grounding.get("by_task_type", {}).get(task_type, {})
    return list(bucket.get("interfaces", []))[:limit]


def task_risk_notes(task: dict[str, Any], api_refs: list[str], interface_refs: list[str]) -> list[str]:
    notes = []
    if not task.get("evidence_refs"):
        notes.append("task has no evidence references")
    if not api_refs:
        notes.append("no parsed API candidate was linked to this task_type")
    if api_refs and not interface_refs:
        notes.append("API candidates exist, but no inspected interface is linked to this task_type")
    if task.get("verification_status") == "execution_verified" and not task.get("trace_ref"):
        notes.append("execution_verified label has no trace_ref")
    if task.get("verification_status") == "source_grounded":
        notes.append("source-grounded only; do not claim execution verification")
    return notes


def build_draft_candidates(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    method_name = str(request.get("method_name") or request.get("package_name"))
    tasks = []
    for task in task_catalog.get("tasks", []):
        api_refs = task_api_refs(api_grounding, str(task.get("task_type")))
        interface_refs = task_interface_refs(interface_grounding, str(task.get("task_type")))
        tasks.append(
            {
                "task_type": task.get("task_type"),
                "verification_status": task.get("verification_status"),
                "evidence_refs": task.get("evidence_refs", []),
                "api_candidate_refs": api_refs,
                "interface_refs": interface_refs,
                "route_count": len([route for route in router.get("routes", []) if route.get("task_type") == task.get("task_type")]),
                "risk_notes": task_risk_notes(task, api_refs, interface_refs),
            }
        )
    candidate = {
        "candidate_id": f"child-skill:{slugify(method_name)}",
        "skill_name": slugify(method_name),
        "package_name": request.get("package_name"),
        "method_name": method_name,
        "target_agent": request.get("target_agent"),
        "layout": "scientific-agent-skills-lightweight",
        "one_package_one_skill": True,
        "discovery_decision": discovery_report.get("decision"),
        "recommended_action": discovery_report.get("decision"),
        "task_count": len(tasks),
        "tasks": tasks,
        "required_references": [
            "task-types.md",
            "input-output-contracts.md",
            "limitations-and-refusal.md",
            "validation.md",
            "troubleshooting.md",
            "evidence.md",
            "environment.md",
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "candidate_count": 1,
        "candidates": [candidate],
        "notes": [
            "A package produces one child-skill candidate.",
            "Multiple capabilities remain inside the same child skill as task_type entries.",
        ],
    }
