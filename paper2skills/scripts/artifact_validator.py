"""Validate build artifacts before publish."""

from __future__ import annotations

from typing import Any

from artifact_contracts import validate_artifact_contracts
from common import now_utc, slugify
from constants import SCHEMA_VERSION


REQUIRED_TOP_LEVEL_ARTIFACTS = [
    "request",
    "phase_state",
    "phase_state_audit",
    "protocol_compliance_audit",
    "builder_runtime_audit",
    "agent_metadata_audit",
    "public_origin_audit",
    "module_inventory_audit",
    "builder_baseline_audit",
    "skill_package_audit",
    "request_template_audit",
    "builder_version_audit",
    "request_audit",
    "request_fingerprint",
    "external_result_contracts",
    "discovery_preflight",
    "discovery_report",
    "discovery_audit",
    "discovery_match_audit",
    "discovery_resolution_audit",
    "source_grounding",
    "source_fetch_report",
    "source_fetch_boundary_audit",
    "source_index",
    "source_parse_report",
    "source_parsing_coverage",
    "source_parsing_audit",
    "source_ingestion_audit",
    "source_grounding_audit",
    "evidence_cards",
    "evidence_coverage",
    "evidence_precedence",
    "evidence_claim_taxonomy_audit",
    "source_manifest",
    "api_grounding",
    "interface_grounding",
    "key_api_coverage_audit",
    "backend_contract",
    "backend_extension_audit",
    "environment_spec",
    "environment_install_plan",
    "resource_inventory",
    "resource_boundary_audit",
    "tutorial_catalog",
    "parameter_catalog",
    "task_catalog",
    "task_partition_decision_log",
    "task_type_router",
    "task_partition_audit",
    "task_conflict_matrix",
    "routing_fixture",
    "eval_plan",
    "execution_trace_validation",
    "execution_replay_orchestrator",
    "verification_claim_audit",
    "execution_plan",
    "tutorial_reproduction_plan",
    "contract_traceability",
    "lineage_graph",
    "acceptance_suite",
    "eval_splits",
    "eval_result_judge",
    "eval_leakage_audit",
    "agent_rollout_result_judge",
    "e2e_acceptance",
    "smoke_test_plan",
    "draft_candidates",
    "candidate_registry",
    "candidate_selection_audit",
    "candidate_promotion_audit",
    "final_candidate_audit",
    "candidate_evolution_audit",
    "skill_spec",
    "review_summary",
    "review_evolution",
    "review_evolution_plot",
    "review_iteration_log",
    "review_prompt_contracts",
    "review_prompt_materials",
    "review_prompt_suite_audit",
    "review_cursor",
    "patch_application",
    "review_remediation_audit",
    "review_optimizer_state",
    "patch_safety_audit",
    "patch_operation_contracts",
    "review_discipline_audit",
    "rubric_grounding_audit",
    "review_trajectory_audit",
    "skill_lint_report",
    "child_metadata_audit",
    "child_package_purity_audit",
    "draft_readiness",
    "output_boundary_audit",
    "skill_update_plan",
    "skill_update_audit",
    "forward_test_plan",
    "agent_rollout_harness",
    "agent_rollout_audit",
    "api_surface_audit",
    "claim_consistency_audit",
    "biological_claim_boundary_audit",
    "child_reference_coverage",
    "routing_metadata_audit",
    "workflow_invariant_audit",
    "requirement_coverage",
    "completion_evidence_audit",
    "acceptance_handoff",
    "architecture_completeness_audit",
    "grounding_gate",
    "artifact_contracts",
    "artifact_closure_audit",
    "artifact_validation",
    "code_fence_audit",
    "public_safety_audit",
    "publish_gate",
    "quality_report",
    "score_report",
    "release_package",
    "release_action_audit",
    "codex_publish_adapter",
    "install_readiness",
    "publish_manifest",
    "publish_manifest_audit",
    "completion_audit",
    "build_timeline",
    "build_timeline_audit",
    "run_scorecard",
    "run_manifest",
]

POST_CLEANUP_ARTIFACTS = [
    "output_retention",
]

PRE_PUBLISH_ARTIFACTS = [
    "request",
    "phase_state",
    "phase_state_audit",
    "protocol_compliance_audit",
    "builder_runtime_audit",
    "agent_metadata_audit",
    "public_origin_audit",
    "module_inventory_audit",
    "builder_baseline_audit",
    "skill_package_audit",
    "request_template_audit",
    "request_audit",
    "request_fingerprint",
    "external_result_contracts",
    "discovery_preflight",
    "discovery_report",
    "discovery_audit",
    "discovery_match_audit",
    "discovery_resolution_audit",
    "source_grounding",
    "source_fetch_report",
    "source_fetch_boundary_audit",
    "source_index",
    "source_parse_report",
    "source_parsing_coverage",
    "source_parsing_audit",
    "source_ingestion_audit",
    "source_grounding_audit",
    "evidence_cards",
    "evidence_coverage",
    "evidence_precedence",
    "evidence_claim_taxonomy_audit",
    "source_manifest",
    "api_grounding",
    "interface_grounding",
    "key_api_coverage_audit",
    "backend_contract",
    "backend_extension_audit",
    "environment_spec",
    "environment_install_plan",
    "resource_inventory",
    "resource_boundary_audit",
    "tutorial_catalog",
    "parameter_catalog",
    "task_catalog",
    "task_partition_decision_log",
    "task_type_router",
    "task_partition_audit",
    "task_conflict_matrix",
    "routing_fixture",
    "eval_plan",
    "execution_trace_validation",
    "execution_replay_orchestrator",
    "verification_claim_audit",
    "execution_plan",
    "tutorial_reproduction_plan",
    "contract_traceability",
    "lineage_graph",
    "acceptance_suite",
    "eval_splits",
    "eval_result_judge",
    "eval_leakage_audit",
    "agent_rollout_result_judge",
    "e2e_acceptance",
    "smoke_test_plan",
    "draft_candidates",
    "skill_spec",
    "review_summary",
    "review_evolution",
    "review_iteration_log",
    "review_prompt_contracts",
    "review_prompt_materials",
    "review_prompt_suite_audit",
    "review_cursor",
    "patch_application",
    "review_remediation_audit",
    "review_optimizer_state",
    "patch_safety_audit",
    "patch_operation_contracts",
    "review_discipline_audit",
    "rubric_grounding_audit",
    "review_trajectory_audit",
    "skill_lint_report",
    "child_metadata_audit",
    "child_package_purity_audit",
    "draft_readiness",
    "output_boundary_audit",
    "skill_update_plan",
    "skill_update_audit",
    "forward_test_plan",
    "agent_rollout_harness",
    "agent_rollout_audit",
    "api_surface_audit",
    "claim_consistency_audit",
    "biological_claim_boundary_audit",
    "child_reference_coverage",
    "routing_metadata_audit",
    "workflow_invariant_audit",
    "requirement_coverage",
    "completion_evidence_audit",
    "acceptance_handoff",
    "grounding_gate",
    "artifact_contracts",
    "code_fence_audit",
    "public_safety_audit",
]


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


def validate_artifact_bundle(
    artifacts: dict[str, Any],
    required_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    required = required_artifacts or REQUIRED_TOP_LEVEL_ARTIFACTS
    for name in required:
        if name not in artifacts:
            add_finding(findings, "error", "missing_artifact", "Required build artifact is missing.", name)

    for name, artifact in artifacts.items():
        if isinstance(artifact, dict) and artifact.get("schema_version") != SCHEMA_VERSION:
            add_finding(findings, "error", "schema_version_mismatch", "Artifact schema_version is missing or wrong.", name)

    findings.extend(validate_artifact_contracts(artifacts, required))

    artifact_contracts = artifacts.get("artifact_contracts") or {}
    if isinstance(artifact_contracts, dict) and artifact_contracts.get("contracts"):
        declared_contracts = artifact_contracts.get("contracts", {})
        missing_declared_contracts = sorted(name for name in required if name not in declared_contracts)
        if missing_declared_contracts:
            add_finding(
                findings,
                "error",
                "artifact_contract_catalog_incomplete",
                "artifact_contracts.yaml does not declare every required artifact.",
                "artifact_contracts",
            )

    task_catalog = artifacts.get("task_catalog") or {}
    router = artifacts.get("task_type_router") or {}
    source_index = artifacts.get("source_index") or {}
    source_manifest = artifacts.get("source_manifest") or {}
    request_audit = artifacts.get("request_audit") or {}
    builder_runtime_audit = artifacts.get("builder_runtime_audit") or {}
    phase_state_audit = artifacts.get("phase_state_audit") or {}
    if "phase_state_audit" in required and phase_state_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "phase_state_audit_failed",
            "Phase ledger structure or output ownership audit failed.",
            "phase_state_audit",
        )
    protocol_compliance_audit = artifacts.get("protocol_compliance_audit") or {}
    if "protocol_compliance_audit" in required and protocol_compliance_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "protocol_compliance_audit_failed",
            "Cross-stage protocol compliance audit failed.",
            "protocol_compliance_audit",
        )
    if builder_runtime_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "builder_runtime_audit_failed",
            "Builder runtime audit failed.",
            "builder_runtime_audit",
        )
    agent_metadata_audit = artifacts.get("agent_metadata_audit") or {}
    if agent_metadata_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "agent_metadata_audit_failed",
            "Builder SKILL.md and agents/openai.yaml metadata alignment audit failed.",
            "agent_metadata_audit",
        )
    public_origin_audit = artifacts.get("public_origin_audit") or {}
    if public_origin_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "public_origin_audit_failed",
            "Public project files contain private origin markers or machine-specific execution details.",
            "public_origin_audit",
        )
    module_inventory_audit = artifacts.get("module_inventory_audit") or {}
    if module_inventory_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "module_inventory_audit_failed",
            "Builder module inventory audit failed.",
            "module_inventory_audit",
        )
    builder_baseline_audit = artifacts.get("builder_baseline_audit") or {}
    if builder_baseline_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "builder_baseline_audit_failed",
            "Builder engineering baseline coverage audit failed.",
            "builder_baseline_audit",
        )
    skill_package_audit = artifacts.get("skill_package_audit") or {}
    if skill_package_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "skill_package_audit_failed",
            "Builder skill package audit failed.",
            "skill_package_audit",
        )
    request_template_audit = artifacts.get("request_template_audit") or {}
    if request_template_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "request_template_audit_failed",
            "Build request template contract audit failed.",
            "request_template_audit",
        )
    builder_version_audit = artifacts.get("builder_version_audit") or {}
    if "builder_version_audit" in required and builder_version_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "builder_version_audit_failed",
            "Builder version audit failed.",
            "builder_version_audit",
        )
    if request_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "request_audit_failed",
            "Build request audit failed.",
            "request_audit",
        )
    request_fingerprint = artifacts.get("request_fingerprint") or {}
    if "request_fingerprint" in required:
        if request_fingerprint.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "request_fingerprint_failed",
                "Build request fingerprint failed.",
                "request_fingerprint",
            )
        if request_fingerprint.get("stores_raw_request") is not False:
            add_finding(
                findings,
                "error",
                "request_fingerprint_stores_raw_request",
                "Request fingerprint must not store the raw build request.",
                "request_fingerprint",
            )
        sensitive_paths = request_fingerprint.get("sensitive_field_paths") or []
        if request_fingerprint.get("redacted_sensitive_value_count") != len(sensitive_paths):
            add_finding(
                findings,
                "error",
                "request_fingerprint_redaction_count_mismatch",
                "Request fingerprint redaction count must match sensitive field paths.",
                "request_fingerprint",
            )
    external_result_contracts = artifacts.get("external_result_contracts") or {}
    if "external_result_contracts" in required and external_result_contracts.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "external_result_contracts_failed",
            "Supplied external eval, rollout, replay, or E2E result evidence failed schema or leakage-boundary checks.",
            "external_result_contracts",
        )
    discovery_audit = artifacts.get("discovery_audit") or {}
    if discovery_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "discovery_audit_failed",
            "Discovery decision audit failed.",
            "discovery_audit",
        )
    discovery_match_audit = artifacts.get("discovery_match_audit") or {}
    if discovery_match_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "discovery_match_audit_failed",
            "Discovery match-quality audit failed.",
            "discovery_match_audit",
        )
    discovery_resolution_audit = artifacts.get("discovery_resolution_audit") or {}
    if "discovery_resolution_audit" in required and discovery_resolution_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "discovery_resolution_audit_failed",
            "Discovery final resolution failed duplicate-risk or target consistency checks.",
            "discovery_resolution_audit",
        )
    evidence_coverage = artifacts.get("evidence_coverage") or {}
    if evidence_coverage.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "evidence_coverage_failed",
            "Task evidence coverage failed.",
            "evidence_coverage",
        )
    publish_manifest_audit = artifacts.get("publish_manifest_audit") or {}
    if publish_manifest_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "publish_manifest_audit_failed",
            "Publish manifest consistency audit failed.",
            "publish_manifest_audit",
        )
    evidence_precedence = artifacts.get("evidence_precedence") or {}
    if evidence_precedence.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "evidence_precedence_failed",
            "Task evidence precedence failed.",
            "evidence_precedence",
        )
    evidence_claim_taxonomy_audit = artifacts.get("evidence_claim_taxonomy_audit") or {}
    if evidence_claim_taxonomy_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "evidence_claim_taxonomy_audit_failed",
            "Evidence claim taxonomy audit failed.",
            "evidence_claim_taxonomy_audit",
        )
    precedence_tasks = {record.get("task_type") for record in evidence_precedence.get("tasks", [])}
    catalog_tasks = {task.get("task_type") for task in task_catalog.get("tasks", [])}
    missing_precedence = sorted(str(task) for task in catalog_tasks.difference(precedence_tasks) if task)
    if missing_precedence:
        add_finding(
            findings,
            "error",
            "task_without_evidence_precedence",
            "Some task_type entries have no evidence precedence record.",
            "evidence_precedence",
        )
    if source_manifest.get("source_count", 0) == 0:
        add_finding(findings, "error", "missing_sources", "Source manifest has no sources.", "source_manifest")
    source_parse_report = artifacts.get("source_parse_report") or {}
    if "strategy" not in source_parse_report or "counts" not in source_parse_report or "capability_matrix" not in source_parse_report:
        add_finding(
            findings,
            "error",
            "missing_source_parse_report",
            "Source parse report must record parsing strategy, counts, and parser capability matrix.",
            "source_parse_report",
        )
    capability_matrix = source_parse_report.get("capability_matrix") or []
    capability_rows = capability_matrix if isinstance(capability_matrix, list) else []
    if "source_parse_report" in required and not capability_matrix:
        add_finding(
            findings,
            "error",
            "missing_parser_capability_matrix",
            "Source parse report must declare parser capabilities by source kind.",
            "source_parse_report",
        )
    for row in capability_rows:
        if isinstance(row, dict) and row.get("can_verify_execution") is not False:
            add_finding(
                findings,
                "error",
                "parser_capability_overclaims_execution",
                "Static parser capability matrix must not claim execution verification.",
                "source_parse_report",
            )
    source_parsing_coverage = artifacts.get("source_parsing_coverage") or {}
    if source_parsing_coverage.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_parsing_coverage_failed",
            "Source parsing coverage failed.",
            "source_parsing_coverage",
        )
    source_parsing_audit = artifacts.get("source_parsing_audit") or {}
    if source_parsing_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_parsing_audit_failed",
            "Source parsing strategy or provenance audit failed.",
            "source_parsing_audit",
        )
    source_fetch_boundary_audit = artifacts.get("source_fetch_boundary_audit") or {}
    if source_fetch_boundary_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_fetch_boundary_audit_failed",
            "Source fetch opt-in, run-directory, or archive extraction boundary audit failed.",
            "source_fetch_boundary_audit",
        )
    source_ingestion_audit = artifacts.get("source_ingestion_audit") or {}
    if source_ingestion_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_ingestion_audit_failed",
            "Source ingestion identity or count audit failed.",
            "source_ingestion_audit",
        )
    source_grounding_audit = artifacts.get("source_grounding_audit") or {}
    if source_grounding_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_grounding_audit_failed",
            "Source grounding audit failed.",
            "source_grounding_audit",
        )
    if (
        "source_parsing_coverage" in required
        and source_index.get("file_count") is not None
        and source_parsing_coverage.get("file_count") is not None
        and source_index.get("file_count") != source_parsing_coverage.get("file_count")
    ):
        add_finding(
            findings,
            "error",
            "source_parsing_coverage_mismatch",
            "source_index and source_parsing_coverage disagree on file_count.",
            "source_parsing_coverage",
        )
    resource_inventory = artifacts.get("resource_inventory") or {}
    if "resource_inventory" in required and resource_inventory.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "resource_inventory_failed",
            "Resource inventory failed.",
            "resource_inventory",
        )
    resource_boundary_audit = artifacts.get("resource_boundary_audit") or {}
    if resource_boundary_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "resource_boundary_audit_failed",
            "Model, checkpoint, or data resource boundary audit failed.",
            "resource_boundary_audit",
        )
    tasks = {task.get("task_type") for task in task_catalog.get("tasks", [])}
    task_partition_decision_log = artifacts.get("task_partition_decision_log") or {}
    if task_partition_decision_log.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "task_partition_decision_log_failed",
            "Task partition decision log failed.",
            "task_partition_decision_log",
        )
    accepted_partition_tasks = set(task_partition_decision_log.get("accepted_task_types", []))
    missing_decision_tasks = sorted(str(task) for task in tasks.difference(accepted_partition_tasks) if task)
    if "task_partition_decision_log" in required and missing_decision_tasks:
        add_finding(
            findings,
            "error",
            "task_missing_partition_decision",
            "Some task_type entries are missing accepted partition decisions.",
            "task_partition_decision_log",
        )
    routes = {route.get("task_type") for route in router.get("routes", [])}
    missing_routes = sorted(str(task) for task in tasks.difference(routes) if task)
    if missing_routes:
        add_finding(
            findings,
            "error",
            "task_without_route",
            "Some task_type entries have no route.",
            "task_type_router",
        )

    task_partition_audit = artifacts.get("task_partition_audit") or {}
    if task_partition_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "task_partition_audit_failed",
            "Task partition violates capability/task_type boundaries.",
            "task_partition_audit",
        )
    audited_tasks = {task for task in task_partition_audit.get("task_types", [])}
    missing_partition_audit = sorted(str(task) for task in tasks.difference(audited_tasks) if task)
    if missing_partition_audit:
        add_finding(
            findings,
            "error",
            "task_missing_partition_audit",
            "Some task_type entries are missing from task_partition_audit.",
            "task_partition_audit",
        )

    conflict_matrix = artifacts.get("task_conflict_matrix") or {}
    if len(tasks) > 1 and conflict_matrix.get("pair_count", 0) == 0:
        add_finding(
            findings,
            "error",
            "missing_task_conflict_matrix",
            "Multiple task_type entries require a conflict matrix.",
            "task_conflict_matrix",
        )

    routing_fixture = artifacts.get("routing_fixture") or {}
    routing_cases = routing_fixture.get("cases", [])
    routing_tasks = {case.get("expected_task_type") for case in routing_cases if case.get("kind") == "select_task_type"}
    missing_routing_fixtures = sorted(str(task) for task in tasks.difference(routing_tasks) if task)
    if missing_routing_fixtures:
        add_finding(
            findings,
            "error",
            "task_without_routing_fixture",
            "Some task_type entries have no select_task_type routing fixture.",
            "routing_fixture",
        )
    if not any(case.get("kind") == "unsupported_task" for case in routing_cases):
        add_finding(
            findings,
            "error",
            "missing_unsupported_routing_fixture",
            "Routing fixtures must include an unsupported-task refusal case.",
            "routing_fixture",
        )

    eval_plan = artifacts.get("eval_plan") or {}
    eval_tasks = {scenario.get("task_type") for scenario in eval_plan.get("scenarios", [])}
    missing_eval = sorted(str(task) for task in tasks.difference(eval_tasks) if task)
    if missing_eval:
        add_finding(findings, "error", "task_without_eval", "Some task_type entries have no eval scenario.", "eval_plan")

    execution_trace_validation = artifacts.get("execution_trace_validation") or {}
    if execution_trace_validation.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "execution_trace_validation_failed",
            "Execution trace validation failed.",
            "execution_trace_validation",
        )
    verification_claim_audit = artifacts.get("verification_claim_audit") or {}
    if verification_claim_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "verification_claim_audit_failed",
            "Task_type verification claims do not match validated traces or rendered child-skill text.",
            "verification_claim_audit",
        )
    if (
        execution_trace_validation.get("execution_grounded_requested")
        and execution_trace_validation.get("valid_success_count", 0) == 0
    ):
        add_finding(
            findings,
            "error",
            "execution_grounding_without_valid_success_trace",
            "Execution grounding was requested, but no valid successful trace was supplied.",
            "execution_trace_validation",
        )

    execution_replay_orchestrator = artifacts.get("execution_replay_orchestrator") or {}
    if execution_replay_orchestrator.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "execution_replay_orchestrator_failed",
            "Execution replay orchestration failed.",
            "execution_replay_orchestrator",
        )

    execution_plan = artifacts.get("execution_plan") or {}
    execution_tasks = {task.get("task_type") for task in execution_plan.get("tasks", [])}
    missing_execution_plan = sorted(str(task) for task in tasks.difference(execution_tasks) if task)
    if missing_execution_plan:
        add_finding(
            findings,
            "error",
            "task_without_execution_plan",
            "Some task_type entries have no execution plan boundary.",
            "execution_plan",
        )

    tutorial_reproduction_plan = artifacts.get("tutorial_reproduction_plan") or {}
    if tutorial_reproduction_plan.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "tutorial_reproduction_plan_failed",
            "Tutorial reproduction planning failed.",
            "tutorial_reproduction_plan",
        )
    replay_tasks = {replay.get("task_type") for replay in tutorial_reproduction_plan.get("replays", [])}
    missing_replays = sorted(str(task) for task in tasks.difference(replay_tasks) if task)
    if missing_replays:
        add_finding(
            findings,
            "error",
            "task_without_tutorial_reproduction_plan",
            "Some task_type entries have no tutorial reproduction plan.",
            "tutorial_reproduction_plan",
        )
    replay_job_tasks = {job.get("task_type") for job in execution_replay_orchestrator.get("jobs", [])}
    missing_replay_jobs = sorted(str(task) for task in tasks.difference(replay_job_tasks) if task)
    if missing_replay_jobs:
        add_finding(
            findings,
            "error",
            "task_without_execution_replay_job",
            "Some task_type entries have no execution replay orchestration job.",
            "execution_replay_orchestrator",
        )
    if tutorial_reproduction_plan.get("execution_grounded_requested"):
        if tutorial_reproduction_plan.get("replay_count", 0) == 0:
            add_finding(
                findings,
                "error",
                "execution_grounding_without_replay_plan",
                "Execution grounding was requested, but no tutorial replay plan was produced.",
                "tutorial_reproduction_plan",
            )
        if tutorial_reproduction_plan.get("tutorial_count", 0) == 0:
            add_finding(
                findings,
                "error",
                "execution_grounding_without_tutorial_plan_sources",
                "Execution grounding was requested, but no tutorial/example steps are available for replay planning.",
                "tutorial_reproduction_plan",
            )

    contract_traceability = artifacts.get("contract_traceability") or {}
    traceability_records = contract_traceability.get("records", [])
    traceability_tasks = {record.get("task_type") for record in traceability_records}
    missing_traceability = sorted(str(task) for task in tasks.difference(traceability_tasks) if task)
    if missing_traceability:
        add_finding(
            findings,
            "error",
            "task_without_contract_traceability",
            "Some task_type entries have no contract traceability records.",
            "contract_traceability",
        )
    if contract_traceability.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "contract_traceability_failed",
            "Contract traceability failed.",
            "contract_traceability",
        )

    lineage_graph = artifacts.get("lineage_graph") or {}
    if lineage_graph.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "lineage_graph_failed",
            "Lineage graph failed.",
            "lineage_graph",
        )
    lineage_nodes = {node.get("id") for node in lineage_graph.get("nodes", [])}
    lineage_edges = lineage_graph.get("edges", [])
    if "lineage_graph" in required:
        if not lineage_nodes:
            add_finding(
                findings,
                "error",
                "empty_lineage_nodes",
                "Lineage graph has no nodes.",
                "lineage_graph",
            )
        if not lineage_edges:
            add_finding(
                findings,
                "error",
                "empty_lineage_edges",
                "Lineage graph has no edges.",
                "lineage_graph",
            )
        for task in sorted(str(task) for task in tasks if task):
            if f"task:{task}" not in lineage_nodes:
                add_finding(
                    findings,
                    "error",
                    "task_missing_from_lineage_graph",
                    "Task_type is missing from lineage graph.",
                    "lineage_graph",
                )

    acceptance_suite = artifacts.get("acceptance_suite") or {}
    acceptance_cases = acceptance_suite.get("cases", [])
    for task in sorted(str(task) for task in tasks if task):
        task_cases = [case for case in acceptance_cases if case.get("task_type") == task]
        task_kinds = {case.get("kind") for case in task_cases}
        for required_kind in (
            "task_type_routing",
            "input_output_contract",
            "contract_traceability",
            "execution_boundary",
            "tutorial_reproduction_plan",
        ):
            if required_kind not in task_kinds:
                add_finding(
                    findings,
                    "error",
                    "task_missing_acceptance_case",
                    f"Task_type is missing required acceptance case kind: {required_kind}.",
                    "acceptance_suite",
                )
        if not any(kind == "structured_refusal" for kind in task_kinds):
            add_finding(
                findings,
                "error",
                "task_missing_refusal_case",
                "Task_type is missing a structured refusal acceptance case.",
                "acceptance_suite",
            )

    eval_splits = artifacts.get("eval_splits") or {}
    if eval_splits.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "eval_splits_failed",
            "Static eval splits failed.",
            "eval_splits",
        )
    split_counts = eval_splits.get("split_counts", {})
    for split in ("train", "selection", "test"):
        if split_counts.get(split, 0) == 0:
            add_finding(
                findings,
                "error",
                "empty_eval_split",
                f"Eval split has no cases: {split}.",
                "eval_splits",
            )
    split_case_ids = {case.get("source_case_id") for case in eval_splits.get("cases", [])}
    missing_acceptance_split = [
        str(case.get("case_id"))
        for case in acceptance_cases
        if case.get("case_id") and case.get("case_id") not in split_case_ids
    ]
    if missing_acceptance_split:
        add_finding(
            findings,
            "error",
            "acceptance_case_missing_from_eval_splits",
            "Some acceptance cases are missing from eval_splits.",
            "eval_splits",
        )

    eval_result_judge = artifacts.get("eval_result_judge") or {}
    if eval_result_judge.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "eval_result_judge_failed",
            "Supplied eval results failed against static expectations.",
            "eval_result_judge",
        )
    eval_leakage_audit = artifacts.get("eval_leakage_audit") or {}
    if eval_leakage_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "eval_leakage_audit_failed",
            "Eval leakage audit failed.",
            "eval_leakage_audit",
        )
    agent_rollout_result_judge = artifacts.get("agent_rollout_result_judge") or {}
    if agent_rollout_result_judge.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "agent_rollout_result_judge_failed",
            "Supplied agent rollout results failed against static expectations.",
            "agent_rollout_result_judge",
        )
    e2e_acceptance = artifacts.get("e2e_acceptance") or {}
    if e2e_acceptance.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "e2e_acceptance_failed",
            "E2E acceptance plan or supplied results failed.",
            "e2e_acceptance",
        )
    if e2e_acceptance and e2e_acceptance.get("plan_only") is not True:
        add_finding(
            findings,
            "error",
            "e2e_acceptance_not_plan_only",
            "E2E acceptance must not run package code or launch agents.",
            "e2e_acceptance",
        )
    if (
        "e2e_acceptance" in required
        and e2e_acceptance.get("scenario_count") is not None
        and e2e_acceptance.get("scenario_count") != len(e2e_acceptance.get("scenarios", []))
    ):
        add_finding(
            findings,
            "error",
            "e2e_acceptance_scenario_count_mismatch",
            "scenario_count must equal the number of E2E scenarios.",
            "e2e_acceptance",
        )
    if (
        "e2e_acceptance" in required
        and e2e_acceptance.get("result_count") is not None
        and e2e_acceptance.get("result_count") != len(e2e_acceptance.get("result_records", []))
    ):
        add_finding(
            findings,
            "error",
            "e2e_acceptance_result_count_mismatch",
            "result_count must equal the number of E2E result records.",
            "e2e_acceptance",
        )
    if (
        "e2e_acceptance" in required
        and e2e_acceptance.get("result_template_count") is not None
        and e2e_acceptance.get("result_template_count") != len(e2e_acceptance.get("result_templates", []))
    ):
        add_finding(
            findings,
            "error",
            "e2e_acceptance_result_template_count_mismatch",
            "result_template_count must equal the number of E2E result templates.",
            "e2e_acceptance",
        )
    if (
        "e2e_acceptance" in required
        and e2e_acceptance.get("scenario_count") is not None
        and e2e_acceptance.get("result_template_count") is not None
        and e2e_acceptance.get("scenario_count") != e2e_acceptance.get("result_template_count")
    ):
        add_finding(
            findings,
            "error",
            "e2e_acceptance_template_scenario_mismatch",
            "Each E2E scenario must have one result template.",
            "e2e_acceptance",
        )
    if (
        "e2e_acceptance" in required
        and e2e_acceptance.get("required_scenario_count") is not None
        and e2e_acceptance.get("required_scenario_count")
        != sum(1 for scenario in e2e_acceptance.get("scenarios", []) if scenario.get("required_for_full_e2e"))
    ):
        add_finding(
            findings,
            "error",
            "e2e_acceptance_required_count_mismatch",
            "required_scenario_count must equal the number of required E2E scenarios.",
            "e2e_acceptance",
        )
    if e2e_acceptance.get("require_e2e_acceptance") and e2e_acceptance.get("e2e_verdict") != "passed":
        add_finding(
            findings,
            "error",
            "required_e2e_acceptance_not_passed",
            "E2E acceptance is required but full E2E verdict is not passed.",
            "e2e_acceptance",
        )
    if "e2e_acceptance" in required and e2e_acceptance:
        e2e_task_scenarios = {
            str(scenario.get("scenario_id") or "").removeprefix("e2e:task-type:")
            for scenario in e2e_acceptance.get("scenarios", [])
            if scenario.get("kind") == "task_type_acceptance"
        }
        missing_e2e_task_scenarios = sorted(
            str(task)
            for task in tasks
            if task and slugify(str(task)) not in e2e_task_scenarios
        )
        if missing_e2e_task_scenarios:
            add_finding(
                findings,
                "error",
                "task_without_e2e_acceptance_scenario",
                "Some task_type entries have no E2E acceptance scenario.",
                "e2e_acceptance",
            )

    smoke_test_plan = artifacts.get("smoke_test_plan") or {}
    if smoke_test_plan.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "smoke_test_plan_failed",
            "Smoke test plan or supplied results failed.",
            "smoke_test_plan",
        )
    if smoke_test_plan and smoke_test_plan.get("plan_only") is not True:
        add_finding(
            findings,
            "error",
            "smoke_test_plan_not_plan_only",
            "Smoke test planning must not run package code or launch agents.",
            "smoke_test_plan",
        )
    if (
        "smoke_test_plan" in required
        and smoke_test_plan.get("scenario_count") is not None
        and smoke_test_plan.get("scenario_count") != len(smoke_test_plan.get("scenarios", []))
    ):
        add_finding(
            findings,
            "error",
            "smoke_test_plan_scenario_count_mismatch",
            "scenario_count must equal the number of smoke test scenarios.",
            "smoke_test_plan",
        )
    if (
        "smoke_test_plan" in required
        and smoke_test_plan.get("result_count") is not None
        and smoke_test_plan.get("result_count") != len(smoke_test_plan.get("result_records", []))
    ):
        add_finding(
            findings,
            "error",
            "smoke_test_plan_result_count_mismatch",
            "result_count must equal the number of smoke test result records.",
            "smoke_test_plan",
        )
    if smoke_test_plan.get("require_smoke_test") and smoke_test_plan.get("smoke_verdict") != "passed":
        add_finding(
            findings,
            "error",
            "required_smoke_test_not_passed",
            "Smoke testing is required but the smoke verdict is not passed.",
            "smoke_test_plan",
        )
    if "smoke_test_plan" in required and smoke_test_plan:
        smoke_task_scenarios = {
            str(scenario.get("scenario_id") or "").removeprefix("smoke:task:")
            for scenario in smoke_test_plan.get("scenarios", [])
            if str(scenario.get("scenario_id") or "").startswith("smoke:task:")
        }
        missing_smoke_task_scenarios = sorted(
            str(task)
            for task in tasks
            if task and slugify(str(task)) not in smoke_task_scenarios
        )
        if missing_smoke_task_scenarios:
            add_finding(
                findings,
                "error",
                "task_without_smoke_test_scenario",
                "Some task_type entries have no smoke test scenario.",
                "smoke_test_plan",
            )

    candidate_selection_audit = artifacts.get("candidate_selection_audit") or {}
    if "candidate_selection_audit" in required and candidate_selection_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "candidate_selection_audit_failed",
            "Candidate selection audit failed.",
            "candidate_selection_audit",
        )
    candidate_registry = artifacts.get("candidate_registry") or {}
    if "candidate_registry" in required and candidate_registry.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "candidate_registry_failed",
            "Candidate registry failed.",
            "candidate_registry",
        )
    if (
        "candidate_selection_audit" in required
        and candidate_selection_audit
        and candidate_selection_audit.get("selected_version_id") != candidate_registry.get("active_version_id")
    ):
        add_finding(
            findings,
            "error",
            "candidate_selection_active_version_mismatch",
            "Candidate selection must match the registry active version.",
            "candidate_selection_audit",
        )
    candidate_promotion_audit = artifacts.get("candidate_promotion_audit") or {}
    if "candidate_promotion_audit" in required and candidate_promotion_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "candidate_promotion_audit_failed",
            "Candidate promotion audit failed.",
            "candidate_promotion_audit",
        )
    if (
        "candidate_promotion_audit" in required
        and candidate_promotion_audit
        and candidate_selection_audit
        and candidate_promotion_audit.get("candidate_selection_audit_status") != candidate_selection_audit.get("status")
    ):
        add_finding(
            findings,
            "error",
            "candidate_promotion_selection_status_mismatch",
            "Candidate promotion audit must record the candidate selection audit status.",
            "candidate_promotion_audit",
        )

    final_candidate_audit = artifacts.get("final_candidate_audit") or {}
    if "final_candidate_audit" in required and final_candidate_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "final_candidate_audit_failed",
            "Final candidate audit failed.",
            "final_candidate_audit",
        )
    if (
        "final_candidate_audit" in required
        and final_candidate_audit
        and final_candidate_audit.get("active_version_id") != candidate_registry.get("active_version_id")
    ):
        add_finding(
            findings,
            "error",
            "final_candidate_active_version_mismatch",
            "Final candidate audit must point to the active registry version.",
            "final_candidate_audit",
        )

    backend_contract = artifacts.get("backend_contract") or {}
    if backend_contract.get("status") != "supported":
        add_finding(
            findings,
            "error",
            "unsupported_backend",
            "Requested backend is not implemented.",
            "backend_contract",
        )
    backend_extension_audit = artifacts.get("backend_extension_audit") or {}
    if backend_extension_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "backend_extension_audit_failed",
            "Backend extension boundary audit failed.",
            "backend_extension_audit",
        )

    environment_install_plan = artifacts.get("environment_install_plan") or {}
    if environment_install_plan.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "environment_install_plan_failed",
            "Environment install planning failed.",
            "environment_install_plan",
        )
    if environment_install_plan and not environment_install_plan.get("plan_only"):
        add_finding(
            findings,
            "error",
            "environment_install_plan_not_plan_only",
            "Environment install plan must be plan-only.",
            "environment_install_plan",
        )

    grounding_gate = artifacts.get("grounding_gate") or {}
    if grounding_gate.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "grounding_gate_failed",
            "API/interface grounding gate failed.",
            "grounding_gate",
        )

    api_surface_audit = artifacts.get("api_surface_audit") or {}
    if api_surface_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "api_surface_audit_failed",
            "Rendered API surface audit failed.",
            "api_surface_audit",
        )
    key_api_coverage_audit = artifacts.get("key_api_coverage_audit") or {}
    if key_api_coverage_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "key_api_coverage_audit_failed",
            "Explicit key API coverage audit failed.",
            "key_api_coverage_audit",
        )

    code_fence_audit = artifacts.get("code_fence_audit") or {}
    if code_fence_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "code_fence_audit_failed",
            "Generated child skill code fences failed audit.",
            "code_fence_audit",
        )

    public_safety_audit = artifacts.get("public_safety_audit") or {}
    if public_safety_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "public_safety_audit_failed",
            "Generated public child skill failed safety audit.",
            "public_safety_audit",
        )

    review_summary = artifacts.get("review_summary") or {}
    review_evolution = artifacts.get("review_evolution") or {}
    review_evolution_plot = artifacts.get("review_evolution_plot") or {}
    review_iteration_log = artifacts.get("review_iteration_log") or {}
    if (
        "review_evolution" in required
        and review_summary.get("iteration_count") is not None
        and review_evolution.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_evolution.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_evolution_mismatch",
            "review_summary and review_evolution disagree on iteration_count.",
            "review_evolution",
        )
    if "review_evolution_plot" in required:
        if review_evolution_plot.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "review_evolution_plot_failed",
                "Review evolution plot metadata failed.",
                "review_evolution_plot",
            )
        if not str(review_evolution_plot.get("svg_path") or "").endswith(".svg"):
            add_finding(
                findings,
                "error",
                "review_evolution_plot_missing_svg_path",
                "Review evolution plot must point to an SVG file.",
                "review_evolution_plot",
            )
        if (
            review_evolution.get("iteration_count") is not None
            and review_evolution_plot.get("iteration_count") is not None
            and review_evolution.get("iteration_count") != review_evolution_plot.get("iteration_count")
        ):
            add_finding(
                findings,
                "error",
                "review_evolution_plot_iteration_mismatch",
                "review_evolution and review_evolution_plot disagree on iteration_count.",
                "review_evolution_plot",
            )
    if "review_iteration_log" in required:
        if review_iteration_log.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "review_iteration_log_failed",
                "Review iteration log metadata failed.",
                "review_iteration_log",
            )
        if not str(review_iteration_log.get("markdown_path") or "").endswith(".md"):
            add_finding(
                findings,
                "error",
                "review_iteration_log_missing_markdown_path",
                "Review iteration log must point to a Markdown file.",
                "review_iteration_log",
            )
        if (
            review_summary.get("iteration_count") is not None
            and review_iteration_log.get("iteration_count") is not None
            and review_summary.get("iteration_count") != review_iteration_log.get("iteration_count")
        ):
            add_finding(
                findings,
                "error",
                "review_iteration_log_mismatch",
                "review_summary and review_iteration_log disagree on iteration_count.",
                "review_iteration_log",
            )
    review_prompt_contracts = artifacts.get("review_prompt_contracts") or {}
    if review_prompt_contracts.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_prompt_contracts_failed",
            "Review prompt/state contracts failed.",
            "review_prompt_contracts",
        )
    if (
        "review_prompt_contracts" in required
        and review_summary.get("iteration_count") is not None
        and review_prompt_contracts.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_prompt_contracts.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_prompt_contracts_mismatch",
            "review_summary and review_prompt_contracts disagree on iteration_count.",
            "review_prompt_contracts",
        )

    review_prompt_materials = artifacts.get("review_prompt_materials") or {}
    if review_prompt_materials.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_prompt_materials_failed",
            "Review prompt materials failed.",
            "review_prompt_materials",
        )
    if (
        "review_prompt_materials" in required
        and review_prompt_contracts.get("contract_count") is not None
        and review_prompt_materials.get("material_count") is not None
        and review_prompt_contracts.get("contract_count") != review_prompt_materials.get("material_count")
    ):
        add_finding(
            findings,
            "error",
            "review_prompt_materials_contract_mismatch",
            "review_prompt_contracts and review_prompt_materials disagree on role/material count.",
            "review_prompt_materials",
        )

    review_prompt_suite_audit = artifacts.get("review_prompt_suite_audit") or {}
    if review_prompt_suite_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_prompt_suite_audit_failed",
            "Review prompt suite audit failed.",
            "review_prompt_suite_audit",
        )
    if (
        "review_prompt_suite_audit" in required
        and review_summary.get("iteration_count") is not None
        and review_prompt_suite_audit.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_prompt_suite_audit.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_prompt_suite_audit_mismatch",
            "review_summary and review_prompt_suite_audit disagree on iteration_count.",
            "review_prompt_suite_audit",
        )

    review_cursor = artifacts.get("review_cursor") or {}
    if review_cursor.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_cursor_failed",
            "Review cursor state failed.",
            "review_cursor",
        )
    if (
        "review_cursor" in required
        and review_summary.get("iteration_count") is not None
        and review_cursor.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_cursor.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_cursor_mismatch",
            "review_summary and review_cursor disagree on iteration_count.",
            "review_cursor",
        )
    patch_application = artifacts.get("patch_application") or {}
    if patch_application.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "patch_application_failed",
            "Patch application audit failed.",
            "patch_application",
        )
    if (
        "patch_application" in required
        and review_summary.get("iteration_count") is not None
        and patch_application.get("iteration_count") is not None
        and review_summary.get("iteration_count") != patch_application.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "patch_application_mismatch",
            "review_summary and patch_application disagree on iteration_count.",
            "patch_application",
        )

    review_remediation_audit = artifacts.get("review_remediation_audit") or {}
    if review_remediation_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_remediation_audit_failed",
            "Review remediation audit failed.",
            "review_remediation_audit",
        )
    if (
        "review_remediation_audit" in required
        and review_summary.get("iteration_count") is not None
        and review_remediation_audit.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_remediation_audit.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_remediation_audit_mismatch",
            "review_summary and review_remediation_audit disagree on iteration_count.",
            "review_remediation_audit",
        )

    review_optimizer_state = artifacts.get("review_optimizer_state") or {}
    if review_optimizer_state.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_optimizer_state_failed",
            "Review optimizer state failed.",
            "review_optimizer_state",
        )
    if (
        "review_optimizer_state" in required
        and review_summary.get("iteration_count") is not None
        and review_optimizer_state.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_optimizer_state.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_optimizer_state_mismatch",
            "review_summary and review_optimizer_state disagree on iteration_count.",
            "review_optimizer_state",
        )
    if "review_optimizer_state" in required and review_optimizer_state.get("strict_improvement_gate") is not True:
        add_finding(
            findings,
            "error",
            "review_optimizer_state_missing_strict_gate",
            "review_optimizer_state must declare strict_improvement_gate=true.",
            "review_optimizer_state",
        )

    patch_safety_audit = artifacts.get("patch_safety_audit") or {}
    if patch_safety_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "patch_safety_audit_failed",
            "Patch safety audit failed.",
            "patch_safety_audit",
        )
    patch_operation_contracts = artifacts.get("patch_operation_contracts") or {}
    if patch_operation_contracts.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "patch_operation_contracts_failed",
            "Patch operation contracts failed.",
            "patch_operation_contracts",
        )
    if (
        "patch_operation_contracts" in required
        and review_summary.get("iteration_count") is not None
        and patch_operation_contracts.get("iteration_count") is not None
        and review_summary.get("iteration_count") != patch_operation_contracts.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "patch_operation_contracts_mismatch",
            "review_summary and patch_operation_contracts disagree on iteration_count.",
            "patch_operation_contracts",
        )

    review_discipline_audit = artifacts.get("review_discipline_audit") or {}
    if review_discipline_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_discipline_audit_failed",
            "Review-loop discipline audit failed.",
            "review_discipline_audit",
        )
    if (
        "review_discipline_audit" in required
        and review_summary.get("iteration_count") is not None
        and review_discipline_audit.get("iteration_count") is not None
        and review_summary.get("iteration_count") != review_discipline_audit.get("iteration_count")
    ):
        add_finding(
            findings,
            "error",
            "review_discipline_audit_mismatch",
            "review_summary and review_discipline_audit disagree on iteration_count.",
            "review_discipline_audit",
        )

    rubric_grounding_audit = artifacts.get("rubric_grounding_audit") or {}
    if rubric_grounding_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "rubric_grounding_audit_failed",
            "Rubric grounding audit failed.",
            "rubric_grounding_audit",
        )
    if (
        "rubric_grounding_audit" in required
        and review_summary.get("iteration_count") is not None
        and rubric_grounding_audit.get("record_count") is not None
        and rubric_grounding_audit.get("record_count") != review_summary.get("iteration_count", 0) + 1
    ):
        add_finding(
            findings,
            "error",
            "rubric_grounding_audit_record_mismatch",
            "rubric_grounding_audit must include final_score plus one record per review iteration.",
            "rubric_grounding_audit",
        )

    review_trajectory_audit = artifacts.get("review_trajectory_audit") or {}
    if review_trajectory_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "review_trajectory_audit_failed",
            "Review trajectory integrity audit failed.",
            "review_trajectory_audit",
        )

    draft_readiness = artifacts.get("draft_readiness") or {}
    child_metadata_audit = artifacts.get("child_metadata_audit") or {}
    if child_metadata_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "child_metadata_audit_failed",
            "Child skill metadata or one-skill trigger shape failed audit.",
            "child_metadata_audit",
        )
    child_package_purity_audit = artifacts.get("child_package_purity_audit") or {}
    if child_package_purity_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "child_package_purity_audit_failed",
            "Public child skill contains files outside the lightweight package contract.",
            "child_package_purity_audit",
        )
    if draft_readiness.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "draft_readiness_failed",
            "Generated child skill still contains draft placeholders or template values.",
            "draft_readiness",
        )

    output_boundary_audit = artifacts.get("output_boundary_audit") or {}
    if output_boundary_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "output_boundary_audit_failed",
            "Generated child skill violates build output or public package boundaries.",
            "output_boundary_audit",
        )
    if output_boundary_audit.get("output_dir_inside_install_root"):
        add_finding(
            findings,
            "error",
            "output_dir_inside_skill_install_root",
            "Build output_dir must not be inside a likely Codex skill install root.",
            "output_boundary_audit",
        )

    skill_update_plan = artifacts.get("skill_update_plan") or {}
    if skill_update_plan.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "skill_update_plan_failed",
            "Discovery reuse, update, or create plan failed.",
            "skill_update_plan",
        )
    skill_update_audit = artifacts.get("skill_update_audit") or {}
    if skill_update_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "skill_update_audit_failed",
            "Skill update safety audit failed.",
            "skill_update_audit",
        )
    if skill_update_audit and not skill_update_audit.get("plan_only"):
        add_finding(
            findings,
            "error",
            "skill_update_audit_not_plan_only",
            "Skill update audit must be plan-only.",
            "skill_update_audit",
        )
    if skill_update_plan and not skill_update_plan.get("plan_only"):
        add_finding(
            findings,
            "error",
            "skill_update_plan_not_plan_only",
            "Skill update plan must not modify existing skills.",
            "skill_update_plan",
        )
    discovery_report = artifacts.get("discovery_report") or {}
    if discovery_report.get("decision") == "reuse":
        if skill_update_plan.get("recommended_action") != "reuse_existing":
            add_finding(
                findings,
                "error",
                "reuse_decision_without_reuse_plan",
                "Discovery reuse decision requires a reuse_existing skill update plan.",
                "skill_update_plan",
            )
        if skill_update_plan.get("missing_task_types"):
            add_finding(
                findings,
                "error",
                "reuse_plan_has_task_gaps",
                "Reuse plan must not list missing task_type entries.",
                "skill_update_plan",
            )
    if discovery_report.get("decision") == "update":
        if skill_update_plan.get("recommended_action") != "update_existing":
            add_finding(
                findings,
                "error",
                "update_decision_without_update_plan",
                "Discovery update decision requires an update_existing skill update plan.",
                "skill_update_plan",
            )
        if not skill_update_plan.get("target_existing_skill_path"):
            add_finding(
                findings,
                "error",
                "update_plan_missing_target",
                "Skill update plan must name the target existing skill path.",
                "skill_update_plan",
            )
        if not skill_update_plan.get("missing_task_types"):
            add_finding(
                findings,
                "error",
                "update_plan_missing_task_gaps",
                "Skill update plan must list missing task_type entries.",
                "skill_update_plan",
            )

    if discovery_report.get("decision") == "create" and skill_update_plan.get("recommended_action") != "create_new":
        add_finding(
            findings,
            "error",
            "create_decision_without_create_plan",
            "Discovery create decision requires a create_new skill update plan.",
            "skill_update_plan",
        )

    forward_test_plan = artifacts.get("forward_test_plan") or {}
    if forward_test_plan.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "forward_test_plan_failed",
            "Generated child skill lacks a usable plan-only forward-test suite.",
            "forward_test_plan",
        )
    if forward_test_plan and not forward_test_plan.get("plan_only"):
        add_finding(
            findings,
            "error",
            "forward_test_plan_not_plan_only",
            "Forward-test plan must not execute package code.",
            "forward_test_plan",
        )
    forward_test_tasks = {
        scenario.get("task_type")
        for scenario in forward_test_plan.get("scenarios", [])
        if scenario.get("task_type") not in (None, "global", "ambiguity")
    }
    missing_forward_tests = sorted(str(task) for task in tasks.difference(forward_test_tasks) if task)
    if missing_forward_tests:
        add_finding(
            findings,
            "error",
            "task_without_forward_test",
            "Some task_type entries have no forward-test scenario.",
            "forward_test_plan",
        )

    agent_rollout_harness = artifacts.get("agent_rollout_harness") or {}
    if agent_rollout_harness.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "agent_rollout_harness_failed",
            "Plan-only agent rollout harness failed.",
            "agent_rollout_harness",
        )
    if agent_rollout_harness and not agent_rollout_harness.get("plan_only"):
        add_finding(
            findings,
            "error",
            "agent_rollout_harness_not_plan_only",
            "Agent rollout harness must not execute agents or package code.",
            "agent_rollout_harness",
        )
    if (
        "agent_rollout_harness" in required
        and agent_rollout_harness.get("rollout_count") is not None
        and agent_rollout_harness.get("rollout_count") != len(agent_rollout_harness.get("cases", []))
    ):
        add_finding(
            findings,
            "error",
            "agent_rollout_count_mismatch",
            "rollout_count must equal the number of rollout cases.",
            "agent_rollout_harness",
        )

    agent_rollout_audit = artifacts.get("agent_rollout_audit") or {}
    if agent_rollout_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "agent_rollout_audit_failed",
            "Plan-only agent rollout audit failed.",
            "agent_rollout_audit",
        )
    if agent_rollout_audit and not agent_rollout_audit.get("plan_only"):
        add_finding(
            findings,
            "error",
            "agent_rollout_audit_not_plan_only",
            "Agent rollout audit must be plan-only.",
            "agent_rollout_audit",
        )
    if (
        "agent_rollout_audit" in required
        and forward_test_plan.get("scenario_count") is not None
        and agent_rollout_audit.get("scenario_count") is not None
        and forward_test_plan.get("scenario_count") != agent_rollout_audit.get("scenario_count")
    ):
        add_finding(
            findings,
            "error",
            "agent_rollout_audit_scenario_mismatch",
            "forward_test_plan and agent_rollout_audit disagree on scenario_count.",
            "agent_rollout_audit",
        )
    if (
        "agent_rollout_audit" in required
        and agent_rollout_harness.get("rollout_count") is not None
        and agent_rollout_audit.get("rollout_count") is not None
        and agent_rollout_harness.get("rollout_count") != agent_rollout_audit.get("rollout_count")
    ):
        add_finding(
            findings,
            "error",
            "agent_rollout_audit_rollout_mismatch",
            "agent_rollout_harness and agent_rollout_audit disagree on rollout_count.",
            "agent_rollout_audit",
        )

    claim_consistency_audit = artifacts.get("claim_consistency_audit") or {}
    if claim_consistency_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "claim_consistency_audit_failed",
            "Rendered child-skill claims do not match build artifacts.",
            "claim_consistency_audit",
        )
    biological_claim_boundary_audit = artifacts.get("biological_claim_boundary_audit") or {}
    if biological_claim_boundary_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "biological_claim_boundary_audit_failed",
            "Rendered child skill contains unsupported high-risk biological claims or missing claim-boundary refusals.",
            "biological_claim_boundary_audit",
        )

    child_reference_coverage = artifacts.get("child_reference_coverage") or {}
    if child_reference_coverage.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "child_reference_coverage_failed",
            "Rendered child references do not cover required build artifacts.",
            "child_reference_coverage",
        )

    routing_metadata_audit = artifacts.get("routing_metadata_audit") or {}
    if routing_metadata_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "routing_metadata_audit_failed",
            "Task_type routing metadata failed audit.",
            "routing_metadata_audit",
        )

    workflow_invariant_audit = artifacts.get("workflow_invariant_audit") or {}
    if workflow_invariant_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "workflow_invariant_audit_failed",
            "First-principles workflow invariants failed.",
            "workflow_invariant_audit",
        )

    requirement_coverage = artifacts.get("requirement_coverage") or {}
    if requirement_coverage.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "requirement_coverage_failed",
            "Core requirement coverage matrix failed.",
            "requirement_coverage",
        )

    completion_evidence_audit = artifacts.get("completion_evidence_audit") or {}
    if "completion_evidence_audit" in required and completion_evidence_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "completion_evidence_audit_failed",
            "Completion evidence audit failed.",
            "completion_evidence_audit",
        )
    if completion_evidence_audit.get("can_claim_full_goal_complete") and completion_evidence_audit.get("e2e_verdict") != "passed":
        add_finding(
            findings,
            "error",
            "full_completion_claim_without_passing_e2e",
            "Full completion cannot be claimed unless E2E verdict is passed.",
            "completion_evidence_audit",
        )
    if completion_evidence_audit.get("claim_verdict") == "full_goal_complete" and completion_evidence_audit.get("missing_evidence"):
        add_finding(
            findings,
            "error",
            "full_completion_claim_has_missing_evidence",
            "Full completion claim must not list missing evidence.",
            "completion_evidence_audit",
        )

    acceptance_handoff = artifacts.get("acceptance_handoff") or {}
    if "acceptance_handoff" in required and acceptance_handoff.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "acceptance_handoff_failed",
            "Acceptance handoff failed.",
            "acceptance_handoff",
        )
    if acceptance_handoff and acceptance_handoff.get("plan_only") is not True:
        add_finding(
            findings,
            "error",
            "acceptance_handoff_not_plan_only",
            "Acceptance handoff must be plan-only.",
            "acceptance_handoff",
        )
    if (
        "acceptance_handoff" in required
        and acceptance_handoff.get("handoff_item_count") is not None
        and acceptance_handoff.get("handoff_item_count") != len(acceptance_handoff.get("handoff_items", []))
    ):
        add_finding(
            findings,
            "error",
            "acceptance_handoff_item_count_mismatch",
            "handoff_item_count must equal the number of handoff items.",
            "acceptance_handoff",
        )
    target_fields = set(acceptance_handoff.get("target_request_fields", []))
    required_target_fields = {"agent_rollout_results", "execution_replay_results", "e2e_acceptance_results"}
    if "acceptance_handoff" in required and not required_target_fields.issubset(target_fields):
        add_finding(
            findings,
            "error",
            "acceptance_handoff_missing_target_fields",
            "Acceptance handoff must name all external result request fields.",
            "acceptance_handoff",
        )
    if acceptance_handoff.get("publish_manifest_supplied") and not acceptance_handoff.get("publish_manifest_status"):
        add_finding(
            findings,
            "error",
            "acceptance_handoff_missing_publish_status",
            "Acceptance handoff with supplied publish manifest must record publish_manifest_status.",
            "acceptance_handoff",
        )

    architecture_completeness_audit = artifacts.get("architecture_completeness_audit") or {}
    if "architecture_completeness_audit" in required and architecture_completeness_audit.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "architecture_completeness_audit_failed",
            "Architecture completeness audit failed.",
            "architecture_completeness_audit",
        )

    artifact_closure_audit = artifacts.get("artifact_closure_audit") or {}
    if "artifact_closure_audit" in required and artifact_closure_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "artifact_closure_audit_failed",
            "Artifact closure audit failed.",
            "artifact_closure_audit",
        )

    score_report = artifacts.get("score_report") or {}
    if "score_report" in required and score_report.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "score_report_failed",
            "Run-level score report failed.",
            "score_report",
        )

    candidate_evolution_audit = artifacts.get("candidate_evolution_audit") or {}
    if "candidate_evolution_audit" in required and candidate_evolution_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "candidate_evolution_audit_failed",
            "Candidate evolution audit failed.",
            "candidate_evolution_audit",
        )

    release_action_audit = artifacts.get("release_action_audit") or {}
    if "release_action_audit" in required and release_action_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "release_action_audit_failed",
            "Release action audit failed.",
            "release_action_audit",
        )

    run_manifest = artifacts.get("run_manifest") or {}
    codex_publish_adapter = artifacts.get("codex_publish_adapter") or {}
    if "codex_publish_adapter" in required:
        if codex_publish_adapter.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "codex_publish_adapter_failed",
                "Codex publish adapter failed.",
                "codex_publish_adapter",
            )
        if codex_publish_adapter and not codex_publish_adapter.get("plan_only"):
            add_finding(
                findings,
                "error",
                "codex_publish_adapter_not_plan_only",
                "Codex publish adapter must not copy or install files.",
                "codex_publish_adapter",
            )
        if codex_publish_adapter and codex_publish_adapter.get("target_agent") != "codex":
            add_finding(
                findings,
                "error",
                "codex_publish_adapter_wrong_target",
                "Codex publish adapter must target Codex.",
                "codex_publish_adapter",
            )
    install_readiness = artifacts.get("install_readiness") or {}
    if "install_readiness" in required and install_readiness.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "install_readiness_failed",
            "Generated child skill is not ready to copy into a Codex skills directory.",
            "install_readiness",
        )

    if "run_manifest" in required:
        files = run_manifest.get("files") or []
        if run_manifest.get("file_count", 0) == 0:
            add_finding(
                findings,
                "error",
                "empty_run_manifest",
                "Run manifest must record generated files.",
                "run_manifest",
            )
        if not files:
            add_finding(
                findings,
                "error",
                "missing_run_manifest_files",
                "Run manifest is missing file records.",
                "run_manifest",
            )
        if run_manifest.get("file_count") != len(files):
            add_finding(
                findings,
                "error",
                "run_manifest_file_count_mismatch",
                "Run manifest file_count must match the number of file records.",
                "run_manifest",
            )
        role_counts = {"run_artifact": 0, "child_skill_file": 0, "retained_process_artifact": 0}
        seen_paths: set[str] = set()
        for record in files:
            if not isinstance(record, dict):
                add_finding(
                    findings,
                    "error",
                    "run_manifest_record_not_mapping",
                    "Run manifest file records must be mappings.",
                    "run_manifest",
                )
                continue
            rel = str(record.get("path") or "")
            role = str(record.get("role") or "")
            if not rel:
                add_finding(findings, "error", "run_manifest_record_missing_path", "Run manifest file record is missing path.", "run_manifest")
            elif rel in seen_paths:
                add_finding(findings, "error", "run_manifest_duplicate_path", "Run manifest records a path more than once.", "run_manifest")
            seen_paths.add(rel)
            if rel == "run_manifest.yaml":
                add_finding(findings, "error", "run_manifest_records_itself", "Run manifest must not record itself.", "run_manifest")
            if role not in role_counts:
                add_finding(findings, "error", "run_manifest_invalid_role", "Run manifest record role must be run_artifact, child_skill_file, or retained_process_artifact.", "run_manifest")
            else:
                role_counts[role] += 1
            if not record.get("sha256"):
                add_finding(findings, "error", "run_manifest_missing_sha256", "Run manifest file record is missing SHA-256.", "run_manifest")
            if record.get("bytes") is None:
                add_finding(findings, "error", "run_manifest_missing_bytes", "Run manifest file record is missing byte size.", "run_manifest")
        if run_manifest.get("artifact_count") != role_counts["run_artifact"]:
            add_finding(
                findings,
                "error",
                "run_manifest_artifact_count_mismatch",
                "Run manifest artifact_count must match run_artifact records.",
                "run_manifest",
            )
        if run_manifest.get("child_skill_file_count") != role_counts["child_skill_file"]:
            add_finding(
                findings,
                "error",
                "run_manifest_child_file_count_mismatch",
                "Run manifest child_skill_file_count must match child_skill_file records.",
                "run_manifest",
            )
        if run_manifest.get("retained_process_artifact_count") != role_counts["retained_process_artifact"]:
            add_finding(
                findings,
                "error",
                "run_manifest_retained_process_artifact_count_mismatch",
                "Run manifest retained_process_artifact_count must match retained_process_artifact records.",
                "run_manifest",
            )

    completion_audit = artifacts.get("completion_audit") or {}
    if "completion_audit" in required and completion_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "completion_audit_failed",
            "Final completion audit failed.",
            "completion_audit",
        )

    build_timeline_audit = artifacts.get("build_timeline_audit") or {}
    if "build_timeline_audit" in required and build_timeline_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "build_timeline_audit_failed",
            "Build timeline integrity audit failed.",
            "build_timeline_audit",
        )

    run_scorecard = artifacts.get("run_scorecard") or {}
    if "run_scorecard" in required:
        if run_scorecard.get("status") != "pass":
            add_finding(
                findings,
                "error",
                "run_scorecard_failed",
                "Run scorecard metadata failed.",
                "run_scorecard",
            )
        if not str(run_scorecard.get("markdown_path") or "").endswith(".md"):
            add_finding(
                findings,
                "error",
                "run_scorecard_missing_markdown_path",
                "Run scorecard must point to a Markdown file.",
                "run_scorecard",
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "required_artifacts": required,
        "findings": findings,
    }
