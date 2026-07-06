"""Cross-stage protocol compliance audit for paper2skills builds."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PLAN_ONLY_ARTIFACTS = [
    "discovery_resolution_audit",
    "environment_install_plan",
    "execution_plan",
    "tutorial_reproduction_plan",
    "execution_replay_orchestrator",
    "skill_update_plan",
    "skill_update_audit",
    "forward_test_plan",
    "agent_rollout_harness",
    "agent_rollout_audit",
    "e2e_acceptance",
    "smoke_test_plan",
    "acceptance_handoff",
]


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


def status_of(artifacts: dict[str, dict[str, Any]], name: str) -> Any:
    return (artifacts.get(name) or {}).get("status")


def plan_only_record(
    artifacts: dict[str, dict[str, Any]],
    name: str,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    artifact = artifacts.get(name) or {}
    present = bool(artifact)
    plan_only = artifact.get("plan_only")
    passed = present and plan_only is True
    if not present:
        add_finding(findings, "error", "protocol_artifact_missing", "Required protocol artifact is missing.", name)
    elif plan_only is not True:
        add_finding(findings, "error", "protocol_artifact_not_plan_only", "Protocol artifact must remain plan-only.", name)
    return {
        "artifact": name,
        "present": present,
        "status": artifact.get("status"),
        "plan_only": plan_only,
        "passed": passed,
    }


def all_phases_completed(phase_state: dict[str, Any]) -> bool:
    phases = phase_state.get("phases", [])
    return bool(phases) and all(str(phase.get("status")) in {"completed", "skipped"} for phase in phases)


def build_protocol_compliance_audit(
    request: dict[str, Any],
    phase_state: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Audit cross-stage protocol boundaries without replacing focused gates."""
    findings: list[dict[str, Any]] = []
    plan_only_records = [plan_only_record(artifacts, name, findings) for name in PLAN_ONLY_ARTIFACTS]

    phase_state_audit = artifacts.get("phase_state_audit") or {}
    if phase_state_audit.get("status") != "pass":
        add_finding(findings, "error", "phase_state_audit_failed", "Phase-state audit must pass for protocol compliance.", "phase_state_audit")
    if not all_phases_completed(phase_state):
        add_finding(findings, "error", "phase_state_not_completed", "All recorded phases must be completed or skipped.", "phase_state")

    request_fingerprint = artifacts.get("request_fingerprint") or {}
    if request_fingerprint.get("stores_raw_request") is not False:
        add_finding(findings, "error", "request_fingerprint_stores_raw_request", "Request fingerprint must not store raw request values.", "request_fingerprint")

    external_result_contracts = artifacts.get("external_result_contracts") or {}
    if external_result_contracts.get("status") != "pass":
        add_finding(findings, "error", "external_result_contracts_failed", "External result evidence contract audit must pass.", "external_result_contracts")

    output_boundary_audit = artifacts.get("output_boundary_audit") or {}
    if output_boundary_audit.get("status") != "pass":
        add_finding(findings, "error", "output_boundary_audit_failed", "Output boundary audit must pass.", "output_boundary_audit")
    if output_boundary_audit.get("output_dir_inside_install_root"):
        add_finding(findings, "error", "output_dir_inside_install_root", "Build output directory must not be inside a likely skill install root.", "output_boundary_audit")

    skill_update_plan = artifacts.get("skill_update_plan") or {}
    skill_update_audit = artifacts.get("skill_update_audit") or {}
    codex_publish_adapter = artifacts.get("codex_publish_adapter") or {}
    action = str(skill_update_plan.get("recommended_action") or "")
    if action in {"update_existing", "reuse_existing"} and skill_update_plan.get("manual_review_required") is not True:
        add_finding(findings, "error", "manual_review_missing_for_existing_skill_action", "Update and reuse actions require manual review awareness.", "skill_update_plan")
    if action == "update_existing" and not skill_update_audit.get("target_existing_skill_path"):
        add_finding(findings, "error", "update_missing_target_existing_skill", "Update action requires a target existing skill path.", "skill_update_audit")
    if codex_publish_adapter and codex_publish_adapter.get("target_agent") != "codex":
        add_finding(findings, "error", "codex_publish_adapter_wrong_target", "Publish adapter must target Codex.", "codex_publish_adapter")

    verification_claim_audit = artifacts.get("verification_claim_audit") or {}
    if verification_claim_audit.get("status") != "pass":
        add_finding(findings, "error", "verification_claim_audit_failed", "Verification claim audit must pass.", "verification_claim_audit")
    if verification_claim_audit.get("valid_success_count", 0) == 0:
        for task in verification_claim_audit.get("tasks", []):
            if task.get("verification_status") == "execution_verified":
                add_finding(findings, "error", "execution_verified_without_success_evidence", "execution_verified claims require successful execution evidence.", "verification_claim_audit")

    completion_evidence_audit = artifacts.get("completion_evidence_audit") or {}
    if completion_evidence_audit.get("can_claim_full_goal_complete"):
        if int(completion_evidence_audit.get("agent_rollout_result_count") or 0) == 0:
            add_finding(findings, "error", "full_completion_without_rollout_results", "Full completion requires supplied agent rollout results.", "completion_evidence_audit")
        if int(completion_evidence_audit.get("e2e_result_count") or 0) == 0:
            add_finding(findings, "error", "full_completion_without_e2e_results", "Full completion requires supplied E2E results.", "completion_evidence_audit")
        if request.get("execution_grounded") and int(completion_evidence_audit.get("successful_execution_evidence_count") or 0) == 0:
            add_finding(findings, "error", "full_completion_without_execution_evidence", "Execution-grounded full completion requires successful execution evidence.", "completion_evidence_audit")

    protocol_records = [
        {
            "protocol": "phase_state",
            "artifact": "phase_state",
            "passed": all_phases_completed(phase_state) and phase_state_audit.get("status") == "pass",
        },
        {
            "protocol": "request_privacy",
            "artifact": "request_fingerprint",
            "passed": request_fingerprint.get("stores_raw_request") is False,
        },
        {
            "protocol": "external_results",
            "artifact": "external_result_contracts",
            "passed": external_result_contracts.get("status") == "pass",
        },
        {
            "protocol": "output_boundary",
            "artifact": "output_boundary_audit",
            "passed": output_boundary_audit.get("status") == "pass" and not output_boundary_audit.get("output_dir_inside_install_root"),
        },
        {
            "protocol": "verification_claims",
            "artifact": "verification_claim_audit",
            "passed": verification_claim_audit.get("status") == "pass",
        },
        {
            "protocol": "completion_evidence",
            "artifact": "completion_evidence_audit",
            "passed": completion_evidence_audit.get("status") == "pass",
        },
    ]
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only_artifact_count": len(plan_only_records),
        "plan_only_pass_count": sum(1 for record in plan_only_records if record["passed"]),
        "protocol_record_count": len(protocol_records),
        "protocol_pass_count": sum(1 for record in protocol_records if record["passed"]),
        "plan_only_records": plan_only_records,
        "protocol_records": protocol_records,
        "findings": findings,
        "policy": [
            "Protocol compliance is a cross-stage static audit.",
            "Plan-only artifacts must not execute package code, launch agents, install environments, copy skills, or mutate existing skills.",
            "External rollout, replay, and E2E results only count when supplied through the build request and audited by result judges.",
            "Publish and install actions remain manifest or manual-plan artifacts until a user explicitly performs them outside the builder run.",
        ],
    }
