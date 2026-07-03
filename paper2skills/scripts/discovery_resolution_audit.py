"""Audit final Discovery resolution against preflight and update planning."""

from __future__ import annotations

from typing import Any

from action_policy import CREATE_NEW, REUSE_EXISTING, UPDATE_EXISTING
from common import now_utc
from constants import SCHEMA_VERSION


EXPECTED_ACTION_BY_DECISION = {
    "create": CREATE_NEW,
    "update": UPDATE_EXISTING,
    "reuse": REUSE_EXISTING,
}
STRONG_MATCH_LEVELS = {"exact_repo", "paper_reference", "package_task_overlap"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    artifact: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if artifact:
        item["artifact"] = artifact
    findings.append(item)


def strong_matches(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        match for match in report.get("matches", [])
        if match.get("match_level") in STRONG_MATCH_LEVELS and float(match.get("confidence", 0.0)) >= 0.35
    ]


def ambiguous_high_confidence(matches: list[dict[str, Any]]) -> bool:
    if len(matches) < 2:
        return False
    ordered = sorted(matches, key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
    top = float(ordered[0].get("confidence", 0.0))
    runner_up = float(ordered[1].get("confidence", 0.0))
    return top >= 0.55 and runner_up >= 0.55 and abs(top - runner_up) <= 0.1


def best_path(report: dict[str, Any]) -> str:
    matches = report.get("matches", [])
    return str(matches[0].get("path") or "") if matches else ""


def build_discovery_resolution_audit(
    request: dict[str, Any],
    discovery_preflight: dict[str, Any],
    discovery_report: dict[str, Any],
    discovery_match_audit: dict[str, Any],
    skill_update_plan: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit that Discovery resolution is non-duplicating."""
    findings: list[dict[str, Any]] = []
    preflight_decision = str(discovery_preflight.get("decision") or "")
    final_decision = str(discovery_report.get("decision") or "")
    recommended_action = str(skill_update_plan.get("recommended_action") or "")
    expected_action = EXPECTED_ACTION_BY_DECISION.get(final_decision)
    final_best_path = best_path(discovery_report)
    plan_target = str(skill_update_plan.get("target_existing_skill_path") or "")
    shape_update_required = bool(skill_update_plan.get("shape_update_required"))
    final_strong_matches = strong_matches(discovery_report)
    preflight_strong_matches = strong_matches(discovery_preflight)
    ambiguous_final = ambiguous_high_confidence(discovery_report.get("matches", []))

    if preflight_decision not in EXPECTED_ACTION_BY_DECISION:
        add_finding(findings, "error", "invalid_preflight_decision", "Discovery preflight decision must be create, update, or reuse.", "discovery_preflight")
    if final_decision not in EXPECTED_ACTION_BY_DECISION:
        add_finding(findings, "error", "invalid_final_decision", "Final Discovery decision must be create, update, or reuse.", "discovery_report")
    if discovery_match_audit.get("status") != "pass":
        add_finding(findings, "error", "discovery_match_audit_failed", "Discovery resolution requires passing match audit.", "discovery_match_audit")
    if skill_update_plan.get("status") != "pass":
        add_finding(findings, "error", "skill_update_plan_failed", "Discovery resolution requires passing skill update plan.", "skill_update_plan")
    if skill_update_plan.get("plan_only") is not True:
        add_finding(findings, "error", "skill_update_plan_not_plan_only", "Discovery resolution must remain plan-only.", "skill_update_plan")

    if expected_action and recommended_action != expected_action:
        add_finding(findings, "error", "decision_action_mismatch", "Skill update recommended_action must match final Discovery decision.", "skill_update_plan")

    if final_decision == "create" and final_strong_matches:
        add_finding(findings, "error", "create_with_final_strong_match", "Create would duplicate a strong existing child-skill match.", "discovery_report")
    if final_decision == "create" and preflight_strong_matches:
        add_finding(findings, "error", "create_with_preflight_strong_match", "Create conflicts with a strong preflight existing-skill match.", "discovery_preflight")

    if final_decision in {"update", "reuse"}:
        if not final_best_path:
            add_finding(findings, "error", "existing_action_without_final_match", "Update or reuse requires a final matched existing child skill.", "discovery_report")
        if not plan_target:
            add_finding(findings, "error", "existing_action_without_plan_target", "Update or reuse requires target_existing_skill_path in the update plan.", "skill_update_plan")
        if final_best_path and plan_target and final_best_path != plan_target:
            add_finding(findings, "error", "plan_target_not_final_best_match", "Update plan target must match final Discovery best match.", "skill_update_plan")

    if final_decision == "reuse":
        if skill_update_plan.get("missing_task_types"):
            add_finding(findings, "error", "reuse_with_missing_task_types", "Reuse must not have missing task_type entries.", "skill_update_plan")
        if discovery_match_audit.get("best_match", {}).get("shape_status") != "pass":
            add_finding(findings, "error", "reuse_with_nonstandard_shape", "Reuse requires the existing child skill to have a standard lightweight shape.", "discovery_match_audit")

    if final_decision == "update":
        if not skill_update_plan.get("missing_task_types") and not shape_update_required:
            add_finding(findings, "error", "update_without_delta", "Update must record missing task_type entries or child-skill shape updates.", "skill_update_plan")
        if skill_update_plan.get("manual_review_required") is not True:
            add_finding(findings, "error", "update_without_manual_review", "Update must require manual merge review.", "skill_update_plan")

    if ambiguous_final:
        add_finding(findings, "error", "ambiguous_high_confidence_resolution", "High-confidence existing-skill matches are too close for automatic resolution.", "discovery_report")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "preflight_decision": preflight_decision,
        "final_decision": final_decision,
        "recommended_action": recommended_action,
        "expected_action": expected_action,
        "final_best_match_path": final_best_path,
        "plan_target_existing_skill_path": plan_target,
        "shape_update_required": shape_update_required,
        "preflight_strong_match_count": len(preflight_strong_matches),
        "final_strong_match_count": len(final_strong_matches),
        "ambiguous_high_confidence": ambiguous_final,
        "findings": findings,
        "policy": [
            "Discovery resolution is plan-only and never modifies existing skills.",
            "Create is blocked when strong existing-skill matches would risk duplication.",
            "Update and reuse must target the final Discovery best match.",
            "Ambiguous high-confidence matches require manual resolution before publish.",
        ],
    }
