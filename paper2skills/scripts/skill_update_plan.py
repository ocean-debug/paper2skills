"""Plan-only update guidance when Discovery finds a related child skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def best_match(discovery_report: dict[str, Any]) -> dict[str, Any]:
    matches = discovery_report.get("matches", [])
    return matches[0] if matches else {}


def merge_actions(child_skill_dir: Path, missing_task_types: list[str]) -> list[dict[str, Any]]:
    files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    actions = []
    for rel in files:
        actions.append(
            {
                "source_candidate_file": str(child_skill_dir / rel),
                "target_relative_file": rel,
                "action": "merge_review_required",
                "reason": "Preserve existing skill content while adding or revising task_type contracts.",
                "task_types_to_review": missing_task_types,
            }
        )
    return actions


def build_skill_update_plan(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    discovery_audit: dict[str, Any],
    task_catalog: dict[str, Any],
    child_skill_dir: Path,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    decision = str(discovery_report.get("decision") or "create")
    match = best_match(discovery_report)
    task_types = [str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")]
    missing_task_types = sorted(set(match.get("missing_task_types", []) or []))
    target_path = str(match.get("path") or "")
    shape_update_required = match.get("shape_status") not in {None, "", "pass"}

    if decision == "update" and not target_path:
        add_finding(findings, "error", "update_without_target", "Update decision requires a target existing skill path.")
    if decision == "update" and not missing_task_types and not shape_update_required:
        add_finding(findings, "error", "update_without_delta", "Update decision must identify missing task_type entries or child-skill shape updates.")
    if decision == "reuse" and missing_task_types:
        add_finding(findings, "error", "reuse_with_missing_task_types", "Reuse cannot have missing task_type entries.")
    if discovery_audit.get("status") == "fail":
        add_finding(findings, "error", "discovery_audit_failed", "Discovery audit must pass before planning reuse, update, or create.")

    if decision == "update":
        recommended_action = "update_existing"
    elif decision == "reuse":
        recommended_action = "reuse_existing"
    else:
        recommended_action = "create_new"

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "discovery_decision": decision,
        "recommended_action": recommended_action,
        "target_existing_skill_path": target_path,
        "candidate_child_skill_path": str(child_skill_dir),
        "covered_task_types": sorted(set(match.get("covered_task_types", []) or [])),
        "missing_task_types": missing_task_types,
        "shape_update_required": shape_update_required,
        "shape_findings": match.get("shape_findings", []),
        "inferred_task_types": task_types,
        "merge_actions": merge_actions(child_skill_dir, missing_task_types) if decision == "update" else [],
        "manual_review_required": decision in {"update", "reuse"},
        "findings": findings,
        "policy": [
            "This artifact is a plan only; it does not modify existing skills.",
            "Update existing skills when Discovery finds a related skill that misses task_type coverage or standard child-skill shape.",
            "Reuse existing skills instead of publishing a duplicate when all inferred task_types are covered.",
            "Create a new child skill only when no covering or updatable skill is found.",
        ],
    }
