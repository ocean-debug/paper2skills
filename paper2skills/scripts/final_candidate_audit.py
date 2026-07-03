"""Audit final candidate consistency before Codex publish planning."""

from __future__ import annotations

from typing import Any

from action_policy import REUSE_EXISTING, UPDATE_EXISTING, is_publish_status_acceptable
from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


REQUIRED_FILES = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]


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


def release_file_paths(release_package: dict[str, Any]) -> list[str]:
    return sorted(str(item.get("path")) for item in release_package.get("files", []) if item.get("path"))


def missing_release_files(release_package: dict[str, Any]) -> list[str]:
    missing = []
    records = {str(item.get("path")): item for item in release_package.get("files", []) if item.get("path")}
    for rel in REQUIRED_FILES:
        if not records.get(rel, {}).get("exists"):
            missing.append(rel)
    return missing


def build_final_candidate_audit(
    request: dict[str, Any],
    candidate_registry: dict[str, Any],
    candidate_selection_audit: dict[str, Any],
    candidate_promotion_audit: dict[str, Any],
    release_package: dict[str, Any],
    skill_update_plan: dict[str, Any],
    publish_gate: dict[str, Any],
) -> dict[str, Any]:
    """Check that release metadata points to the selected and promoted candidate."""
    findings: list[dict[str, Any]] = []
    active = active_version(candidate_registry)
    active_id = candidate_registry.get("active_version_id")
    release_candidate = release_package.get("candidate_version")
    recommended_action = skill_update_plan.get("recommended_action")
    release_action = release_package.get("recommended_action")
    active_files = sorted(str(path) for path in active.get("files", []))
    release_files = release_file_paths(release_package)
    missing_files = missing_release_files(release_package)

    if not active:
        add_finding(findings, "error", "active_candidate_missing", "Candidate registry must contain the active candidate version.")
    if active_id != candidate_selection_audit.get("selected_version_id"):
        add_finding(findings, "error", "selection_active_version_mismatch", "Candidate selection must point to the active registry version.")
    if active_id != candidate_promotion_audit.get("active_version_id"):
        add_finding(findings, "error", "promotion_active_version_mismatch", "Candidate promotion must point to the active registry version.")
    if active_id != release_candidate:
        add_finding(findings, "error", "release_candidate_mismatch", "Release package must point to the active candidate version.")
    if candidate_selection_audit.get("status") != "pass":
        add_finding(findings, "error", "selection_audit_failed", "Final candidate requires a passed selection audit.")
    if candidate_promotion_audit.get("status") != "pass":
        add_finding(findings, "error", "promotion_audit_failed", "Final candidate requires a passed promotion audit.")
    if publish_gate.get("status") != active.get("status"):
        add_finding(findings, "error", "active_status_mismatch", "Active candidate status must mirror publish_gate status.")
    if release_action != recommended_action:
        add_finding(findings, "error", "release_action_mismatch", "Release package action must mirror skill_update_plan recommended_action.")
    if not is_publish_status_acceptable(recommended_action, publish_gate.get("status")):
        add_finding(findings, "error", "final_publish_status_invalid", "Publish gate status must match the action-specific final candidate policy.")
    if recommended_action == REUSE_EXISTING and not release_package.get("target_existing_skill_path"):
        add_finding(findings, "error", "reuse_without_target", "Reuse final action requires target_existing_skill_path.")
    if recommended_action == UPDATE_EXISTING and not release_package.get("target_existing_skill_path"):
        add_finding(findings, "error", "update_without_target", "Final update candidate requires target_existing_skill_path.")
    if (
        recommended_action != REUSE_EXISTING
        and release_package.get("status") == "ready"
        and candidate_promotion_audit.get("promoted_to_release") is not True
    ):
        add_finding(findings, "error", "release_ready_without_promotion", "Ready release package must have promoted_to_release=true.")
    if missing_files:
        add_finding(findings, "error", "missing_release_files", "Release package is missing one or more required child-skill files.")
    if active_files and sorted(REQUIRED_FILES) != active_files:
        add_finding(findings, "error", "active_file_manifest_mismatch", "Active candidate file manifest must match required child-skill files.")
    if release_files and sorted(REQUIRED_FILES) != release_files:
        add_finding(findings, "error", "release_file_manifest_mismatch", "Release package file manifest must match required child-skill files.")
    if active.get("blocking_findings"):
        add_finding(findings, "error", "active_candidate_has_blockers", "Final candidate must not retain blocking publish findings.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    finalized = (
        not has_errors
        and recommended_action != REUSE_EXISTING
        and release_package.get("status") == "ready"
        and candidate_promotion_audit.get("promoted_to_release") is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "finalized_for_release": finalized,
        "active_version_id": active_id,
        "release_candidate_version": release_candidate,
        "selected_candidate_id": candidate_selection_audit.get("selected_candidate_id"),
        "candidate_selection_audit_status": candidate_selection_audit.get("status"),
        "candidate_promotion_audit_status": candidate_promotion_audit.get("status"),
        "publish_gate_status": publish_gate.get("status"),
        "release_package_status": release_package.get("status"),
        "recommended_action": recommended_action,
        "release_recommended_action": release_action,
        "required_files": REQUIRED_FILES,
        "active_files": active_files,
        "release_files": release_files,
        "missing_release_files": missing_files,
        "findings": findings,
        "policy": [
            "Final candidate audit is manifest-only; it does not copy, install, or mutate files.",
            "The release package must point to the active selected and promoted candidate.",
            "Reuse actions may pass consistency checks but must not finalize a duplicate child-skill release.",
            "The public child skill remains the only deployable artifact; build-run records stay outside it.",
        ],
    }
