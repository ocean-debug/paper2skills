"""Audit candidate identity and gate evolution across release artifacts."""

from __future__ import annotations

from typing import Any

from action_policy import REUSE_EXISTING, is_publish_status_acceptable
from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def active_version(candidate_registry: dict[str, Any]) -> dict[str, Any]:
    active_id = candidate_registry.get("active_version_id")
    for version in candidate_registry.get("versions", []):
        if version.get("version_id") == active_id:
            return version
    return {}


def candidate_ids(draft_candidates: dict[str, Any]) -> set[str]:
    return {str(item.get("candidate_id")) for item in draft_candidates.get("candidates", []) if item.get("candidate_id")}


def build_candidate_evolution_audit(
    request: dict[str, Any],
    draft_candidates: dict[str, Any],
    candidate_registry: dict[str, Any],
    candidate_selection_audit: dict[str, Any],
    candidate_promotion_audit: dict[str, Any],
    release_package: dict[str, Any],
    final_candidate_audit: dict[str, Any],
    publish_gate: dict[str, Any],
    skill_update_plan: dict[str, Any],
    review_iteration_log: dict[str, Any],
) -> dict[str, Any]:
    """Check that candidate identity and status evolve consistently."""
    findings: list[dict[str, Any]] = []
    active = active_version(candidate_registry)
    active_version_id = candidate_registry.get("active_version_id")
    active_candidate_id = active.get("candidate_id")
    drafts = candidate_ids(draft_candidates)
    recommended_action = skill_update_plan.get("recommended_action")

    records = [
        {
            "stage": "draft",
            "candidate_count": draft_candidates.get("candidate_count", 0),
            "candidate_ids": sorted(drafts),
        },
        {
            "stage": "registry",
            "active_version_id": active_version_id,
            "candidate_id": active_candidate_id,
            "status": active.get("status"),
            "review_status": active.get("review_status"),
            "review_iteration_count": active.get("review_iteration_count"),
        },
        {
            "stage": "selection",
            "selected_version_id": candidate_selection_audit.get("selected_version_id"),
            "selected_candidate_id": candidate_selection_audit.get("selected_candidate_id"),
            "status": candidate_selection_audit.get("status"),
        },
        {
            "stage": "promotion",
            "active_version_id": candidate_promotion_audit.get("active_version_id"),
            "selected_candidate_id": candidate_promotion_audit.get("selected_candidate_id"),
            "status": candidate_promotion_audit.get("status"),
            "promoted_to_release": candidate_promotion_audit.get("promoted_to_release"),
        },
        {
            "stage": "release_package",
            "candidate_version": release_package.get("candidate_version"),
            "status": release_package.get("status"),
            "recommended_action": release_package.get("recommended_action"),
        },
        {
            "stage": "final_candidate",
            "active_version_id": final_candidate_audit.get("active_version_id"),
            "release_candidate_version": final_candidate_audit.get("release_candidate_version"),
            "status": final_candidate_audit.get("status"),
            "finalized_for_release": final_candidate_audit.get("finalized_for_release"),
        },
    ]

    if draft_candidates.get("candidate_count") != 1:
        add_finding(findings, "error", "candidate_count_not_one", "Exactly one child-skill candidate is allowed per package.")
    if not active:
        add_finding(findings, "error", "active_version_missing", "Candidate registry active_version_id must resolve to a version.")
    if active_candidate_id not in drafts:
        add_finding(findings, "error", "active_candidate_not_drafted", "Active registry candidate_id must exist in draft_candidates.")
    if candidate_selection_audit.get("selected_version_id") != active_version_id:
        add_finding(findings, "error", "selection_version_mismatch", "Selection audit must point to the active registry version.")
    if candidate_selection_audit.get("selected_candidate_id") != active_candidate_id:
        add_finding(findings, "error", "selection_candidate_mismatch", "Selection audit must point to the active candidate id.")
    if candidate_promotion_audit.get("active_version_id") != active_version_id:
        add_finding(findings, "error", "promotion_version_mismatch", "Promotion audit must point to the active registry version.")
    if release_package.get("candidate_version") != active_version_id:
        add_finding(findings, "error", "release_version_mismatch", "Release package must point to the active registry version.")
    if final_candidate_audit.get("active_version_id") != active_version_id:
        add_finding(findings, "error", "final_active_version_mismatch", "Final candidate audit must point to the active registry version.")
    if final_candidate_audit.get("release_candidate_version") != active_version_id:
        add_finding(findings, "error", "final_release_version_mismatch", "Final candidate audit release version must match the active registry version.")
    if active.get("status") != publish_gate.get("status"):
        add_finding(findings, "error", "active_status_publish_mismatch", "Active candidate status must mirror publish_gate status.")
    if not is_publish_status_acceptable(recommended_action, publish_gate.get("status")):
        add_finding(findings, "error", "action_publish_status_invalid", "Publish status must match the recommended create/update/reuse action.")
    if release_package.get("recommended_action") != recommended_action:
        add_finding(findings, "error", "release_action_mismatch", "Release package action must match skill_update_plan recommended action.")
    if final_candidate_audit.get("recommended_action") != recommended_action:
        add_finding(findings, "error", "final_action_mismatch", "Final candidate action must match skill_update_plan recommended action.")
    if candidate_selection_audit.get("status") != "pass":
        add_finding(findings, "error", "selection_not_passed", "Candidate evolution requires selection audit to pass.")
    if candidate_promotion_audit.get("status") != "pass":
        add_finding(findings, "error", "promotion_not_passed", "Candidate evolution requires promotion audit to pass.")
    if final_candidate_audit.get("status") != "pass":
        add_finding(findings, "error", "final_candidate_not_passed", "Candidate evolution requires final candidate audit to pass.")
    if review_iteration_log.get("status") != "pass":
        add_finding(findings, "error", "review_iteration_log_not_passed", "Candidate evolution requires review iteration log to pass.")
    if active.get("review_iteration_count") != review_iteration_log.get("iteration_count"):
        add_finding(findings, "error", "candidate_review_iteration_mismatch", "Candidate registry review iteration count must match review_iteration_log.")
    if recommended_action == REUSE_EXISTING and candidate_promotion_audit.get("promoted_to_release"):
        add_finding(findings, "error", "reuse_promoted_duplicate", "Reuse action must not promote a generated duplicate candidate.")

    has_errors = any(finding.get("severity") == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "recommended_action": recommended_action,
        "active_version_id": active_version_id,
        "active_candidate_id": active_candidate_id,
        "publish_gate_status": publish_gate.get("status"),
        "review_iteration_count": review_iteration_log.get("iteration_count", 0),
        "stage_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Candidate evolution audit is manifest-only; it does not copy, install, or mutate files.",
            "One package must keep one selected candidate whose identity is stable across registry, selection, promotion, release, and final audit artifacts.",
            "Reuse actions may pass as no-copy decisions but must not promote a generated duplicate release.",
        ],
    }
