"""Audit non-destructive create, update, and reuse skill-update plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from action_policy import CREATE_NEW, REUSE_EXISTING, UPDATE_EXISTING
from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


EXPECTED_ACTION_BY_DECISION = {
    "create": CREATE_NEW,
    "update": UPDATE_EXISTING,
    "reuse": REUSE_EXISTING,
}
REQUIRED_PUBLIC_FILES = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    action: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if action:
        item["action"] = action
    findings.append(item)


def is_relative_public_file(path: str) -> bool:
    if path not in REQUIRED_PUBLIC_FILES:
        return False
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def build_skill_update_audit(
    request: dict[str, Any],
    skill_update_plan: dict[str, Any],
) -> dict[str, Any]:
    """Audit skill-update guidance without touching existing child skills."""
    findings: list[dict[str, Any]] = []
    decision = str(skill_update_plan.get("discovery_decision") or "")
    action = str(skill_update_plan.get("recommended_action") or "")
    expected_action = EXPECTED_ACTION_BY_DECISION.get(decision)
    target_path = str(skill_update_plan.get("target_existing_skill_path") or "")
    candidate_path = str(skill_update_plan.get("candidate_child_skill_path") or "")
    merge_actions = skill_update_plan.get("merge_actions", [])
    missing_task_types = [str(item) for item in skill_update_plan.get("missing_task_types", [])]
    shape_update_required = bool(skill_update_plan.get("shape_update_required"))
    covered_task_types = [str(item) for item in skill_update_plan.get("covered_task_types", [])]
    inferred_task_types = [str(item) for item in skill_update_plan.get("inferred_task_types", [])]

    if skill_update_plan.get("status") != "pass":
        add_finding(findings, "error", "skill_update_plan_failed", "Skill update plan must pass before update audit.", action)
    if skill_update_plan.get("plan_only") is not True:
        add_finding(findings, "error", "skill_update_plan_not_plan_only", "Skill update plan must remain plan-only.", action)
    if expected_action is None:
        add_finding(findings, "error", "unknown_discovery_decision", "Discovery decision must be create, update, or reuse.", action)
    elif action != expected_action:
        add_finding(findings, "error", "action_decision_mismatch", "Recommended action does not match discovery decision.", action)

    if action == CREATE_NEW:
        if target_path:
            add_finding(findings, "error", "create_has_existing_target", "Create action must not carry an existing skill target.", action)
        if merge_actions:
            add_finding(findings, "error", "create_has_merge_actions", "Create action must not include merge actions.", action)
        if skill_update_plan.get("manual_review_required") is True:
            add_finding(findings, "warning", "create_manual_review_required", "Create usually should not require manual merge review.", action)
    elif action == UPDATE_EXISTING:
        if not target_path:
            add_finding(findings, "error", "update_missing_target", "Update action requires target_existing_skill_path.", action)
        if not missing_task_types and not shape_update_required:
            add_finding(findings, "error", "update_missing_delta", "Update action must identify missing task_type entries or child-skill shape updates.", action)
        if skill_update_plan.get("manual_review_required") is not True:
            add_finding(findings, "error", "update_missing_manual_review", "Update action requires manual review.", action)
        if not merge_actions:
            add_finding(findings, "error", "update_missing_merge_actions", "Update action requires merge actions for standard child files.", action)
    elif action == REUSE_EXISTING:
        if not target_path:
            add_finding(findings, "error", "reuse_missing_target", "Reuse action requires target_existing_skill_path.", action)
        if missing_task_types:
            add_finding(findings, "error", "reuse_has_task_delta", "Reuse action must not have missing task_type entries.", action)
        if merge_actions:
            add_finding(findings, "error", "reuse_has_merge_actions", "Reuse action must not include merge actions.", action)
        if skill_update_plan.get("manual_review_required") is not True:
            add_finding(findings, "warning", "reuse_without_manual_review", "Reuse should still require manual awareness of the existing skill.", action)

    expected_targets = set(REQUIRED_PUBLIC_FILES) if action == UPDATE_EXISTING else set()
    actual_targets = set()
    for item in merge_actions:
        source = str(item.get("source_candidate_file") or "")
        target = str(item.get("target_relative_file") or "")
        actual_targets.add(target)
        if item.get("action") != "merge_review_required":
            add_finding(findings, "error", "merge_action_not_review_required", "Merge action must require manual review.", action)
        if item.get("reason") is None:
            add_finding(findings, "error", "merge_action_missing_reason", "Merge action must include a reason.", action)
        if not is_relative_public_file(target):
            add_finding(findings, "error", "merge_target_outside_public_files", "Merge target must be a standard child skill file.", action)
        if candidate_path and source and not source.startswith(candidate_path):
            add_finding(findings, "error", "merge_source_outside_candidate", "Merge source must stay under candidate_child_skill_path.", action)
        if item.get("task_types_to_review") != missing_task_types:
            add_finding(findings, "error", "merge_task_delta_mismatch", "Merge action task delta must match missing_task_types.", action)

    missing_merge_targets = sorted(expected_targets.difference(actual_targets))
    extra_merge_targets = sorted(actual_targets.difference(expected_targets))
    if missing_merge_targets:
        add_finding(findings, "error", "update_missing_standard_merge_targets", "Update merge actions must cover every standard child file.", action)
    if extra_merge_targets:
        add_finding(findings, "error", "unexpected_merge_targets", "Merge actions include targets outside the expected update set.", action)

    if action in {UPDATE_EXISTING, REUSE_EXISTING} and not covered_task_types and inferred_task_types:
        add_finding(findings, "warning", "existing_skill_coverage_empty", "Existing skill coverage is empty despite an update or reuse action.", action)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "discovery_decision": decision,
        "recommended_action": action,
        "target_existing_skill_path": target_path,
        "candidate_child_skill_path": candidate_path,
        "required_public_files": REQUIRED_PUBLIC_FILES,
        "merge_action_count": len(merge_actions),
        "missing_task_types": missing_task_types,
        "shape_update_required": shape_update_required,
        "covered_task_types": covered_task_types,
        "inferred_task_types": inferred_task_types,
        "findings": findings,
        "policy": [
            "Skill update audit is plan-only and never reads, copies, or modifies existing skills.",
            "Update actions require target_existing_skill_path, missing task_type deltas or child-skill shape updates, and manual merge actions for every standard child file.",
            "Reuse actions must not carry merge actions or publish a duplicate generated child skill.",
            "Create actions must not point at an existing skill target.",
        ],
    }
