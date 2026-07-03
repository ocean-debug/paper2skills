"""Final publish gate for generated child skills."""

from __future__ import annotations

from typing import Any

from action_policy import REUSE_EXISTING, normalize_action
from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        item["task_type"] = task_type
    findings.append(item)


def evaluate_publish_gate(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    discovery_audit: dict[str, Any],
    discovery_match_audit: dict[str, Any],
    discovery_resolution_audit: dict[str, Any],
    review_result: dict[str, Any],
    lint_report: dict[str, Any],
    child_metadata_audit: dict[str, Any],
    child_package_purity_audit: dict[str, Any],
    builder_runtime_audit: dict[str, Any],
    agent_metadata_audit: dict[str, Any],
    public_origin_audit: dict[str, Any],
    module_inventory_audit: dict[str, Any],
    builder_baseline_audit: dict[str, Any],
    skill_package_audit: dict[str, Any],
    request_template_audit: dict[str, Any],
    request_audit: dict[str, Any],
    request_fingerprint: dict[str, Any],
    external_result_contracts: dict[str, Any],
    phase_state_audit: dict[str, Any],
    draft_readiness: dict[str, Any],
    output_boundary_audit: dict[str, Any],
    skill_update_plan: dict[str, Any],
    skill_update_audit: dict[str, Any],
    forward_test_plan: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    agent_rollout_audit: dict[str, Any],
    execution_trace_validation: dict[str, Any],
    verification_claim_audit: dict[str, Any],
    artifact_validation: dict[str, Any],
    code_fence_audit: dict[str, Any],
    public_safety_audit: dict[str, Any],
    claim_consistency_audit: dict[str, Any],
    biological_claim_boundary_audit: dict[str, Any],
    child_reference_coverage: dict[str, Any],
    routing_metadata_audit: dict[str, Any],
    source_grounding_audit: dict[str, Any],
    source_fetch_boundary_audit: dict[str, Any],
    workflow_invariant_audit: dict[str, Any],
    requirement_coverage: dict[str, Any],
    api_surface_audit: dict[str, Any],
    key_api_coverage_audit: dict[str, Any],
    eval_splits: dict[str, Any],
    eval_result_judge: dict[str, Any],
    eval_leakage_audit: dict[str, Any],
    agent_rollout_result_judge: dict[str, Any],
    e2e_acceptance: dict[str, Any],
    smoke_test_plan: dict[str, Any],
    review_cursor: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
    review_prompt_materials: dict[str, Any],
    review_prompt_suite_audit: dict[str, Any],
    review_iteration_log: dict[str, Any],
    patch_application: dict[str, Any],
    review_remediation_audit: dict[str, Any],
    review_optimizer_state: dict[str, Any],
    patch_safety_audit: dict[str, Any],
    patch_operation_contracts: dict[str, Any],
    review_discipline_audit: dict[str, Any],
    rubric_grounding_audit: dict[str, Any],
    review_trajectory_audit: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
    task_catalog: dict[str, Any],
    task_partition_decision_log: dict[str, Any],
    task_partition_audit: dict[str, Any],
    source_parsing_coverage: dict[str, Any],
    source_parsing_audit: dict[str, Any],
    source_ingestion_audit: dict[str, Any],
    backend_extension_audit: dict[str, Any],
    environment_install_plan: dict[str, Any],
    resource_boundary_audit: dict[str, Any],
    evidence_coverage: dict[str, Any],
    evidence_precedence: dict[str, Any],
    evidence_claim_taxonomy_audit: dict[str, Any],
    contract_traceability: dict[str, Any],
    lineage_graph: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    environment_spec: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    parameter_catalog: dict[str, Any],
    eval_plan: dict[str, Any],
    draft_candidates: dict[str, Any],
    grounding_gate: dict[str, Any],
    routing_fixture: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    if lint_report.get("status") != "pass":
        add_finding(findings, "error", "lint_failed", "Child skill lint did not pass.")
    if child_metadata_audit.get("status") != "pass":
        add_finding(findings, "error", "child_metadata_audit_failed", "Child skill metadata or one-skill trigger shape failed audit.")
    if child_package_purity_audit.get("status") != "pass":
        add_finding(findings, "error", "child_package_purity_audit_failed", "Public child skill contains files outside the lightweight package contract.")
    if builder_runtime_audit.get("status") != "pass":
        add_finding(findings, "error", "builder_runtime_audit_failed", "Builder runtime audit did not pass.")
    if agent_metadata_audit.get("status") != "pass":
        add_finding(findings, "error", "agent_metadata_audit_failed", "Builder SKILL.md and agents/openai.yaml metadata alignment audit did not pass.")
    if public_origin_audit.get("status") != "pass":
        add_finding(findings, "error", "public_origin_audit_failed", "Public project files contain private origin markers or machine-specific execution details.")
    if module_inventory_audit.get("status") != "pass":
        add_finding(findings, "error", "module_inventory_audit_failed", "Builder module inventory audit did not pass.")
    if builder_baseline_audit.get("status") != "pass":
        add_finding(findings, "error", "builder_baseline_audit_failed", "Builder engineering baseline coverage audit did not pass.")
    if skill_package_audit.get("status") != "pass":
        add_finding(findings, "error", "skill_package_audit_failed", "Builder skill package audit did not pass.")
    if request_template_audit.get("status") != "pass":
        add_finding(findings, "error", "request_template_audit_failed", "Build request template contract audit did not pass.")
    if request_audit.get("status") != "pass":
        add_finding(findings, "error", "request_audit_failed", "Build request audit did not pass.")
    if request_fingerprint.get("status") != "pass":
        add_finding(findings, "error", "request_fingerprint_failed", "Build request fingerprint did not pass.")
    if request_fingerprint.get("stores_raw_request") is not False:
        add_finding(findings, "error", "request_fingerprint_stores_raw_request", "Request fingerprint must not store the raw build request.")
    if external_result_contracts.get("status") != "pass":
        add_finding(findings, "error", "external_result_contracts_failed", "Supplied external eval, rollout, replay, or E2E result evidence failed contract audit.")
    if discovery_resolution_audit.get("status") != "pass":
        add_finding(findings, "error", "discovery_resolution_audit_failed", "Discovery final resolution failed duplicate-risk or target consistency checks.")
    if phase_state_audit.get("status") != "pass":
        add_finding(findings, "error", "phase_state_audit_failed", "Phase ledger structure or output ownership audit failed.")
    if draft_readiness.get("status") != "pass":
        add_finding(findings, "error", "draft_readiness_failed", "Generated child skill still contains draft placeholders or template values.")
    if output_boundary_audit.get("status") != "pass":
        add_finding(findings, "error", "output_boundary_audit_failed", "Generated child skill violates build output or public package boundaries.")
    if skill_update_plan.get("status") != "pass":
        add_finding(findings, "error", "skill_update_plan_failed", "Discovery reuse, update, or create plan failed.")
    if skill_update_audit.get("status") != "pass":
        add_finding(findings, "error", "skill_update_audit_failed", "Discovery update safety audit failed.")
    if skill_update_audit.get("plan_only") is not True:
        add_finding(findings, "error", "skill_update_audit_not_plan_only", "Skill update audit must remain plan-only.")
    if forward_test_plan.get("status") != "pass":
        add_finding(findings, "error", "forward_test_plan_failed", "Generated child skill lacks a usable plan-only forward-test suite.")
    if agent_rollout_harness.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_harness_failed", "Plan-only agent rollout harness failed.")
    if agent_rollout_audit.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_audit_failed", "Plan-only agent rollout audit failed.")
    if execution_trace_validation.get("status") != "pass":
        add_finding(findings, "error", "execution_trace_validation_failed", "Supplied execution traces are missing required provenance or validation fields.")
    if verification_claim_audit.get("status") != "pass":
        add_finding(findings, "error", "verification_claim_audit_failed", "Task_type verification claims do not match validated traces or rendered child-skill text.")
    if artifact_validation.get("status") != "pass":
        add_finding(findings, "error", "artifact_validation_failed", "Required build artifacts are missing or inconsistent.")
    if code_fence_audit.get("status") != "pass":
        add_finding(findings, "error", "code_fence_audit_failed", "Generated child skill code fences failed audit.")
    if public_safety_audit.get("status") != "pass":
        add_finding(findings, "error", "public_safety_audit_failed", "Generated public child skill failed safety audit.")
    if claim_consistency_audit.get("status") != "pass":
        add_finding(findings, "error", "claim_consistency_audit_failed", "Rendered child-skill claims do not match build artifacts.")
    if biological_claim_boundary_audit.get("status") != "pass":
        add_finding(findings, "error", "biological_claim_boundary_audit_failed", "Rendered child skill contains unsupported high-risk biological claims or missing claim-boundary refusals.")
    if child_reference_coverage.get("status") != "pass":
        add_finding(findings, "error", "child_reference_coverage_failed", "Rendered child references do not cover required build artifacts.")
    if routing_metadata_audit.get("status") != "pass":
        add_finding(findings, "error", "routing_metadata_audit_failed", "Rendered task_type routing metadata failed audit.")
    if source_grounding_audit.get("status") != "pass":
        add_finding(findings, "error", "source_grounding_audit_failed", "Source grounding is not fully traceable into task contracts and rendered references.")
    if source_fetch_boundary_audit.get("status") != "pass":
        add_finding(findings, "error", "source_fetch_boundary_audit_failed", "Source fetching or local source registration violated opt-in or run-directory boundaries.")
    if workflow_invariant_audit.get("status") != "pass":
        add_finding(findings, "error", "workflow_invariant_audit_failed", "First-principles workflow invariants failed.")
    if requirement_coverage.get("status") != "pass":
        add_finding(findings, "error", "requirement_coverage_failed", "Core requirement coverage matrix failed.")
    if api_surface_audit.get("status") != "pass":
        add_finding(findings, "error", "api_surface_audit_failed", "Rendered API surface audit failed.")
    if key_api_coverage_audit.get("status") != "pass":
        add_finding(findings, "error", "key_api_coverage_audit_failed", "Explicit key APIs from the build request were not fully grounded.")
    if eval_splits.get("status") == "fail":
        add_finding(findings, "error", "eval_splits_failed", "Static eval splits are missing required holdout coverage.")
    if eval_result_judge.get("status") == "fail":
        add_finding(findings, "error", "eval_result_judge_failed", "Supplied eval results failed against static expectations.")
    if eval_leakage_audit.get("status") != "pass":
        add_finding(findings, "error", "eval_leakage_audit_failed", "Eval split or rollout prompt leakage audit failed.")
    if agent_rollout_result_judge.get("status") == "fail":
        add_finding(findings, "error", "agent_rollout_result_judge_failed", "Supplied agent rollout results failed against static expectations.")
    if e2e_acceptance.get("status") != "pass":
        add_finding(findings, "error", "e2e_acceptance_failed", "E2E acceptance plan or supplied results failed audit.")
    if request.get("require_e2e_acceptance") and e2e_acceptance.get("e2e_verdict") != "passed":
        add_finding(findings, "error", "required_e2e_acceptance_not_passed", "require_e2e_acceptance is true but full E2E acceptance has not passed.")
    if smoke_test_plan.get("status") != "pass":
        add_finding(findings, "error", "smoke_test_plan_failed", "Smoke test plan or supplied results failed audit.")
    if request.get("require_smoke_test") and smoke_test_plan.get("smoke_verdict") != "passed":
        add_finding(findings, "error", "required_smoke_test_not_passed", "require_smoke_test is true but smoke test results have not fully passed.")
    if review_cursor.get("status") == "fail":
        add_finding(findings, "error", "review_cursor_failed", "Review cursor state is incomplete.")
    if review_prompt_contracts.get("status") == "fail":
        add_finding(findings, "error", "review_prompt_contracts_failed", "Review prompt/state contracts failed.")
    if review_prompt_materials.get("status") == "fail":
        add_finding(findings, "error", "review_prompt_materials_failed", "Review prompt materials failed.")
    if review_prompt_suite_audit.get("status") == "fail":
        add_finding(findings, "error", "review_prompt_suite_audit_failed", "Review prompt suite audit failed.")
    if review_iteration_log.get("status") == "fail":
        add_finding(findings, "error", "review_iteration_log_failed", "Review iteration log failed.")
    if patch_application.get("status") == "fail":
        add_finding(findings, "error", "patch_application_failed", "Review patch application audit failed.")
    if review_remediation_audit.get("status") == "fail":
        add_finding(findings, "error", "review_remediation_audit_failed", "Review finding remediation audit failed.")
    if review_optimizer_state.get("status") == "fail":
        add_finding(findings, "error", "review_optimizer_state_failed", "Review optimizer state failed.")
    if patch_safety_audit.get("status") == "fail":
        add_finding(findings, "error", "patch_safety_audit_failed", "Review patch safety audit failed.")
    if patch_operation_contracts.get("status") == "fail":
        add_finding(findings, "error", "patch_operation_contracts_failed", "Review patch operation contracts failed.")
    if review_discipline_audit.get("status") == "fail":
        add_finding(findings, "error", "review_discipline_audit_failed", "Review-loop discipline audit failed.")
    if rubric_grounding_audit.get("status") == "fail":
        add_finding(findings, "error", "rubric_grounding_audit_failed", "Rubric grounding audit failed.")
    if review_trajectory_audit.get("status") == "fail":
        add_finding(findings, "error", "review_trajectory_audit_failed", "Review trajectory integrity audit failed.")
    if task_partition_audit.get("status") == "fail":
        add_finding(findings, "error", "task_partition_audit_failed", "Task partition violates capability/task_type boundaries.")
    if task_partition_decision_log.get("status") == "fail":
        add_finding(findings, "error", "task_partition_decision_log_failed", "Task partition decision log failed.")
    if source_parsing_coverage.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_coverage_failed", "Source parsing coverage failed.")
    if source_parsing_audit.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_audit_failed", "Source parsing strategy or provenance audit failed.")
    if source_ingestion_audit.get("status") == "fail":
        add_finding(findings, "error", "source_ingestion_audit_failed", "Source ingestion identity or count audit failed.")
    if backend_extension_audit.get("status") == "fail":
        add_finding(findings, "error", "backend_extension_audit_failed", "Backend extension boundary audit failed.")
    if environment_install_plan.get("status") == "fail":
        add_finding(findings, "error", "environment_install_plan_failed", "Environment install planning failed.")
    if resource_boundary_audit.get("status") == "fail":
        add_finding(findings, "error", "resource_boundary_audit_failed", "Model, checkpoint, or data resource boundary audit failed.")
    if tutorial_reproduction_plan.get("status") == "fail":
        add_finding(findings, "error", "tutorial_reproduction_plan_failed", "Tutorial reproduction planning failed.")
    if execution_replay_orchestrator.get("status") == "fail":
        add_finding(findings, "error", "execution_replay_orchestrator_failed", "Execution replay orchestration failed.")
    if evidence_coverage.get("status") == "fail":
        add_finding(findings, "error", "evidence_coverage_failed", "Task evidence coverage failed.")
    if evidence_precedence.get("status") == "fail":
        add_finding(findings, "error", "evidence_precedence_failed", "Task evidence precedence failed.")
    if evidence_claim_taxonomy_audit.get("status") == "fail":
        add_finding(findings, "error", "evidence_claim_taxonomy_audit_failed", "Evidence claim taxonomy audit failed.")
    if contract_traceability.get("status") != "pass":
        add_finding(findings, "error", "contract_traceability_failed", "Task input, output, validation, or refusal contracts lack evidence traceability.")
    if lineage_graph.get("status") == "fail":
        add_finding(findings, "error", "lineage_graph_failed", "Source-to-skill lineage graph failed.")
    if grounding_gate.get("status") == "fail":
        add_finding(findings, "error", "grounding_gate_failed", "Task API/interface grounding gate failed.")
    if discovery_audit.get("status") == "fail":
        add_finding(findings, "error", "discovery_audit_failed", "Discovery decision audit failed.")
    if discovery_match_audit.get("status") == "fail":
        add_finding(findings, "error", "discovery_match_audit_failed", "Discovery match-quality audit failed.")
    if review_result.get("status") != "passed":
        add_finding(findings, "error", "review_not_passed", "Self-review loop did not pass the configured gate.")
    action = normalize_action(discovery_report.get("decision"), skill_update_plan.get("recommended_action"))
    if action == REUSE_EXISTING:
        add_finding(findings, "warning", "reuse_existing_skill", "Discovery recommends reusing an existing child skill instead of publishing a duplicate.")

    tasks = task_catalog.get("tasks", [])
    if not tasks:
        add_finding(findings, "error", "missing_task_types", "No task_type entries were produced.")
    if eval_plan.get("scenario_count", 0) == 0:
        add_finding(findings, "error", "missing_eval_plan", "No static eval scenarios were produced.")
    if routing_fixture.get("case_count", 0) == 0:
        add_finding(findings, "error", "missing_routing_fixture", "No task_type routing fixture cases were produced.")
    if tutorial_reproduction_plan.get("replay_count", 0) == 0:
        add_finding(findings, "error", "missing_tutorial_reproduction_plan", "No tutorial reproduction replay plans were produced.")
    if contract_traceability.get("record_count", 0) == 0:
        add_finding(findings, "error", "missing_contract_traceability", "No contract traceability records were produced.")
    if lineage_graph.get("node_count", 0) == 0 or lineage_graph.get("edge_count", 0) == 0:
        add_finding(findings, "error", "missing_lineage_graph", "Lineage graph has no nodes or edges.")
    if not environment_spec.get("declared_dependencies") and not environment_spec.get("imported_modules"):
        add_finding(findings, "warning", "missing_environment_hints", "No dependency or import hints were mined.")
    if tutorial_catalog.get("tutorial_count", 0) == 0:
        add_finding(findings, "warning", "missing_tutorial_steps", "No tutorial or example steps were mined.")
    if interface_grounding.get("interface_count", 0) > 0 and parameter_catalog.get("parameter_count", 0) == 0:
        add_finding(findings, "warning", "missing_parameter_constraints", "Interfaces were inspected, but no parameters were mined.")

    any_execution_verified = False
    for task in tasks:
        task_type = str(task.get("task_type"))
        if not task.get("evidence_refs"):
            add_finding(findings, "error", "task_missing_evidence", "Task is missing evidence references.", task_type)
        if task.get("verification_status") == "execution_verified":
            any_execution_verified = True
            if not task.get("trace_ref"):
                add_finding(findings, "error", "verified_without_trace", "execution_verified task_type has no trace_ref.", task_type)
        if task.get("verification_status") == "execution_failed":
            add_finding(
                findings,
                "warning",
                "execution_trace_failed",
                "A supplied execution trace failed; keep this task_type unverified and include troubleshooting guidance.",
                task_type,
            )
        has_replay_plan = any(
            replay.get("task_type") == task_type for replay in tutorial_reproduction_plan.get("replays", [])
        )
        if not has_replay_plan:
            add_finding(
                findings,
                "error",
                "task_missing_tutorial_reproduction_plan",
                "Task_type has no tutorial reproduction plan.",
                task_type,
            )
        api_refs = api_grounding.get("by_task_type", {}).get(task_type, {}).get("api_candidates", [])
        if not api_refs:
            add_finding(findings, "warning", "task_missing_api_grounding", "No parsed API candidate is linked to this task_type.", task_type)
        interface_refs = interface_grounding.get("by_task_type", {}).get(task_type, {}).get("interfaces", [])
        if api_refs and not interface_refs:
            add_finding(
                findings,
                "warning",
                "task_missing_interface_grounding",
                "API candidates exist, but no inspected interface is linked to this task_type.",
                task_type,
            )

    if request.get("execution_grounded") and not any_execution_verified:
        add_finding(
            findings,
            "error",
            "execution_grounding_requested_without_verified_task",
            "execution_grounded was requested, but no task_type has successful trace-backed verification.",
        )
    if request.get("execution_grounded") and execution_trace_validation.get("valid_success_count", 0) == 0:
        add_finding(
            findings,
            "error",
            "execution_grounding_without_valid_success_trace",
            "execution_grounded was requested, but no valid successful trace passed validation.",
        )
    if request.get("execution_grounded") and tutorial_reproduction_plan.get("tutorial_count", 0) == 0:
        add_finding(
            findings,
            "error",
            "execution_grounding_without_tutorial_plan_sources",
            "execution_grounded was requested, but no tutorial/example steps are available for replay planning.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    status = "blocked" if has_errors else ("reuse_ready" if action == REUSE_EXISTING else "publishable")
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": status,
        "recommended_action": action,
        "lint_status": lint_report.get("status"),
        "child_metadata_audit_status": child_metadata_audit.get("status"),
        "child_package_purity_audit_status": child_package_purity_audit.get("status"),
        "builder_runtime_audit_status": builder_runtime_audit.get("status"),
        "agent_metadata_audit_status": agent_metadata_audit.get("status"),
        "public_origin_audit_status": public_origin_audit.get("status"),
        "module_inventory_audit_status": module_inventory_audit.get("status"),
        "builder_baseline_audit_status": builder_baseline_audit.get("status"),
        "skill_package_audit_status": skill_package_audit.get("status"),
        "request_template_audit_status": request_template_audit.get("status"),
        "request_audit_status": request_audit.get("status"),
        "request_fingerprint_status": request_fingerprint.get("status"),
        "external_result_contracts_status": external_result_contracts.get("status"),
        "phase_state_audit_status": phase_state_audit.get("status"),
        "review_status": review_result.get("status"),
        "discovery_decision": discovery_report.get("decision"),
        "discovery_audit_status": discovery_audit.get("status"),
        "discovery_match_audit_status": discovery_match_audit.get("status"),
        "discovery_resolution_audit_status": discovery_resolution_audit.get("status"),
        "candidate_count": draft_candidates.get("candidate_count", 0),
        "output_boundary_audit_status": output_boundary_audit.get("status"),
        "skill_update_plan_status": skill_update_plan.get("status"),
        "skill_update_audit_status": skill_update_audit.get("status"),
        "skill_update_recommended_action": skill_update_plan.get("recommended_action"),
        "forward_test_plan_status": forward_test_plan.get("status"),
        "forward_test_scenario_count": forward_test_plan.get("scenario_count", 0),
        "agent_rollout_harness_status": agent_rollout_harness.get("status"),
        "agent_rollout_audit_status": agent_rollout_audit.get("status"),
        "agent_rollout_count": agent_rollout_harness.get("rollout_count", 0),
        "lineage_graph_status": lineage_graph.get("status"),
        "execution_replay_orchestrator_status": execution_replay_orchestrator.get("status"),
        "evidence_precedence_status": evidence_precedence.get("status"),
        "evidence_claim_taxonomy_audit_status": evidence_claim_taxonomy_audit.get("status"),
        "claim_consistency_audit_status": claim_consistency_audit.get("status"),
        "biological_claim_boundary_audit_status": biological_claim_boundary_audit.get("status"),
        "child_reference_coverage_status": child_reference_coverage.get("status"),
        "routing_metadata_audit_status": routing_metadata_audit.get("status"),
        "source_grounding_audit_status": source_grounding_audit.get("status"),
        "source_fetch_boundary_audit_status": source_fetch_boundary_audit.get("status"),
        "workflow_invariant_audit_status": workflow_invariant_audit.get("status"),
        "requirement_coverage_status": requirement_coverage.get("status"),
        "api_surface_audit_status": api_surface_audit.get("status"),
        "key_api_coverage_audit_status": key_api_coverage_audit.get("status"),
        "eval_split_counts": eval_splits.get("split_counts", {}),
        "eval_result_judge_status": eval_result_judge.get("status"),
        "eval_leakage_audit_status": eval_leakage_audit.get("status"),
        "agent_rollout_result_judge_status": agent_rollout_result_judge.get("status"),
        "e2e_acceptance_status": e2e_acceptance.get("status"),
        "e2e_verdict": e2e_acceptance.get("e2e_verdict"),
        "require_e2e_acceptance": bool(request.get("require_e2e_acceptance")),
        "smoke_test_plan_status": smoke_test_plan.get("status"),
        "smoke_verdict": smoke_test_plan.get("smoke_verdict"),
        "require_smoke_test": bool(request.get("require_smoke_test")),
        "review_cursor_status": review_cursor.get("status"),
        "review_prompt_contracts_status": review_prompt_contracts.get("status"),
        "review_prompt_materials_status": review_prompt_materials.get("status"),
        "review_prompt_suite_audit_status": review_prompt_suite_audit.get("status"),
        "review_iteration_log_status": review_iteration_log.get("status"),
        "patch_application_status": patch_application.get("status"),
        "review_remediation_audit_status": review_remediation_audit.get("status"),
        "review_optimizer_state_status": review_optimizer_state.get("status"),
        "patch_safety_audit_status": patch_safety_audit.get("status"),
        "patch_operation_contracts_status": patch_operation_contracts.get("status"),
        "review_discipline_audit_status": review_discipline_audit.get("status"),
        "backend_extension_audit_status": backend_extension_audit.get("status"),
        "rubric_grounding_audit_status": rubric_grounding_audit.get("status"),
        "review_trajectory_audit_status": review_trajectory_audit.get("status"),
        "task_partition_audit_status": task_partition_audit.get("status"),
        "task_partition_decision_log_status": task_partition_decision_log.get("status"),
        "source_parsing_coverage_status": source_parsing_coverage.get("status"),
        "source_parsing_audit_status": source_parsing_audit.get("status"),
        "source_ingestion_audit_status": source_ingestion_audit.get("status"),
        "environment_install_plan_status": environment_install_plan.get("status"),
        "resource_boundary_audit_status": resource_boundary_audit.get("status"),
        "tutorial_reproduction_plan_status": tutorial_reproduction_plan.get("status"),
        "verification_claim_audit_status": verification_claim_audit.get("status"),
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "findings": findings,
        "policy": "Publish only when builder runtime audit, agent metadata audit, public origin audit, module inventory audit, builder baseline audit, skill package audit, request template audit, request audit, request fingerprint, phase state audit, lint, child metadata audit, child package purity audit, draft readiness, output boundary, skill update planning, skill update audit, forward test planning, agent rollout harness, task partition audit, execution trace validation, verification claim audit, source parsing coverage, source parsing audit, source ingestion audit, source grounding audit, backend extension audit, environment install planning, resource boundary audit, review prompt contracts, review prompt materials, review iteration log, review cursor, patch application, review remediation, review optimizer state, patch safety, review discipline, rubric grounding, review trajectory, tutorial reproduction planning, evidence coverage, evidence precedence, contract traceability, API surface audit, key API coverage audit, claim consistency, biological claim boundary audit, child reference coverage, routing metadata, workflow invariants, requirement coverage, smoke test planning, E2E acceptance contract, lineage graph, eval splits, supplied eval results, eval leakage audit, supplied agent rollout results, artifact validation, code-fence audit, public safety audit, grounding gate, review, discovery audit, discovery match audit, discovery, routing fixture, task evidence, backend, and verification boundaries pass.",
    }
