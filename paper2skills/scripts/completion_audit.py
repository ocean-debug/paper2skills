"""Final completion audit for a Papert2Skills build run."""

from __future__ import annotations

from typing import Any

from action_policy import expected_install_statuses, expected_publish_statuses
from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_COMPLETION_PHASES = [
    "request",
    "request_fingerprint",
    "external_result_contracts",
    "phase_state_audit",
    "builder_runtime_audit",
    "agent_metadata_audit",
    "public_origin_audit",
    "module_inventory_audit",
    "builder_baseline_audit",
    "skill_package_audit",
    "request_template_audit",
    "builder_version_audit",
    "discovery_preflight",
    "discovery_match_audit",
    "discovery_resolution_audit",
    "source_grounding",
    "source_fetch_boundary_audit",
    "source_ingestion_audit",
    "source_grounding_audit",
    "key_api_coverage_audit",
    "source_index",
    "resource_inventory",
    "source_parsing_coverage",
    "source_parsing_audit",
    "backend_extension_audit",
    "task_partition",
    "task_partition_decision_log",
    "task_partition_audit",
    "self_review",
    "review_iteration_log",
    "review_remediation_audit",
    "review_prompt_contracts",
    "review_prompt_materials",
    "review_optimizer_state",
    "review_prompt_suite_audit",
    "patch_safety_audit",
    "patch_operation_contracts",
    "review_trajectory_audit",
    "rubric_grounding_audit",
    "tutorial_reproduction_plan",
    "verification_claim_audit",
    "resource_boundary_audit",
    "biological_claim_boundary_audit",
    "contract_traceability",
    "acceptance_suite",
    "skill_draft",
    "child_metadata_audit",
    "child_package_purity_audit",
    "lint",
    "skill_update_audit",
    "requirement_coverage",
    "completion_evidence_audit",
    "acceptance_handoff",
    "architecture_completeness_audit",
    "agent_rollout_harness",
    "agent_rollout_audit",
    "eval_leakage_audit",
    "agent_rollout_result_judge",
    "e2e_acceptance",
    "smoke_test_plan",
    "routing_metadata_audit",
    "artifact_validation",
    "artifact_closure_audit",
    "publish_gate",
    "candidate_selection_audit",
    "candidate_promotion_audit",
    "final_candidate_audit",
    "candidate_evolution_audit",
    "quality_report",
    "score_report",
    "release_package",
    "release_action_audit",
    "codex_publish_adapter",
    "install_readiness",
    "publish_manifest",
    "publish_manifest_audit",
    "protocol_compliance_audit",
    "completion_audit",
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


def status_record(name: str, artifact: dict[str, Any], expected: str | set[str]) -> dict[str, Any]:
    expected_set = {expected} if isinstance(expected, str) else expected
    status = artifact.get("status")
    return {
        "artifact": name,
        "status": status,
        "expected": sorted(expected_set),
        "passed": status in expected_set,
        "finding_count": len(artifact.get("findings", [])),
    }


def build_completion_audit(
    request: dict[str, Any],
    phase_state: dict[str, Any],
    builder_runtime_audit: dict[str, Any],
    agent_metadata_audit: dict[str, Any],
    public_origin_audit: dict[str, Any],
    module_inventory_audit: dict[str, Any],
    builder_baseline_audit: dict[str, Any],
    skill_package_audit: dict[str, Any],
    request_template_audit: dict[str, Any],
    builder_version_audit: dict[str, Any],
    request_audit: dict[str, Any],
    request_fingerprint: dict[str, Any],
    external_result_contracts: dict[str, Any],
    phase_state_audit: dict[str, Any],
    protocol_compliance_audit: dict[str, Any],
    requirement_coverage: dict[str, Any],
    completion_evidence_audit: dict[str, Any],
    acceptance_handoff: dict[str, Any],
    architecture_completeness_audit: dict[str, Any],
    artifact_validation: dict[str, Any],
    publish_gate: dict[str, Any],
    quality_report: dict[str, Any],
    score_report: dict[str, Any],
    release_package: dict[str, Any],
    install_readiness: dict[str, Any],
    publish_manifest: dict[str, Any],
    publish_manifest_audit: dict[str, Any],
    skill_update_plan: dict[str, Any],
    skill_update_audit: dict[str, Any] | None = None,
    discovery_match_audit: dict[str, Any] | None = None,
    discovery_resolution_audit: dict[str, Any] | None = None,
    review_optimizer_state: dict[str, Any] | None = None,
    patch_safety_audit: dict[str, Any] | None = None,
    patch_operation_contracts: dict[str, Any] | None = None,
    candidate_selection_audit: dict[str, Any] | None = None,
    candidate_promotion_audit: dict[str, Any] | None = None,
    final_candidate_audit: dict[str, Any] | None = None,
    candidate_evolution_audit: dict[str, Any] | None = None,
    artifact_closure_audit: dict[str, Any] | None = None,
    source_fetch_boundary_audit: dict[str, Any] | None = None,
    source_ingestion_audit: dict[str, Any] | None = None,
    source_grounding_audit: dict[str, Any] | None = None,
    key_api_coverage_audit: dict[str, Any] | None = None,
    verification_claim_audit: dict[str, Any] | None = None,
    execution_replay_orchestrator: dict[str, Any] | None = None,
    backend_extension_audit: dict[str, Any] | None = None,
    resource_boundary_audit: dict[str, Any] | None = None,
    evidence_claim_taxonomy_audit: dict[str, Any] | None = None,
    child_metadata_audit: dict[str, Any] | None = None,
    child_package_purity_audit: dict[str, Any] | None = None,
    biological_claim_boundary_audit: dict[str, Any] | None = None,
    review_prompt_contracts: dict[str, Any] | None = None,
    review_prompt_materials: dict[str, Any] | None = None,
    review_prompt_suite_audit: dict[str, Any] | None = None,
    review_iteration_log: dict[str, Any] | None = None,
    review_remediation_audit: dict[str, Any] | None = None,
    review_trajectory_audit: dict[str, Any] | None = None,
    agent_rollout_harness: dict[str, Any] | None = None,
    agent_rollout_audit: dict[str, Any] | None = None,
    eval_leakage_audit: dict[str, Any] | None = None,
    agent_rollout_result_judge: dict[str, Any] | None = None,
    e2e_acceptance: dict[str, Any] | None = None,
    smoke_test_plan: dict[str, Any] | None = None,
    routing_metadata_audit: dict[str, Any] | None = None,
    codex_publish_adapter: dict[str, Any] | None = None,
    release_action_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate the final semantic gates into one run-level verdict."""
    findings: list[dict[str, Any]] = []
    update_action = skill_update_plan.get("recommended_action")
    publish_statuses = expected_publish_statuses(update_action)
    install_statuses = expected_install_statuses(update_action)
    checks = [
        status_record("builder_runtime_audit", builder_runtime_audit, "pass"),
        status_record("agent_metadata_audit", agent_metadata_audit, "pass"),
        status_record("public_origin_audit", public_origin_audit, "pass"),
        status_record("module_inventory_audit", module_inventory_audit, "pass"),
        status_record("builder_baseline_audit", builder_baseline_audit, "pass"),
        status_record("skill_package_audit", skill_package_audit, "pass"),
        status_record("request_template_audit", request_template_audit, "pass"),
        status_record("builder_version_audit", builder_version_audit, "pass"),
        status_record("request_audit", request_audit, "pass"),
        status_record("request_fingerprint", request_fingerprint, "pass"),
        status_record("external_result_contracts", external_result_contracts, "pass"),
        status_record("phase_state_audit", phase_state_audit, "pass"),
        status_record("protocol_compliance_audit", protocol_compliance_audit, "pass"),
        status_record("requirement_coverage", requirement_coverage, "pass"),
        status_record("completion_evidence_audit", completion_evidence_audit, "pass"),
        status_record("acceptance_handoff", acceptance_handoff, "pass"),
        status_record("architecture_completeness_audit", architecture_completeness_audit, "pass"),
        status_record("artifact_validation", artifact_validation, "pass"),
        status_record("publish_gate", publish_gate, publish_statuses),
        status_record("quality_report", quality_report, "pass"),
        status_record("score_report", score_report, "pass"),
        status_record("release_package", release_package, "ready"),
        status_record("release_action_audit", release_action_audit or {}, "pass"),
        status_record("install_readiness", install_readiness, install_statuses),
        status_record("publish_manifest", publish_manifest, publish_statuses.union({"ready"})),
        status_record("publish_manifest_audit", publish_manifest_audit, "pass"),
        status_record("skill_update_plan", skill_update_plan, "pass"),
    ]
    if skill_update_audit is not None:
        checks.append(status_record("skill_update_audit", skill_update_audit, "pass"))
    if discovery_match_audit is not None:
        checks.append(status_record("discovery_match_audit", discovery_match_audit, "pass"))
    if discovery_resolution_audit is not None:
        checks.append(status_record("discovery_resolution_audit", discovery_resolution_audit, "pass"))
    if review_optimizer_state is not None:
        checks.append(status_record("review_optimizer_state", review_optimizer_state, "pass"))
    if patch_safety_audit is not None:
        checks.append(status_record("patch_safety_audit", patch_safety_audit, "pass"))
    if patch_operation_contracts is not None:
        checks.append(status_record("patch_operation_contracts", patch_operation_contracts, "pass"))
    if candidate_selection_audit is not None:
        checks.append(status_record("candidate_selection_audit", candidate_selection_audit, "pass"))
    if candidate_promotion_audit is not None:
        checks.append(status_record("candidate_promotion_audit", candidate_promotion_audit, "pass"))
    if final_candidate_audit is not None:
        checks.append(status_record("final_candidate_audit", final_candidate_audit, "pass"))
    if candidate_evolution_audit is not None:
        checks.append(status_record("candidate_evolution_audit", candidate_evolution_audit, "pass"))
    if artifact_closure_audit is not None:
        checks.append(status_record("artifact_closure_audit", artifact_closure_audit, "pass"))
    if source_fetch_boundary_audit is not None:
        checks.append(status_record("source_fetch_boundary_audit", source_fetch_boundary_audit, "pass"))
    if source_ingestion_audit is not None:
        checks.append(status_record("source_ingestion_audit", source_ingestion_audit, "pass"))
    if source_grounding_audit is not None:
        checks.append(status_record("source_grounding_audit", source_grounding_audit, "pass"))
    if key_api_coverage_audit is not None:
        checks.append(status_record("key_api_coverage_audit", key_api_coverage_audit, "pass"))
    if verification_claim_audit is not None:
        checks.append(status_record("verification_claim_audit", verification_claim_audit, "pass"))
    if execution_replay_orchestrator is not None:
        checks.append(status_record("execution_replay_orchestrator", execution_replay_orchestrator, "pass"))
    if backend_extension_audit is not None:
        checks.append(status_record("backend_extension_audit", backend_extension_audit, "pass"))
    if resource_boundary_audit is not None:
        checks.append(status_record("resource_boundary_audit", resource_boundary_audit, "pass"))
    if evidence_claim_taxonomy_audit is not None:
        checks.append(status_record("evidence_claim_taxonomy_audit", evidence_claim_taxonomy_audit, "pass"))
    if child_metadata_audit is not None:
        checks.append(status_record("child_metadata_audit", child_metadata_audit, "pass"))
    if child_package_purity_audit is not None:
        checks.append(status_record("child_package_purity_audit", child_package_purity_audit, "pass"))
    if biological_claim_boundary_audit is not None:
        checks.append(status_record("biological_claim_boundary_audit", biological_claim_boundary_audit, "pass"))
    if review_prompt_contracts is not None:
        checks.append(status_record("review_prompt_contracts", review_prompt_contracts, "pass"))
    if review_prompt_materials is not None:
        checks.append(status_record("review_prompt_materials", review_prompt_materials, "pass"))
    if review_prompt_suite_audit is not None:
        checks.append(status_record("review_prompt_suite_audit", review_prompt_suite_audit, "pass"))
    if review_iteration_log is not None:
        checks.append(status_record("review_iteration_log", review_iteration_log, "pass"))
    if review_remediation_audit is not None:
        checks.append(status_record("review_remediation_audit", review_remediation_audit, "pass"))
    if review_trajectory_audit is not None:
        checks.append(status_record("review_trajectory_audit", review_trajectory_audit, "pass"))
    if agent_rollout_harness is not None:
        checks.append(status_record("agent_rollout_harness", agent_rollout_harness, "pass"))
    if agent_rollout_audit is not None:
        checks.append(status_record("agent_rollout_audit", agent_rollout_audit, "pass"))
    if eval_leakage_audit is not None:
        checks.append(status_record("eval_leakage_audit", eval_leakage_audit, "pass"))
    if agent_rollout_result_judge is not None:
        checks.append(status_record("agent_rollout_result_judge", agent_rollout_result_judge, {"pass", "not_run"}))
    if e2e_acceptance is not None:
        checks.append(status_record("e2e_acceptance", e2e_acceptance, "pass"))
    if smoke_test_plan is not None:
        checks.append(status_record("smoke_test_plan", smoke_test_plan, "pass"))
    if routing_metadata_audit is not None:
        checks.append(status_record("routing_metadata_audit", routing_metadata_audit, "pass"))
    if codex_publish_adapter is not None:
        checks.append(status_record("codex_publish_adapter", codex_publish_adapter, "pass"))
    for check in checks:
        if not check["passed"]:
            add_finding(
                findings,
                "error",
                "completion_gate_failed",
                f"{check['artifact']} status is {check['status']}; expected one of {', '.join(check['expected'])}.",
                check["artifact"],
            )

    phase_names = [str(phase.get("name")) for phase in phase_state.get("phases", [])]
    missing_phases = sorted(phase for phase in REQUIRED_COMPLETION_PHASES if phase not in phase_names)
    if missing_phases:
        add_finding(
            findings,
            "error",
            "missing_completion_phase",
            "Phase ledger is missing required completion phases.",
            "phase_state",
        )
    failed_phases = [
        str(phase.get("name"))
        for phase in phase_state.get("phases", [])
        if str(phase.get("status")) not in {"completed", "skipped"}
    ]
    if failed_phases:
        add_finding(
            findings,
            "error",
            "phase_not_completed",
            "One or more phases are not marked completed or skipped.",
            "phase_state",
        )

    discovery_decision = publish_manifest.get("discovery_decision")
    release_action = release_package.get("recommended_action")
    manifest_action = publish_manifest.get("recommended_action")
    if release_action != update_action:
        add_finding(
            findings,
            "error",
            "release_action_mismatch",
            "Release package action must match skill update plan action.",
            "release_package",
        )
    if manifest_action != publish_gate.get("recommended_action"):
        add_finding(
            findings,
            "error",
            "manifest_action_mismatch",
            "Publish manifest action must match publish gate action.",
            "publish_manifest",
        )
    if discovery_decision == "reuse" and update_action != "reuse_existing":
        add_finding(
            findings,
            "error",
            "reuse_decision_action_mismatch",
            "Discovery reuse decision must map to reuse_existing.",
            "skill_update_plan",
        )
    if discovery_decision == "update" and update_action != "update_existing":
        add_finding(
            findings,
            "error",
            "update_decision_action_mismatch",
            "Discovery update decision must map to update_existing.",
            "skill_update_plan",
        )
    if discovery_decision == "create" and update_action != "create_new":
        add_finding(
            findings,
            "error",
            "create_decision_action_mismatch",
            "Discovery create decision must map to create_new.",
            "skill_update_plan",
        )
    if not publish_manifest.get("run_manifest_path"):
        add_finding(
            findings,
            "error",
            "missing_run_manifest_path",
            "Publish manifest must point to the final run manifest.",
            "publish_manifest",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "recommended_action": update_action,
        "discovery_decision": discovery_decision,
        "builder_runtime_audit_status": builder_runtime_audit.get("status"),
        "agent_metadata_audit_status": agent_metadata_audit.get("status"),
        "public_origin_audit_status": public_origin_audit.get("status"),
        "module_inventory_audit_status": module_inventory_audit.get("status"),
        "builder_baseline_audit_status": builder_baseline_audit.get("status"),
        "skill_package_audit_status": skill_package_audit.get("status"),
        "request_template_audit_status": request_template_audit.get("status"),
        "builder_version_audit_status": builder_version_audit.get("status"),
        "request_fingerprint_status": request_fingerprint.get("status"),
        "external_result_contracts_status": external_result_contracts.get("status"),
        "phase_state_audit_status": phase_state_audit.get("status"),
        "protocol_compliance_audit_status": protocol_compliance_audit.get("status"),
        "completion_evidence_audit_status": completion_evidence_audit.get("status"),
        "acceptance_handoff_status": acceptance_handoff.get("status"),
        "can_claim_full_goal_complete": completion_evidence_audit.get("can_claim_full_goal_complete"),
        "completion_claim_verdict": completion_evidence_audit.get("claim_verdict"),
        "publish_gate_status": publish_gate.get("status"),
        "quality_status": quality_report.get("status"),
        "score_report_status": score_report.get("status"),
        "agent_rollout_audit_status": (agent_rollout_audit or {}).get("status"),
        "eval_leakage_audit_status": (eval_leakage_audit or {}).get("status"),
        "agent_rollout_result_judge_status": (agent_rollout_result_judge or {}).get("status"),
        "e2e_acceptance_status": (e2e_acceptance or {}).get("status"),
        "e2e_verdict": (e2e_acceptance or {}).get("e2e_verdict"),
        "smoke_test_plan_status": (smoke_test_plan or {}).get("status"),
        "smoke_verdict": (smoke_test_plan or {}).get("smoke_verdict"),
        "install_readiness_status": install_readiness.get("status"),
        "release_action_audit_status": (release_action_audit or {}).get("status"),
        "candidate_evolution_audit_status": (candidate_evolution_audit or {}).get("status"),
        "artifact_closure_audit_status": (artifact_closure_audit or {}).get("status"),
        "source_fetch_boundary_audit_status": (source_fetch_boundary_audit or {}).get("status"),
        "skill_update_audit_status": (skill_update_audit or {}).get("status"),
        "discovery_match_audit_status": (discovery_match_audit or {}).get("status"),
        "discovery_resolution_audit_status": (discovery_resolution_audit or {}).get("status"),
        "source_ingestion_audit_status": (source_ingestion_audit or {}).get("status"),
        "key_api_coverage_audit_status": (key_api_coverage_audit or {}).get("status"),
        "verification_claim_audit_status": (verification_claim_audit or {}).get("status"),
        "execution_replay_orchestrator_status": (execution_replay_orchestrator or {}).get("status"),
        "backend_extension_audit_status": (backend_extension_audit or {}).get("status"),
        "resource_boundary_audit_status": (resource_boundary_audit or {}).get("status"),
        "evidence_claim_taxonomy_audit_status": (evidence_claim_taxonomy_audit or {}).get("status"),
        "child_metadata_audit_status": (child_metadata_audit or {}).get("status"),
        "child_package_purity_audit_status": (child_package_purity_audit or {}).get("status"),
        "biological_claim_boundary_audit_status": (biological_claim_boundary_audit or {}).get("status"),
        "review_prompt_materials_status": (review_prompt_materials or {}).get("status"),
        "review_prompt_suite_audit_status": (review_prompt_suite_audit or {}).get("status"),
        "review_remediation_audit_status": (review_remediation_audit or {}).get("status"),
        "patch_operation_contracts_status": (patch_operation_contracts or {}).get("status"),
        "publish_manifest_audit_status": publish_manifest_audit.get("status"),
        "run_manifest_path": publish_manifest.get("run_manifest_path"),
        "run_manifest_planned": bool(publish_manifest.get("run_manifest_path")),
        "phase_count": len(phase_state.get("phases", [])),
        "missing_phases": missing_phases,
        "failed_phases": failed_phases,
        "checks": checks,
        "findings": findings,
        "policy": [
            "Completion audit is the final semantic verdict for the build run.",
            "Run manifest hashing is written after this audit and should be verified with verify-run-manifest.",
            "Completion requires builder runtime, agent metadata, public origin, module inventory, builder baseline, skill package shape, request template, builder version, request, request fingerprint, external result contracts, phase state, discovery match, source ingestion, source grounding, verification claim, resource boundaries, child metadata, child package purity, biological claim boundaries, requirement, completion evidence, acceptance handoff, architecture completeness, smoke test planning, artifact validation, artifact closure, skill update audit, review prompt contracts, review iteration log, agent rollout harness, routing metadata, review optimizer, patch safety, review trajectory, candidate selection, candidate promotion, final candidate, candidate evolution, publish, quality, score report, release, Codex publish adapter, install, and manifest gates to agree under the selected create/update/reuse action.",
            "can_claim_full_goal_complete is stricter than build completion and requires explicit external validation evidence.",
        ],
    }
