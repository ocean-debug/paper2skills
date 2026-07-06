"""Audit final create, update, or reuse release-action semantics."""

from __future__ import annotations

from typing import Any

from action_policy import (
    CREATE_NEW,
    REUSE_EXISTING,
    UPDATE_EXISTING,
    VALID_ACTIONS,
    expected_install_statuses,
    expected_publish_statuses,
)
from common import now_utc, public_existing_skill_path
from constants import SCHEMA_VERSION


EXPECTED_STEP_BY_ACTION = {
    CREATE_NEW: "copy_child_skill_directory",
    UPDATE_EXISTING: "review_manual_merge",
    REUSE_EXISTING: "reuse_existing_skill",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    artifact: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if artifact:
        finding["artifact"] = artifact
    findings.append(finding)


def publish_steps(codex_publish_adapter: dict[str, Any]) -> set[str]:
    return {
        str(step.get("step"))
        for step in codex_publish_adapter.get("publish_steps", [])
        if step.get("step")
    }


def build_release_action_audit(
    request: dict[str, Any],
    skill_update_plan: dict[str, Any],
    skill_update_audit: dict[str, Any],
    publish_gate: dict[str, Any],
    release_package: dict[str, Any],
    candidate_promotion_audit: dict[str, Any],
    final_candidate_audit: dict[str, Any],
    install_readiness: dict[str, Any],
    codex_publish_adapter: dict[str, Any],
    publish_manifest: dict[str, Any],
    publish_manifest_audit: dict[str, Any],
) -> dict[str, Any]:
    """Check that release artifacts agree on the selected action."""
    findings: list[dict[str, Any]] = []
    action = str(skill_update_plan.get("recommended_action") or "")
    expected_publish = expected_publish_statuses(action)
    expected_install = expected_install_statuses(action)
    expected_step = EXPECTED_STEP_BY_ACTION.get(action)
    steps = publish_steps(codex_publish_adapter)

    if action not in VALID_ACTIONS:
        add_finding(findings, "error", "invalid_release_action", "Unknown skill update recommended_action.", "skill_update_plan")
    if skill_update_plan.get("status") != "pass":
        add_finding(findings, "error", "skill_update_plan_failed", "Skill update plan must pass before release action audit.", "skill_update_plan")
    if skill_update_audit.get("status") != "pass":
        add_finding(findings, "error", "skill_update_audit_failed", "Skill update audit must pass before release action audit.", "skill_update_audit")
    if skill_update_audit.get("plan_only") is not True:
        add_finding(findings, "error", "skill_update_audit_not_plan_only", "Skill update audit must remain plan-only.", "skill_update_audit")
    if release_package.get("recommended_action") != action:
        add_finding(findings, "error", "release_action_mismatch", "Release package action must match skill update plan.", "release_package")
    if publish_gate.get("recommended_action") != action:
        add_finding(findings, "error", "publish_gate_action_mismatch", "Publish gate action must match skill update plan.", "publish_gate")
    if codex_publish_adapter.get("recommended_action") != action:
        add_finding(findings, "error", "adapter_action_mismatch", "Codex publish adapter action must match skill update plan.", "codex_publish_adapter")
    if publish_manifest.get("recommended_action") != action:
        add_finding(findings, "error", "manifest_action_mismatch", "Publish manifest action must match skill update plan.", "publish_manifest")
    if publish_manifest.get("release_recommended_action") != action:
        add_finding(findings, "error", "manifest_release_action_mismatch", "Publish manifest release action must match skill update plan.", "publish_manifest")

    if str(publish_gate.get("status")) not in expected_publish:
        add_finding(findings, "error", "publish_status_invalid", "Publish gate status does not match the selected action.", "publish_gate")
    if str(install_readiness.get("status")) not in expected_install:
        add_finding(findings, "error", "install_status_invalid", "Install readiness status does not match the selected action.", "install_readiness")
    if release_package.get("status") != "ready":
        add_finding(findings, "error", "release_package_not_ready", "Release package must be ready for the selected action.", "release_package")
    if candidate_promotion_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_promotion_failed", "Candidate promotion audit must pass for the selected action.", "candidate_promotion_audit")
    if final_candidate_audit.get("status") != "pass":
        add_finding(findings, "error", "final_candidate_failed", "Final candidate audit must pass for the selected action.", "final_candidate_audit")
    if codex_publish_adapter.get("status") != "pass":
        add_finding(findings, "error", "codex_publish_adapter_failed", "Codex publish adapter must pass for the selected action.", "codex_publish_adapter")
    if publish_manifest_audit.get("status") != "pass":
        add_finding(findings, "error", "publish_manifest_audit_failed", "Publish manifest audit must pass for the selected action.", "publish_manifest_audit")
    if codex_publish_adapter.get("plan_only") is not True:
        add_finding(findings, "error", "adapter_not_plan_only", "Codex publish adapter must remain plan-only.", "codex_publish_adapter")
    if expected_step and expected_step not in steps:
        add_finding(findings, "error", "missing_action_publish_step", "Codex publish adapter is missing the expected action step.", "codex_publish_adapter")

    target_path = release_package.get("target_existing_skill_path") or public_existing_skill_path(skill_update_plan.get("target_existing_skill_path"))
    if action in {UPDATE_EXISTING, REUSE_EXISTING} and not target_path:
        add_finding(findings, "error", "missing_existing_skill_target", "Update and reuse actions require a target existing skill path.", "release_package")
    if action == REUSE_EXISTING:
        if candidate_promotion_audit.get("promoted_to_release") is True:
            add_finding(findings, "error", "reuse_promoted_duplicate", "Reuse must not promote a generated duplicate child skill.", "candidate_promotion_audit")
        if final_candidate_audit.get("finalized_for_release") is True:
            add_finding(findings, "error", "reuse_finalized_duplicate", "Reuse must not finalize a generated duplicate child skill.", "final_candidate_audit")
        if publish_manifest.get("status") == "publishable":
            add_finding(findings, "error", "reuse_manifest_publishable", "Reuse must not mark the generated candidate as publishable.", "publish_manifest")
    elif action in {CREATE_NEW, UPDATE_EXISTING}:
        if candidate_promotion_audit.get("promoted_to_release") is not True:
            add_finding(findings, "error", "copyable_action_not_promoted", "Create and update actions require a promoted generated candidate.", "candidate_promotion_audit")
        if final_candidate_audit.get("finalized_for_release") is not True:
            add_finding(findings, "error", "copyable_action_not_finalized", "Create and update actions require final_candidate finalized_for_release=true.", "final_candidate_audit")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "recommended_action": action,
        "expected_publish_statuses": sorted(expected_publish),
        "expected_install_statuses": sorted(expected_install),
        "publish_gate_status": publish_gate.get("status"),
        "skill_update_audit_status": skill_update_audit.get("status"),
        "release_package_status": release_package.get("status"),
        "install_readiness_status": install_readiness.get("status"),
        "codex_publish_adapter_status": codex_publish_adapter.get("status"),
        "publish_manifest_audit_status": publish_manifest_audit.get("status"),
        "target_existing_skill_path": target_path,
        "promoted_to_release": candidate_promotion_audit.get("promoted_to_release"),
        "finalized_for_release": final_candidate_audit.get("finalized_for_release"),
        "publish_steps": sorted(steps),
        "findings": findings,
        "policy": [
            "Release action audit is plan-only and does not copy, install, or mutate skills.",
            "Create and update actions require publishable generated candidates.",
            "Reuse actions require a no-copy reuse_ready decision and must not promote a duplicate generated candidate.",
            "All final release artifacts must agree on the selected create, update, or reuse action.",
        ],
    }
