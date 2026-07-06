"""Audit active candidate promotion before release packaging."""

from __future__ import annotations

from typing import Any

from action_policy import REUSE_EXISTING, UPDATE_EXISTING, is_publish_status_acceptable
from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


REQUIRED_CANDIDATE_FILES = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]


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


def build_candidate_promotion_audit(
    request: dict[str, Any],
    draft_candidates: dict[str, Any],
    candidate_registry: dict[str, Any],
    candidate_selection_audit: dict[str, Any],
    publish_gate: dict[str, Any],
    skill_update_plan: dict[str, Any],
) -> dict[str, Any]:
    """Check that candidate selection is explicit and aligned with publish gates."""
    findings: list[dict[str, Any]] = []
    active = active_version(candidate_registry)
    versions = candidate_registry.get("versions", [])
    recommended_action = skill_update_plan.get("recommended_action")

    if not versions:
        add_finding(findings, "error", "missing_candidate_versions", "Candidate registry must contain at least one version.")
    if not candidate_registry.get("active_version_id"):
        add_finding(findings, "error", "missing_active_version_id", "Candidate registry must name the active candidate version.")
    if not active:
        add_finding(findings, "error", "active_version_not_found", "Active candidate version is not present in candidate registry.")
    if draft_candidates.get("candidate_count", 0) != 1:
        add_finding(findings, "error", "unexpected_candidate_count", "paper2skills must keep one child-skill candidate per package.")
    if candidate_selection_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_selection_not_passed", "Active candidate cannot be promoted until selection audit passes.")
    if candidate_selection_audit.get("selected_version_id") != candidate_registry.get("active_version_id"):
        add_finding(findings, "error", "candidate_selection_mismatch", "Promotion target must match the selected candidate version.")
    if active.get("candidate_id") != candidate_selection_audit.get("selected_candidate_id"):
        add_finding(findings, "error", "candidate_selection_candidate_mismatch", "Selected candidate id must match the active version candidate id.")

    active_files = set(active.get("files", []))
    missing_files = sorted(set(REQUIRED_CANDIDATE_FILES).difference(active_files))
    if missing_files:
        add_finding(findings, "error", "active_candidate_missing_files", "Active candidate is missing required child-skill files.")
    if active.get("status") != publish_gate.get("status"):
        add_finding(findings, "error", "candidate_gate_status_mismatch", "Active candidate status must mirror publish_gate status.")
    if active.get("review_status") != "passed":
        add_finding(findings, "error", "candidate_review_not_passed", "Active candidate cannot be promoted until review passes.")
    if active.get("lint_status") != "pass":
        add_finding(findings, "error", "candidate_lint_not_passed", "Active candidate cannot be promoted until lint passes.")
    if publish_gate.get("status") == "publishable" and active.get("blocking_findings"):
        add_finding(findings, "error", "publishable_candidate_has_blockers", "Publishable candidate must not retain blocking findings.")
    if not is_publish_status_acceptable(recommended_action, publish_gate.get("status")):
        add_finding(findings, "error", "candidate_publish_status_invalid", "Active candidate status must match the action-specific publish status.")
    if recommended_action == REUSE_EXISTING and publish_gate.get("status") == "publishable":
        add_finding(findings, "error", "reuse_candidate_marked_publishable", "Reuse recommendations must not promote a duplicate candidate.")
    if recommended_action == UPDATE_EXISTING and not skill_update_plan.get("target_existing_skill_path"):
        add_finding(findings, "error", "update_candidate_missing_target", "Update promotion requires a target existing skill path.")
    if recommended_action == REUSE_EXISTING and not skill_update_plan.get("target_existing_skill_path"):
        add_finding(findings, "error", "reuse_candidate_missing_target", "Reuse action requires the target existing skill path.")

    promoted = (
        recommended_action != REUSE_EXISTING
        and publish_gate.get("status") == "publishable"
        and candidate_selection_audit.get("status") == "pass"
        and not any(finding["severity"] == "error" for finding in findings)
    )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "candidate_count": draft_candidates.get("candidate_count", 0),
        "active_version_id": candidate_registry.get("active_version_id"),
        "active_candidate_status": active.get("status"),
        "candidate_selection_audit_status": candidate_selection_audit.get("status"),
        "selected_candidate_id": candidate_selection_audit.get("selected_candidate_id"),
        "publish_gate_status": publish_gate.get("status"),
        "skill_update_recommended_action": recommended_action,
        "promoted_to_release": promoted,
        "required_files": REQUIRED_CANDIDATE_FILES,
        "active_files": sorted(active_files),
        "findings": findings,
        "policy": [
            "Candidate promotion is manifest-only; it does not copy or install a skill.",
            "Candidate promotion requires a passed selection audit before release packaging.",
            "One package should have one active child-skill candidate before release packaging.",
            "Reuse recommendations pass as a no-copy action and must not promote a duplicate candidate as publishable.",
        ],
    }
