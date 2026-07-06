"""End-to-end orchestration for the paper2skills builder."""

from __future__ import annotations

from pathlib import Path

from acceptance_suite import build_acceptance_suite
from acceptance_handoff import build_acceptance_handoff, render_acceptance_handoff_markdown
from agent_metadata_audit import build_agent_metadata_audit
from agent_rollout_audit import build_agent_rollout_audit
from agent_rollout_harness import build_agent_rollout_harness
from agent_rollout_result_judge import build_agent_rollout_result_judge
from api_grounding import build_api_grounding
from api_surface_audit import audit_api_surface
from architecture_completeness_audit import build_architecture_completeness_audit
from artifact_closure_audit import build_artifact_closure_audit
from artifact_contracts import build_artifact_contracts_report
from artifact_validator import POST_CLEANUP_ARTIFACTS, PRE_PUBLISH_ARTIFACTS, REQUIRED_TOP_LEVEL_ARTIFACTS, validate_artifact_bundle
from backend_contracts import build_backend_contract
from backend_extension_audit import build_backend_extension_audit
from biological_claim_boundary_audit import build_biological_claim_boundary_audit
from builder_baseline_audit import build_builder_baseline_audit
from builder_runtime_audit import build_builder_runtime_audit
from builder_version_audit import build_builder_version_audit
from build_timeline import build_timeline
from build_timeline_audit import build_timeline_audit
from candidate_promotion_audit import build_candidate_promotion_audit
from candidate_evolution_audit import build_candidate_evolution_audit
from candidate_registry import build_candidate_registry
from candidate_selection_audit import build_candidate_selection_audit
from child_reference_coverage import audit_child_reference_coverage
from child_metadata_audit import build_child_metadata_audit
from child_package_purity_audit import build_child_package_purity_audit
from claim_consistency_audit import audit_claim_consistency
from code_fence_audit import audit_child_skill_code_fences
from codex_publish_adapter import build_codex_publish_adapter
from common import append_jsonl, canonical_task_type, ensure_dir, load_data, public_child_skill_path, slugify, write_data, write_text
from completion_audit import build_completion_audit
from completion_evidence_audit import build_completion_evidence_audit
from contract_traceability import build_contract_traceability
from discovery import discovery
from discovery_audit import build_discovery_audit
from discovery_match_audit import build_discovery_match_audit
from discovery_resolution_audit import build_discovery_resolution_audit
from draft_candidate import build_draft_candidates
from draft_readiness import build_draft_readiness
from e2e_acceptance import build_e2e_acceptance
from eval_plan import build_eval_plan
from eval_leakage_audit import build_eval_leakage_audit
from eval_result_judge import build_eval_result_judge
from eval_splits import build_eval_splits
from external_result_contracts import build_external_result_contracts
from execution_plan import build_execution_plan
from execution_replay_orchestrator import build_execution_replay_orchestrator
from evidence_cards import build_evidence_cards
from environment_install_plan import build_environment_install_plan
from environment_miner import build_environment_spec
from execution_grounding import apply_validated_execution_status, write_execution_trace_if_requested
from execution_trace_validation import build_execution_trace_validation
from evidence_claim_taxonomy_audit import build_evidence_claim_taxonomy_audit
from evidence_coverage import build_evidence_coverage
from evidence_precedence import build_evidence_precedence
from final_candidate_audit import build_final_candidate_audit
from forward_test_plan import build_forward_test_plan
from grounding_gate import build_grounding_gate
from install_readiness import build_install_readiness
from interface_inspector import attach_interface_hints, build_interface_grounding
from key_api_coverage_audit import build_key_api_coverage_audit
from lineage_graph import build_lineage_graph
from lint_skill import build_skill_spec, lint_child_skill, publish_manifest
from module_inventory_audit import audit_module_inventory
from output_boundary_audit import build_output_boundary_audit
from output_retention import build_output_retention, is_within, planned_output_retention, refresh_generation_process_doc, refresh_retained_artifacts
from parameter_miner import attach_parameter_constraints, build_parameter_catalog
from patch_application import build_patch_application
from patch_operation_contracts import build_patch_operation_contracts
from patch_safety_audit import audit_patch_safety
from phase_state_audit import build_phase_state_audit
from phase_state import new_phase_state, record_phase
from publish_gate import evaluate_publish_gate
from publish_manifest_audit import build_publish_manifest_audit
from public_origin_audit import build_public_origin_audit
from public_safety_audit import audit_public_child_skill
from protocol_compliance_audit import build_protocol_compliance_audit
from quality_report import build_quality_report
from release_action_audit import build_release_action_audit
from request_audit import build_request_audit
from request_fingerprint import build_request_fingerprint
from request_model import normalize_request
from request_template_audit import build_request_template_audit
from review_cursor import build_review_cursor
from review_discipline_audit import build_review_discipline_audit
from review_evolution import build_review_evolution
from review_evolution_plot import build_review_evolution_plot, render_review_evolution_svg
from review_iteration_log import build_review_iteration_log, render_review_iteration_log_markdown
from review_loop import review_loop
from review_optimizer_state import build_review_optimizer_state
from review_prompt_contracts import build_review_prompt_contracts
from review_prompt_materials import build_review_prompt_materials
from review_prompt_suite_audit import build_review_prompt_suite_audit
from review_remediation_audit import build_review_remediation_audit
from review_trajectory_audit import build_review_trajectory_audit
from release_packager import build_release_package
from requirement_coverage import build_requirement_coverage
from resource_boundary_audit import build_resource_boundary_audit
from resource_inventory import build_resource_inventory
from routing_metadata_audit import audit_routing_metadata
from routing_fixture import build_routing_fixture
from rubric_grounding_audit import build_rubric_grounding_audit
from run_manifest import build_run_manifest
from run_scorecard import build_run_scorecard, render_run_scorecard_markdown
from score_report import build_score_report
from skill_draft import render_child_skill
from skill_package_audit import audit_skill_package
from skill_update_audit import build_skill_update_audit
from skill_update_plan import build_skill_update_plan
from smoke_test_plan import build_smoke_test_plan
from source_fetch import fetch_sources
from source_fetch_boundary_audit import audit_source_fetch_boundaries
from source_grounding import build_source_grounding, source_entries
from source_grounding_audit import audit_source_grounding
from source_ingestion_audit import build_source_ingestion_audit
from source_index import index_sources
from source_manifest import build_source_manifest
from source_parser import build_source_parse_report
from source_parsing_audit import build_source_parsing_audit
from source_parsing_coverage import build_source_parsing_coverage
from task_conflict import build_task_conflict_matrix
from task_partition import attach_operational_recipes, build_task_catalog
from task_partition_audit import build_task_partition_audit
from task_partition_decision_log import build_task_partition_decision_log
from task_router import build_router
from tutorial_miner import build_tutorial_catalog
from tutorial_reproduction_plan import build_tutorial_reproduction_plan
from verification_claim_audit import build_verification_claim_audit
from workflow_invariant_audit import audit_workflow_invariants


FINAL_VALIDATION_ARTIFACTS = [
    name for name in REQUIRED_TOP_LEVEL_ARTIFACTS if name != "artifact_validation"
] + POST_CLEANUP_ARTIFACTS


def final_artifact_dirs(out: Path, publish_manifest_data: dict[str, object] | None) -> list[Path]:
    dirs = []
    retention_path = str((publish_manifest_data or {}).get("output_retention_path") or "")
    if retention_path:
        marker = out / retention_path
        path = marker.parent
        if (
            marker.suffix
            and marker.name == "output_retention.yaml"
            and is_within(marker, out)
            and is_within(path, out)
            and path.resolve(strict=False) != out.resolve(strict=False)
            and path.exists()
            and path.is_dir()
            and marker.exists()
            and marker.is_file()
        ):
            return [path]
        return []
    unique: list[Path] = []
    seen = set()
    for path in dirs:
        key = str(path.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def load_artifacts_for_final_validation(
    out: Path,
    publish_manifest_data: dict[str, object] | None,
    artifact_names: list[str],
) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    retention_dirs = final_artifact_dirs(out, publish_manifest_data)
    for name in artifact_names:
        retained_candidates = [directory / f"{name}.yaml" for directory in retention_dirs]
        candidates = retained_candidates if name == "output_retention" else [out / f"{name}.yaml"] + retained_candidates
        for path in candidates:
            if path.exists() and path.is_file():
                artifacts[name] = load_data(path)
                break
    return artifacts


def build(request_path: Path, out: Path) -> dict:
    request = normalize_request(load_data(request_path), out)
    out = ensure_dir(out)
    request["output_dir"] = str(out)
    request_audit = build_request_audit(request)
    builder_runtime_audit = build_builder_runtime_audit(request, Path(__file__).resolve().parent.parent)
    phase_state = new_phase_state(request)
    record_phase(
        phase_state,
        "request",
        "completed",
        inputs=[str(request_path)],
        outputs=["request.yaml", "request_audit.yaml", "phase_state.yaml"],
        gates=["package_name or method_name present", "repo_url present", "target_agent is codex", "request fields and remote execution boundaries audited"],
    )
    request_fingerprint = build_request_fingerprint(request, request_audit)
    record_phase(
        phase_state,
        "request_fingerprint",
        "completed",
        inputs=["normalized build request", "request_audit.yaml"],
        outputs=["request_fingerprint.yaml"],
        gates=["raw request not stored", "stable request/control hashes recorded", "sensitive fields recorded by path only"],
    )
    external_result_contracts = build_external_result_contracts(request)
    record_phase(
        phase_state,
        "external_result_contracts",
        "completed",
        inputs=["normalized build request"],
        outputs=["external_result_contracts.yaml"],
        gates=["supplied eval and rollout results are schema checked", "judge-only expected values and prompts are not accepted as external result evidence"],
    )
    record_phase(
        phase_state,
        "builder_runtime_audit",
        "completed",
        inputs=["builder skill package files", "templates/build_request.yaml", "scripts/paper2skills.py"],
        outputs=["builder_runtime_audit.yaml"],
        gates=["builder skill metadata present", "build request template complete", "CLI commands exposed"],
    )
    builder_skill_dir = Path(__file__).resolve().parent.parent
    agent_metadata_audit = build_agent_metadata_audit(builder_skill_dir)
    record_phase(
        phase_state,
        "agent_metadata_audit",
        "completed",
        inputs=["SKILL.md", "agents/openai.yaml"],
        outputs=["agent_metadata_audit.yaml"],
        gates=["SKILL.md trigger metadata and UI metadata align", "default prompt names $paper2skills", "metadata covers source-grounded task_type contracts, refusal, and evidence"],
    )
    public_origin_audit = build_public_origin_audit(builder_skill_dir.parent, builder_skill_dir)
    record_phase(
        phase_state,
        "public_origin_audit",
        "completed",
        inputs=["README.md", "builder skill package text files"],
        outputs=["public_origin_audit.yaml"],
        gates=["public files contain no private origin markers", "public files contain no machine-specific execution details", "remote testing examples remain generic"],
    )
    module_inventory_audit = audit_module_inventory(builder_skill_dir, builder_skill_dir.parent)
    record_phase(
        phase_state,
        "module_inventory_audit",
        "completed",
        inputs=["builder skill package files", "README.md", "SKILL.md", "references/builder-architecture.md"],
        outputs=["module_inventory_audit.yaml"],
        gates=["builder modules have docstrings", "module inventory docs mention every script module"],
    )
    builder_baseline_audit = build_builder_baseline_audit(builder_skill_dir, builder_skill_dir.parent)
    record_phase(
        phase_state,
        "builder_baseline_audit",
        "completed",
        inputs=["builder script modules", "README.md", "SKILL.md", "references/builder-architecture.md"],
        outputs=["builder_baseline_audit.yaml"],
        gates=["core engineering baseline families are covered", "baseline modules are documented", "baseline audit remains static and non-executing"],
    )
    skill_package_audit = audit_skill_package(builder_skill_dir)
    record_phase(
        phase_state,
        "skill_package_audit",
        "completed",
        inputs=["builder skill package files"],
        outputs=["skill_package_audit.yaml"],
        gates=["builder package uses standard Codex skill shape", "no auxiliary docs or cache files inside skill package"],
    )
    request_template_audit = build_request_template_audit(builder_skill_dir)
    record_phase(
        phase_state,
        "request_template_audit",
        "completed",
        inputs=["templates/build_request.yaml", "scripts/request_model.py", "scripts/request_audit.py", "scripts/builder_runtime_audit.py"],
        outputs=["request_template_audit.yaml"],
        gates=["template covers normalized request fields", "template stays generic", "runtime required template fields cover request defaults"],
    )
    requested_task_types = [canonical_task_type(str(item), "task") for item in request.get("requested_task_types", [])]
    discovery_preflight = discovery(request, requested_task_types or ["general_algorithm_use"])
    record_phase(
        phase_state,
        "discovery_preflight",
        "completed",
        inputs=["normalized build request"],
        outputs=["discovery_preflight.yaml"],
        gates=["existing Codex child skills checked before source parsing"],
    )

    sources = source_entries(request)
    source_grounding = build_source_grounding(request, sources)
    record_phase(
        phase_state,
        "source_grounding",
        "completed",
        inputs=["normalized build request"],
        outputs=["source_grounding.yaml"],
        gates=["evidence priority recorded", "source catalog built"],
    )
    source_fetch_report = fetch_sources(request, sources, out)
    record_phase(
        phase_state,
        "source_fetch",
        "completed",
        inputs=["source_grounding.yaml"],
        outputs=["source_fetch_report.yaml"],
        gates=["no source code execution", "remote downloads require fetch_sources true"],
    )
    source_fetch_boundary_audit = audit_source_fetch_boundaries(request, source_fetch_report)
    record_phase(
        phase_state,
        "source_fetch_boundary_audit",
        "completed",
        inputs=["normalized build request", "source_fetch_report.yaml"],
        outputs=["source_fetch_boundary_audit.yaml"],
        gates=["remote fetch remains opt-in", "fetched and registered source material stays under run sources directory", "unsafe archive extraction blocks publish"],
    )
    source_index = index_sources(
        source_fetch_report,
        max_files=int(request.get("max_index_files") or 500),
        max_bytes=int(request.get("max_index_bytes") or 250000),
    )
    record_phase(
        phase_state,
        "source_index",
        "completed",
        inputs=["source_fetch_report.yaml"],
        outputs=["source_index.yaml"],
        gates=["compact metadata only", "no code execution"],
    )
    resource_inventory = build_resource_inventory(request, source_index)
    record_phase(
        phase_state,
        "resource_inventory",
        "completed",
        inputs=["source_index.yaml"],
        outputs=["resource_inventory.yaml"],
        gates=["model, checkpoint, and external data resources mined statically", "no resource downloads"],
    )
    evidence_cards = build_evidence_cards(request, source_index, source_grounding)
    record_phase(
        phase_state,
        "evidence_cards",
        "completed",
        inputs=["source_index.yaml", "source_grounding.yaml"],
        outputs=["evidence_cards.yaml"],
        gates=["concise claim hints only", "no long source excerpts"],
    )
    source_manifest = build_source_manifest(request, source_grounding, source_fetch_report, source_index, evidence_cards)
    record_phase(
        phase_state,
        "source_manifest",
        "completed",
        inputs=["source_grounding.yaml", "source_fetch_report.yaml", "source_index.yaml", "evidence_cards.yaml"],
        outputs=["source_manifest.yaml"],
        gates=["metadata and hashes only", "no long excerpts or full logs"],
    )
    tutorial_catalog = build_tutorial_catalog(request, source_index, source_grounding)
    record_phase(
        phase_state,
        "tutorial_catalog",
        "completed",
        inputs=["source_index.yaml", "source_grounding.yaml"],
        outputs=["tutorial_catalog.yaml"],
        gates=["compact tutorial steps only", "notebooks and scripts are not executed"],
    )
    api_grounding = build_api_grounding(request, source_index, evidence_cards)
    record_phase(
        phase_state,
        "api_grounding",
        "completed",
        inputs=["source_index.yaml", "evidence_cards.yaml"],
        outputs=["api_grounding.yaml"],
        gates=["API candidates are hints, not execution proof"],
    )
    interface_grounding = build_interface_grounding(request, source_index, api_grounding, evidence_cards)
    record_phase(
        phase_state,
        "interface_grounding",
        "completed",
        inputs=["source_index.yaml", "api_grounding.yaml"],
        outputs=["interface_grounding.yaml"],
        gates=["Python AST only", "package code is not imported"],
    )
    key_api_coverage_audit = build_key_api_coverage_audit(request, api_grounding, interface_grounding)
    record_phase(
        phase_state,
        "key_api_coverage_audit",
        "completed",
        inputs=["normalized build request", "api_grounding.yaml", "interface_grounding.yaml"],
        outputs=["key_api_coverage_audit.yaml"],
        gates=["explicit request api_names are exactly grounded", "coverage uses normalized symbol variants", "coverage is static and not execution verification"],
    )
    source_parse_report = build_source_parse_report(
        request,
        source_index,
        api_grounding,
        interface_grounding,
        tutorial_catalog,
    )
    record_phase(
        phase_state,
        "source_parse_report",
        "completed",
        inputs=["source_index.yaml", "api_grounding.yaml", "interface_grounding.yaml", "tutorial_catalog.yaml"],
        outputs=["source_parse_report.yaml"],
        gates=["explicit parse strategy recorded", "parser capability matrix recorded", "static parsing boundaries recorded"],
    )
    source_parsing_coverage = build_source_parsing_coverage(
        request,
        source_fetch_report,
        source_index,
        source_parse_report,
        api_grounding,
        interface_grounding,
        tutorial_catalog,
    )
    record_phase(
        phase_state,
        "source_parsing_coverage",
        "completed",
        inputs=["source_fetch_report.yaml", "source_index.yaml", "source_parse_report.yaml", "api_grounding.yaml", "interface_grounding.yaml", "tutorial_catalog.yaml"],
        outputs=["source_parsing_coverage.yaml"],
        gates=["parser coverage by source kind recorded", "remote fetch gaps and parser gaps surfaced"],
    )
    source_parsing_audit = build_source_parsing_audit(
        request,
        source_index,
        source_parse_report,
        source_parsing_coverage,
        api_grounding,
        interface_grounding,
        tutorial_catalog,
    )
    record_phase(
        phase_state,
        "source_parsing_audit",
        "completed",
        inputs=["source_index.yaml", "source_parse_report.yaml", "source_parsing_coverage.yaml", "api_grounding.yaml", "interface_grounding.yaml", "tutorial_catalog.yaml"],
        outputs=["source_parsing_audit.yaml"],
        gates=["static non-execution policy is explicit", "source records keep provenance and hashes", "parser-derived API, interface, and tutorial gaps are surfaced"],
    )
    source_ingestion_audit = build_source_ingestion_audit(
        request,
        source_grounding,
        source_fetch_report,
        source_index,
        source_parse_report,
        source_parsing_coverage,
        source_parsing_audit,
        source_manifest,
        evidence_cards,
    )
    record_phase(
        phase_state,
        "source_ingestion_audit",
        "completed",
        inputs=["source_grounding.yaml", "source_fetch_report.yaml", "source_index.yaml", "source_parse_report.yaml", "source_parsing_coverage.yaml", "source_parsing_audit.yaml", "source_manifest.yaml", "evidence_cards.yaml"],
        outputs=["source_ingestion_audit.yaml"],
        gates=["source evidence ids agree across ingestion artifacts", "source and evidence-card counts match", "fetch and parse non-execution policies are explicit"],
    )
    backend_contract = build_backend_contract(request)
    record_phase(
        phase_state,
        "backend_contract",
        "completed",
        inputs=["normalized build request"],
        outputs=["backend_contract.yaml"],
        gates=["Python backend implemented", "R backend reserved as extension"],
    )
    environment_spec = build_environment_spec(request, source_index, backend_contract)
    record_phase(
        phase_state,
        "environment_spec",
        "completed",
        inputs=["source_index.yaml", "backend_contract.yaml"],
        outputs=["environment_spec.yaml"],
        gates=["static dependency/import hints only", "no dependency installation"],
    )
    task_catalog = build_task_catalog(request, sources, evidence_cards)
    task_catalog = attach_interface_hints(task_catalog, interface_grounding)
    task_partition_decision_log = build_task_partition_decision_log(
        request,
        sources,
        evidence_cards,
        tutorial_catalog,
        task_catalog,
    )
    task_types = [task["task_type"] for task in task_catalog["tasks"]]
    record_phase(
        phase_state,
        "task_partition",
        "completed",
        inputs=["evidence_cards.yaml", "source_grounding.yaml"],
        outputs=["task_catalog.yaml"],
        gates=["one package remains one child skill", "capabilities mapped to task_type"],
    )
    record_phase(
        phase_state,
        "task_partition_decision_log",
        "completed",
        inputs=["task_catalog.yaml", "evidence_cards.yaml", "tutorial_catalog.yaml"],
        outputs=["task_partition_decision_log.yaml"],
        gates=["accepted task_type decisions recorded", "tutorial-shaped split candidates rejected as evidence-only"],
    )
    parameter_catalog = build_parameter_catalog(request, interface_grounding)
    task_catalog = attach_parameter_constraints(task_catalog, parameter_catalog)
    task_catalog = attach_operational_recipes(
        task_catalog,
        request,
        tutorial_catalog,
        api_grounding,
        interface_grounding,
        parameter_catalog,
    )
    record_phase(
        phase_state,
        "parameter_catalog",
        "completed",
        inputs=["interface_grounding.yaml", "task_catalog.yaml"],
        outputs=["parameter_catalog.yaml"],
        gates=["static signature parameters only", "biological semantics remain evidence-bounded"],
    )
    record_phase(
        phase_state,
        "operational_recipes",
        "completed",
        inputs=["task_catalog.yaml", "tutorial_catalog.yaml", "api_grounding.yaml", "interface_grounding.yaml", "parameter_catalog.yaml"],
        outputs=["task_catalog.operational_recipe"],
        gates=["task_type recipes include workflow steps", "source-grounded API sequence recorded when available", "abstract recipes are flagged for agent review"],
    )
    write_execution_trace_if_requested(request, out)
    record_phase(
        phase_state,
        "optional_execution_grounding",
        "completed" if request.get("execution_grounded") else "skipped",
        inputs=["execution_traces from build request", "execution_replay_results from build request"],
        outputs=["execution_trace.jsonl"] if request.get("execution_grounded") else [],
        gates=["trace capture is explicit", "no package code is executed by this phase"],
    )
    execution_trace_validation = build_execution_trace_validation(request, task_catalog)
    task_catalog = apply_validated_execution_status(task_catalog, execution_trace_validation, request)
    record_phase(
        phase_state,
        "execution_trace_validation",
        "completed",
        inputs=["execution_traces from build request", "execution_replay_results from build request", "task_catalog.yaml"],
        outputs=["execution_trace_validation.yaml"],
        gates=["only successful supplied traces or replay results can mark execution_verified", "trace provenance fields validated"],
    )
    parsed_api_names = [
        str(candidate.get("symbol"))
        for candidate in api_grounding.get("api_candidates", [])[:100]
        if candidate.get("symbol")
    ]
    discovery_report = discovery(request, task_types, parsed_api_names)
    discovery_audit = build_discovery_audit(request, discovery_preflight, discovery_report, task_catalog)
    discovery_match_audit = build_discovery_match_audit(request, discovery_report, task_catalog)
    record_phase(
        phase_state,
        "discovery",
        "completed",
        inputs=["normalized build request", "task_catalog.yaml"],
        outputs=["discovery_report.yaml"],
        gates=["existing Codex child skills checked when directories are provided"],
    )
    record_phase(
        phase_state,
        "discovery_audit",
        "completed",
        inputs=["discovery_preflight.yaml", "discovery_report.yaml", "task_catalog.yaml"],
        outputs=["discovery_audit.yaml"],
        gates=["reuse/update/create decision is explainable", "reuse covers every inferred task_type"],
    )
    record_phase(
        phase_state,
        "discovery_match_audit",
        "completed",
        inputs=["discovery_report.yaml", "task_catalog.yaml"],
        outputs=["discovery_match_audit.yaml"],
        gates=["field-level match quality audited", "reuse/update decisions require strong existing-skill evidence"],
    )
    router = build_router(task_catalog)
    record_phase(
        phase_state,
        "task_type_routing",
        "completed",
        inputs=["task_catalog.yaml"],
        outputs=["task_type_router.yaml"],
        gates=["router selects task_type inside one child skill"],
    )
    review_result = review_loop(
        request,
        discovery_report,
        source_grounding,
        task_catalog,
        router,
        evidence_cards,
        api_grounding,
        interface_grounding,
        environment_spec,
        tutorial_catalog,
        parameter_catalog,
    )
    task_catalog = review_result["task_catalog"]
    router = review_result["router"]
    review_summary = {
        "schema_version": source_grounding["schema_version"],
        "status": review_result["status"],
        "mode": review_result.get("mode"),
        "review_loop_version": review_result.get("review_loop_version"),
        "agent_driven": review_result.get("agent_driven"),
        "final_score": review_result["final_score"],
        "final_findings": review_result["final_findings"],
        "iteration_count": len(review_result["iterations"]),
        "stop_reason": review_result.get("stop_reason"),
        "candidate_versions": review_result.get("candidate_versions", []),
        "score_cache_count": len(review_result.get("score_cache") or {}),
        "rejected_buffer_count": len(review_result.get("rejected_buffer") or []),
        "next_step": review_result.get("next_step"),
    }
    review_evolution = build_review_evolution(request, review_result)
    review_evolution_plot = build_review_evolution_plot(request, review_evolution)
    review_evolution_svg = render_review_evolution_svg(review_evolution)
    review_prompt_contracts = build_review_prompt_contracts(request, review_result)
    review_prompt_materials = build_review_prompt_materials(request, review_prompt_contracts)
    review_cursor = build_review_cursor(request, review_result)
    patch_application = build_patch_application(request, review_result)
    review_remediation_audit = build_review_remediation_audit(request, review_result, patch_application)
    review_iteration_log = build_review_iteration_log(request, review_result, review_evolution, patch_application)
    review_iteration_log_markdown = render_review_iteration_log_markdown(review_iteration_log)
    review_optimizer_state = build_review_optimizer_state(request, review_result)
    review_prompt_suite_audit = build_review_prompt_suite_audit(
        request,
        review_result,
        review_prompt_contracts,
        review_prompt_materials,
        review_optimizer_state,
    )
    patch_safety_audit = audit_patch_safety(request, review_result, review_optimizer_state)
    patch_operation_contracts = build_patch_operation_contracts(request, review_result, patch_application, patch_safety_audit)
    review_discipline_audit = build_review_discipline_audit(request, review_result)
    rubric_grounding_audit = build_rubric_grounding_audit(request, review_result)
    review_trajectory_audit = build_review_trajectory_audit(
        request,
        review_evolution,
        review_cursor,
        patch_application,
        review_optimizer_state,
        review_prompt_contracts,
        rubric_grounding_audit,
    )
    evidence_coverage = build_evidence_coverage(request, task_catalog, evidence_cards, source_grounding)
    task_conflict_matrix = build_task_conflict_matrix(task_catalog, router)
    routing_fixture = build_routing_fixture(request, task_catalog, router, task_conflict_matrix)
    task_partition_audit = build_task_partition_audit(
        request,
        task_catalog,
        router,
        task_conflict_matrix,
        tutorial_catalog,
    )
    record_phase(
        phase_state,
        "self_review",
        "completed",
        inputs=["discovery_report.yaml", "source_grounding.yaml", "task_catalog.yaml", "task_type_router.yaml"],
        outputs=["review_iterations.jsonl", "review_log.jsonl", "review_summary.yaml"],
        gates=["bounded agent-driven review", "Codex-authored proposal required for non-passing drafts", "strict improvement gate"],
    )
    record_phase(
        phase_state,
        "review_evolution",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["review_evolution.yaml"],
        gates=["score trajectory summarized", "patch and gate reasons summarized"],
    )
    record_phase(
        phase_state,
        "review_evolution_plot",
        "completed",
        inputs=["review_evolution.yaml"],
        outputs=["review_evolution_plot.yaml", "review_evolution_plot.svg"],
        gates=["human-readable review trajectory rendered", "run artifact only", "no package execution"],
    )
    record_phase(
        phase_state,
        "review_iteration_log",
        "completed",
        inputs=["review_iterations.jsonl", "review_evolution.yaml", "patch_application.yaml"],
        outputs=["review_iteration_log.yaml", "review_iteration_log.md"],
        gates=["human-readable review iteration log rendered", "run artifact only", "does not change patch or publish decisions"],
    )
    record_phase(
        phase_state,
        "review_prompt_contracts",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["review_prompt_contracts.yaml"],
        gates=["review state roles have declared contracts", "required fields are present", "patch changes record revision state"],
    )
    record_phase(
        phase_state,
        "review_prompt_materials",
        "completed",
        inputs=["review_prompt_contracts.yaml"],
        outputs=["review_prompt_materials.yaml"],
        gates=["review role prompts have static material", "allowed inputs and forbidden outputs declared", "no package execution"],
    )
    record_phase(
        phase_state,
        "review_cursor",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["review_cursor.yaml"],
        gates=[
            "review cursor is resumable or terminal",
            "iteration states include draft, record_score, rollout_plan, critic, patch_plan, and gate",
        ],
    )
    record_phase(
        phase_state,
        "patch_application",
        "completed",
        inputs=["review_iterations.jsonl"],
        outputs=["patch_application.yaml"],
        gates=["planned agent proposal actions match applied patch records"],
    )
    record_phase(
        phase_state,
        "review_remediation_audit",
        "completed",
        inputs=["review_iterations.jsonl", "patch_application.yaml", "review_summary.yaml"],
        outputs=["review_remediation_audit.yaml"],
        gates=["review findings are accounted for", "patch actions cite same-iteration findings", "final blockers remain explicit"],
    )
    record_phase(
        phase_state,
        "review_optimizer_state",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["review_optimizer_state.yaml"],
        gates=["iteration states are hashable", "strict improvement policy enforced and recorded", "rejected edit buffer recorded"],
    )
    record_phase(
        phase_state,
        "review_prompt_suite_audit",
        "completed",
        inputs=["review_iterations.jsonl", "review_prompt_contracts.yaml", "review_prompt_materials.yaml", "review_optimizer_state.yaml"],
        outputs=["review_prompt_suite_audit.yaml"],
        gates=["required review duties covered", "review duty roles present", "review duties remain static and non-executing"],
    )
    record_phase(
        phase_state,
        "patch_safety_audit",
        "completed",
        inputs=["review_iterations.jsonl", "review_optimizer_state.yaml"],
        outputs=["patch_safety_audit.yaml"],
        gates=["patch actions stay inside allowed artifacts", "no commands, paths, installs, or network actions in patch records"],
    )
    record_phase(
        phase_state,
        "patch_operation_contracts",
        "completed",
        inputs=["review_iterations.jsonl", "patch_application.yaml", "patch_safety_audit.yaml"],
        outputs=["patch_operation_contracts.yaml"],
        gates=["patch operation names are declared", "operation fields match contracts", "operations cite same-iteration review findings"],
    )
    record_phase(
        phase_state,
        "review_discipline_audit",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["review_discipline_audit.yaml"],
        gates=["review stop reason is consistent", "patches do not regress review score", "gate and patch states agree"],
    )
    record_phase(
        phase_state,
        "rubric_grounding_audit",
        "completed",
        inputs=["review_iterations.jsonl", "review_summary.yaml"],
        outputs=["rubric_grounding_audit.yaml"],
        gates=["rubric item results are complete", "awarded points have grounding signals", "score equals item-point sum"],
    )
    record_phase(
        phase_state,
        "review_trajectory_audit",
        "completed",
        inputs=["review_evolution.yaml", "review_prompt_contracts.yaml", "review_cursor.yaml", "patch_application.yaml", "review_optimizer_state.yaml", "rubric_grounding_audit.yaml"],
        outputs=["review_trajectory_audit.yaml"],
        gates=["review trajectory artifacts agree", "final score matches final iteration"],
    )
    record_phase(
        phase_state,
        "evidence_coverage",
        "completed",
        inputs=["reviewed task_catalog.yaml", "evidence_cards.yaml", "source_grounding.yaml"],
        outputs=["evidence_coverage.yaml"],
        gates=["task_type evidence priority summarized", "claim-type coverage summarized"],
    )
    record_phase(
        phase_state,
        "task_conflict_matrix",
        "completed",
        inputs=["reviewed task_catalog.yaml", "reviewed task_type_router.yaml"],
        outputs=["task_conflict_matrix.yaml"],
        gates=["ambiguity and selection rules are explicit"],
    )
    record_phase(
        phase_state,
        "routing_fixture",
        "completed",
        inputs=["reviewed task_catalog.yaml", "reviewed task_type_router.yaml", "task_conflict_matrix.yaml"],
        outputs=["routing_fixture.yaml"],
        gates=["select, refuse, unsupported, and ambiguity cases generated"],
    )
    record_phase(
        phase_state,
        "task_partition_audit",
        "completed",
        inputs=["reviewed task_catalog.yaml", "reviewed task_type_router.yaml", "task_conflict_matrix.yaml", "tutorial_catalog.yaml"],
        outputs=["task_partition_audit.yaml"],
        gates=["task_type entries are capabilities, not tutorial artifacts", "task contracts and routing cues are present", "ambiguous splits are surfaced"],
    )
    evidence_precedence = build_evidence_precedence(
        request,
        task_catalog,
        evidence_cards,
        source_grounding,
        execution_trace_validation,
    )
    record_phase(
        phase_state,
        "evidence_precedence",
        "completed",
        inputs=["task_catalog.yaml", "evidence_cards.yaml", "source_grounding.yaml", "execution_trace_validation.yaml"],
        outputs=["evidence_precedence.yaml"],
        gates=["highest-priority evidence selected per task claim", "verified tasks require trace precedence"],
    )
    evidence_claim_taxonomy_audit = build_evidence_claim_taxonomy_audit(
        request,
        task_catalog,
        evidence_cards,
        source_grounding,
        evidence_precedence,
        execution_trace_validation,
    )
    record_phase(
        phase_state,
        "evidence_claim_taxonomy_audit",
        "completed",
        inputs=["task_catalog.yaml", "evidence_cards.yaml", "source_grounding.yaml", "evidence_precedence.yaml", "execution_trace_validation.yaml"],
        outputs=["evidence_claim_taxonomy_audit.yaml"],
        gates=["claim types classified by task_type", "operational claims cannot be paper-only", "execution_verified claims require execution_verification evidence"],
    )
    eval_plan = build_eval_plan(request, task_catalog, interface_grounding)
    record_phase(
        phase_state,
        "eval_plan",
        "completed",
        inputs=["task_catalog.yaml", "interface_grounding.yaml"],
        outputs=["eval_plan.yaml"],
        gates=["static eval scenarios only", "execution scenarios require explicit approval"],
    )
    execution_plan = build_execution_plan(request, task_catalog, eval_plan)
    environment_install_plan = build_environment_install_plan(
        request,
        environment_spec,
        backend_contract,
        execution_plan,
        resource_inventory,
    )
    record_phase(
        phase_state,
        "execution_plan",
        "completed",
        inputs=["task_catalog.yaml", "eval_plan.yaml"],
        outputs=["execution_plan.yaml"],
        gates=["plan only", "execution requires explicit approval and trace capture"],
    )
    record_phase(
        phase_state,
        "environment_install_plan",
        "completed",
        inputs=["environment_spec.yaml", "backend_contract.yaml", "execution_plan.yaml", "resource_inventory.yaml"],
        outputs=["environment_install_plan.yaml"],
        gates=["plan only", "no dependency installation", "environment mutation requires explicit approval"],
    )
    backend_extension_audit = build_backend_extension_audit(
        request,
        backend_contract,
        environment_install_plan,
        task_catalog,
        source_parsing_audit,
    )
    record_phase(
        phase_state,
        "backend_extension_audit",
        "completed",
        inputs=["backend_contract.yaml", "environment_install_plan.yaml", "task_catalog.yaml", "source_parsing_audit.yaml"],
        outputs=["backend_extension_audit.yaml"],
        gates=["Python is the only implemented backend", "R remains extension-reserved", "non-Python backends keep refusal and no-execution boundaries"],
    )
    tutorial_reproduction_plan = build_tutorial_reproduction_plan(
        request,
        task_catalog,
        tutorial_catalog,
        environment_spec,
        execution_plan,
    )
    record_phase(
        phase_state,
        "tutorial_reproduction_plan",
        "completed",
        inputs=["task_catalog.yaml", "tutorial_catalog.yaml", "environment_spec.yaml", "execution_plan.yaml"],
        outputs=["tutorial_reproduction_plan.yaml"],
        gates=["plan only", "tutorial replay queue built", "trace capture requirements explicit"],
    )
    execution_replay_orchestrator = build_execution_replay_orchestrator(
        request,
        tutorial_reproduction_plan,
        execution_plan,
        environment_install_plan,
    )
    record_phase(
        phase_state,
        "execution_replay_orchestrator",
        "completed",
        inputs=["tutorial_reproduction_plan.yaml", "execution_plan.yaml", "environment_install_plan.yaml", "execution_replay_results from build request"],
        outputs=["execution_replay_orchestrator.yaml"],
        gates=["plan-only replay jobs built", "supplied replay results audited", "replay failures become troubleshooting revision actions"],
    )
    contract_traceability = build_contract_traceability(request, task_catalog)
    record_phase(
        phase_state,
        "contract_traceability",
        "completed",
        inputs=["task_catalog.yaml"],
        outputs=["contract_traceability.yaml"],
        gates=["input, output, validation, and refusal contracts linked to evidence refs"],
    )
    acceptance_suite = build_acceptance_suite(
        request,
        task_catalog,
        router,
        task_conflict_matrix,
        eval_plan,
        execution_plan,
        tutorial_reproduction_plan,
        contract_traceability,
    )
    record_phase(
        phase_state,
        "acceptance_suite",
        "completed",
        inputs=["task_catalog.yaml", "task_type_router.yaml", "task_conflict_matrix.yaml", "eval_plan.yaml", "execution_plan.yaml", "tutorial_reproduction_plan.yaml", "contract_traceability.yaml"],
        outputs=["acceptance_suite.yaml"],
        gates=["routing, refusal, contract, ambiguity, tutorial-replay, and execution-boundary cases generated"],
    )
    eval_splits = build_eval_splits(request, eval_plan, acceptance_suite, routing_fixture)
    record_phase(
        phase_state,
        "eval_splits",
        "completed",
        inputs=["eval_plan.yaml", "acceptance_suite.yaml", "routing_fixture.yaml"],
        outputs=["eval_splits.yaml"],
        gates=["train, selection, and test splits generated", "cases remain static and non-executing"],
    )
    eval_result_judge = build_eval_result_judge(request, eval_splits)
    record_phase(
        phase_state,
        "eval_result_judge",
        "completed" if request.get("eval_results") else "skipped",
        inputs=["eval_results from build request", "eval_splits.yaml"],
        outputs=["eval_result_judge.yaml"],
        gates=["only explicit eval results are judged", "static eval results do not imply runtime verification"],
    )
    draft_candidates = build_draft_candidates(
        request,
        discovery_report,
        task_catalog,
        router,
        api_grounding,
        interface_grounding,
    )
    record_phase(
        phase_state,
        "draft_candidate",
        "completed",
        inputs=["task_catalog.yaml", "task_type_router.yaml", "api_grounding.yaml"],
        outputs=["draft_candidates.yaml"],
        gates=["single child-skill candidate", "task_type risk notes recorded"],
    )

    method_name = str(request.get("method_name") or request.get("package_name"))
    child_skill_dir = out / "child_skill" / slugify(method_name)
    render_child_skill(
        child_skill_dir,
        request,
        {
            "source_grounding": source_grounding,
            "source_parse_report": source_parse_report,
            "source_parsing_coverage": source_parsing_coverage,
            "task_catalog": task_catalog,
            "router": router,
            "environment_spec": environment_spec,
            "environment_install_plan": environment_install_plan,
            "resource_inventory": resource_inventory,
            "tutorial_catalog": tutorial_catalog,
            "tutorial_reproduction_plan": tutorial_reproduction_plan,
            "execution_replay_orchestrator": execution_replay_orchestrator,
            "evidence_precedence": evidence_precedence,
            "task_conflict_matrix": task_conflict_matrix,
        },
    )
    record_phase(
        phase_state,
        "skill_draft",
        "completed",
        inputs=["task_catalog.yaml", "task_type_router.yaml", "source_grounding.yaml", "source_parse_report.yaml"],
        outputs=[public_child_skill_path(child_skill_dir)],
        gates=["scientific-agent-skills lightweight layout", "required references rendered"],
    )
    verification_claim_audit = build_verification_claim_audit(
        request,
        task_catalog,
        execution_trace_validation,
        execution_plan,
        tutorial_reproduction_plan,
        child_skill_dir,
    )
    record_phase(
        phase_state,
        "verification_claim_audit",
        "completed",
        inputs=["task_catalog.yaml", "execution_trace_validation.yaml", "execution_plan.yaml", "tutorial_reproduction_plan.yaml", "child_skill directory"],
        outputs=["verification_claim_audit.yaml"],
        gates=["execution_verified claims have validated traces", "source_grounded tasks do not hide successful traces", "verification statuses are rendered"],
    )
    child_skill_files = {
        str(path.relative_to(child_skill_dir)).replace("\\", "/"): path.read_text(encoding="utf-8")
        for path in child_skill_dir.rglob("*.md")
    }
    resource_boundary_audit = build_resource_boundary_audit(
        request,
        resource_inventory,
        environment_install_plan,
        child_skill_files,
    )
    record_phase(
        phase_state,
        "resource_boundary_audit",
        "completed",
        inputs=["resource_inventory.yaml", "environment_install_plan.yaml", "child_skill references"],
        outputs=["resource_boundary_audit.yaml"],
        gates=["model/data resource refusals rendered", "gated or large resources require explicit approval"],
    )
    child_metadata_audit = build_child_metadata_audit(request, child_skill_dir, task_catalog)
    record_phase(
        phase_state,
        "child_metadata_audit",
        "completed",
        inputs=["child_skill/SKILL.md", "task_catalog.yaml"],
        outputs=["child_metadata_audit.yaml"],
        gates=["Codex trigger metadata complete", "one package remains one child skill", "no separate routing-selector shape"],
    )

    skill_spec = build_skill_spec(request, child_skill_dir, task_catalog)
    record_phase(
        phase_state,
        "skill_spec",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml"],
        outputs=["skill_spec.yaml"],
        gates=["child skill install shape summarized", "task metadata attached", "builder version recorded"],
    )
    child_package_purity_audit = build_child_package_purity_audit(request, child_skill_dir, skill_spec)
    record_phase(
        phase_state,
        "child_package_purity_audit",
        "completed",
        inputs=["child_skill directory", "skill_spec.yaml"],
        outputs=["child_package_purity_audit.yaml"],
        gates=["public child skill contains only SKILL.md and standard references", "no build traces, candidates, assets, scripts, staging files, or auxiliary docs"],
    )
    lint_report = lint_child_skill(child_skill_dir)
    draft_readiness = build_draft_readiness(request, child_skill_dir)
    output_boundary_audit = build_output_boundary_audit(request, out, child_skill_dir, skill_spec)
    skill_update_plan = build_skill_update_plan(
        request,
        discovery_report,
        discovery_audit,
        task_catalog,
        child_skill_dir,
    )
    skill_update_audit = build_skill_update_audit(request, skill_update_plan)
    discovery_resolution_audit = build_discovery_resolution_audit(
        request,
        discovery_preflight,
        discovery_report,
        discovery_match_audit,
        skill_update_plan,
    )
    forward_test_plan = build_forward_test_plan(
        request,
        child_skill_dir,
        task_catalog,
        acceptance_suite,
        eval_splits,
    )
    agent_rollout_harness = build_agent_rollout_harness(
        request,
        task_catalog,
        routing_fixture,
        eval_splits,
        forward_test_plan,
    )
    agent_rollout_audit = build_agent_rollout_audit(request, forward_test_plan, agent_rollout_harness)
    eval_leakage_audit = build_eval_leakage_audit(
        request,
        eval_splits,
        forward_test_plan,
        agent_rollout_harness,
        eval_result_judge,
    )
    agent_rollout_result_judge = build_agent_rollout_result_judge(
        request,
        agent_rollout_harness,
        eval_leakage_audit,
    )
    e2e_acceptance = build_e2e_acceptance(
        request,
        task_catalog,
        acceptance_suite,
        eval_splits,
        forward_test_plan,
        agent_rollout_harness,
        agent_rollout_result_judge,
        execution_replay_orchestrator,
        verification_claim_audit,
    )
    smoke_test_plan = build_smoke_test_plan(request, task_catalog)
    record_phase(
        phase_state,
        "lint",
        "completed",
        inputs=[public_child_skill_path(child_skill_dir)],
        outputs=["skill_lint_report.yaml"],
        gates=["required child-skill files present", "SKILL.md contains task_type guidance"],
    )
    record_phase(
        phase_state,
        "draft_readiness",
        "completed",
        inputs=[public_child_skill_path(child_skill_dir), "normalized build request"],
        outputs=["draft_readiness.yaml"],
        gates=["no unresolved draft markers", "no default build-request URLs", "public child-skill markdown checked"],
    )
    record_phase(
        phase_state,
        "output_boundary_audit",
        "completed",
        inputs=["normalized build request", "child_skill directory", "skill_spec.yaml"],
        outputs=["output_boundary_audit.yaml"],
        gates=["child skill stays under output child_skill root", "public child skill contains only installable files"],
    )
    record_phase(
        phase_state,
        "skill_update_plan",
        "completed",
        inputs=["discovery_report.yaml", "discovery_audit.yaml", "task_catalog.yaml", "child_skill directory"],
        outputs=["skill_update_plan.yaml"],
        gates=["plan only", "reuse/update/create action recorded", "existing skill updates require manual merge review"],
    )
    record_phase(
        phase_state,
        "skill_update_audit",
        "completed",
        inputs=["skill_update_plan.yaml"],
        outputs=["skill_update_audit.yaml"],
        gates=["plan only", "update/reuse targets present", "merge actions are manual and limited to standard child files"],
    )
    record_phase(
        phase_state,
        "discovery_resolution_audit",
        "completed",
        inputs=["discovery_preflight.yaml", "discovery_report.yaml", "discovery_match_audit.yaml", "skill_update_plan.yaml"],
        outputs=["discovery_resolution_audit.yaml"],
        gates=["create does not duplicate strong matches", "update/reuse target final best match", "ambiguous high-confidence matches are blocked"],
    )
    record_phase(
        phase_state,
        "forward_test_plan",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml", "acceptance_suite.yaml", "eval_splits.yaml"],
        outputs=["forward_test_plan.yaml"],
        gates=["plan only", "test-agent prompts do not include expected behavior", "structured refusal and execution-boundary cases included"],
    )
    record_phase(
        phase_state,
        "agent_rollout_harness",
        "completed",
        inputs=["forward_test_plan.yaml", "routing_fixture.yaml", "eval_splits.yaml", "task_catalog.yaml"],
        outputs=["agent_rollout_harness.yaml"],
        gates=["plan only", "rollout prompts do not leak judge metadata", "task routing, contract, refusal, and execution-boundary coverage present"],
    )
    record_phase(
        phase_state,
        "agent_rollout_audit",
        "completed",
        inputs=["forward_test_plan.yaml", "agent_rollout_harness.yaml"],
        outputs=["agent_rollout_audit.yaml"],
        gates=["every forward-test scenario maps to rollout", "agent prompts do not leak judge metadata", "rollout remains plan-only"],
    )
    record_phase(
        phase_state,
        "eval_leakage_audit",
        "completed",
        inputs=["eval_splits.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml", "eval_result_judge.yaml"],
        outputs=["eval_leakage_audit.yaml"],
        gates=["eval split identities are disjoint", "holdout forward-test scenarios exist", "agent-visible prompts do not leak judge metadata or expected values"],
    )
    record_phase(
        phase_state,
        "agent_rollout_result_judge",
        "completed" if request.get("agent_rollout_results") else "skipped",
        inputs=["agent_rollout_results from build request", "agent_rollout_harness.yaml", "eval_leakage_audit.yaml"],
        outputs=["agent_rollout_result_judge.yaml"],
        gates=["only explicit rollout results are judged", "not_run does not imply agent validation", "rollout result pass does not imply package execution verification"],
    )
    record_phase(
        phase_state,
        "e2e_acceptance",
        "completed" if request.get("e2e_acceptance_results") else "skipped",
        inputs=["acceptance_suite.yaml", "eval_splits.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml", "agent_rollout_result_judge.yaml", "execution_replay_orchestrator.yaml", "verification_claim_audit.yaml", "e2e_acceptance_results from build request"],
        outputs=["e2e_acceptance.yaml"],
        gates=["plan-only E2E scenarios generated", "only explicit E2E results are audited", "require_e2e_acceptance blocks publish when required results are missing"],
    )
    record_phase(
        phase_state,
        "smoke_test_plan",
        "completed" if request.get("smoke_test_results") else "skipped",
        inputs=["task_catalog.yaml", "child_skill directory", "smoke_test_results from build request"],
        outputs=["smoke_test_plan.yaml"],
        gates=["plan-only smoke scenarios generated", "only explicit smoke results are audited", "require_smoke_test blocks publish when required smoke results are missing"],
    )
    grounding_gate = build_grounding_gate(
        request,
        task_catalog,
        api_grounding,
        interface_grounding,
        tutorial_catalog,
        source_parse_report,
    )
    record_phase(
        phase_state,
        "grounding_gate",
        "completed",
        inputs=["task_catalog.yaml", "api_grounding.yaml", "interface_grounding.yaml", "tutorial_catalog.yaml"],
        outputs=["grounding_gate.yaml"],
        gates=["task_type API/interface grounding reviewed", "verified task_types cannot lack grounded API/interface evidence"],
    )
    api_surface_audit = audit_api_surface(
        child_skill_dir,
        api_grounding,
        interface_grounding,
        task_catalog,
        request,
    )
    record_phase(
        phase_state,
        "api_surface_audit",
        "completed",
        inputs=["child_skill directory", "api_grounding.yaml", "interface_grounding.yaml", "task_catalog.yaml", "normalized build request"],
        outputs=["api_surface_audit.yaml"],
        gates=["rendered code-fence API calls are grounded", "request API names are checked against parsed surface", "task API surface gaps are surfaced"],
    )
    claim_consistency_audit = audit_claim_consistency(
        child_skill_dir,
        task_catalog,
        source_grounding,
        evidence_cards,
        backend_contract,
        evidence_precedence,
    )
    record_phase(
        phase_state,
        "claim_consistency_audit",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml", "source_grounding.yaml", "evidence_cards.yaml", "backend_contract.yaml", "evidence_precedence.yaml"],
        outputs=["claim_consistency_audit.yaml"],
        gates=["rendered task_type, evidence, refusal, backend, and verification claims match artifacts"],
    )
    biological_claim_boundary_audit = build_biological_claim_boundary_audit(
        child_skill_dir,
        task_catalog,
        source_grounding,
        evidence_cards,
    )
    record_phase(
        phase_state,
        "biological_claim_boundary_audit",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml", "source_grounding.yaml", "evidence_cards.yaml"],
        outputs=["biological_claim_boundary_audit.yaml"],
        gates=["high-risk cross-modal biological claims require matching evidence", "unsupported task and modality refusals are present and rendered"],
    )
    child_reference_coverage = audit_child_reference_coverage(
        child_skill_dir,
        task_catalog,
        source_parsing_coverage,
        environment_install_plan,
        tutorial_reproduction_plan,
        evidence_precedence,
        task_conflict_matrix,
    )
    record_phase(
        phase_state,
        "child_reference_coverage",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml", "source_parsing_coverage.yaml", "environment_install_plan.yaml", "tutorial_reproduction_plan.yaml", "evidence_precedence.yaml", "task_conflict_matrix.yaml"],
        outputs=["child_reference_coverage.yaml"],
        gates=["key build artifacts are rendered into child references", "task_type entries appear in required public files"],
    )
    routing_metadata_audit = audit_routing_metadata(
        child_skill_dir,
        task_catalog,
        router,
        task_conflict_matrix,
        routing_fixture,
    )
    record_phase(
        phase_state,
        "routing_metadata_audit",
        "completed",
        inputs=["child_skill directory", "task_catalog.yaml", "task_type_router.yaml", "task_conflict_matrix.yaml", "routing_fixture.yaml"],
        outputs=["routing_metadata_audit.yaml"],
        gates=["router scope is inside one child skill", "task_type routing is rendered", "refusal and ambiguity cases are covered"],
    )
    source_grounding_audit = audit_source_grounding(
        request,
        source_grounding,
        source_parse_report,
        source_parsing_coverage,
        source_parsing_audit,
        evidence_cards,
        evidence_precedence,
        task_catalog,
        contract_traceability,
        child_skill_dir,
    )
    record_phase(
        phase_state,
        "source_grounding_audit",
        "completed",
        inputs=["source_grounding.yaml", "source_parse_report.yaml", "source_parsing_coverage.yaml", "source_parsing_audit.yaml", "evidence_cards.yaml", "evidence_precedence.yaml", "task_catalog.yaml", "contract_traceability.yaml", "child_skill directory"],
        outputs=["source_grounding_audit.yaml"],
        gates=["evidence priority is preserved", "static parsing boundary is explicit", "task_type evidence is traceable and rendered"],
    )
    lineage_graph = build_lineage_graph(
        request,
        source_manifest,
        evidence_cards,
        task_catalog,
        contract_traceability,
        skill_spec,
        child_skill_dir,
    )
    record_phase(
        phase_state,
        "lineage_graph",
        "completed",
        inputs=["source_manifest.yaml", "evidence_cards.yaml", "task_catalog.yaml", "contract_traceability.yaml", "skill_spec.yaml", "child_skill directory"],
        outputs=["lineage_graph.yaml"],
        gates=["source-to-task evidence lineage present", "contract records render into child skill references"],
    )
    workflow_invariant_audit = audit_workflow_invariants(
        request,
        child_skill_dir,
        task_catalog,
        router,
        eval_plan,
        execution_plan,
        tutorial_reproduction_plan,
        contract_traceability,
        lineage_graph,
        claim_consistency_audit,
        backend_contract,
        draft_candidates,
    )
    record_phase(
        phase_state,
        "workflow_invariant_audit",
        "completed",
        inputs=["normalized build request", "child_skill directory", "task_catalog.yaml", "task_type_router.yaml", "eval_plan.yaml", "execution_plan.yaml", "tutorial_reproduction_plan.yaml", "contract_traceability.yaml", "lineage_graph.yaml", "claim_consistency_audit.yaml", "backend_contract.yaml", "draft_candidates.yaml"],
        outputs=["workflow_invariant_audit.yaml"],
        gates=["one package one child skill", "task_type coverage across core artifacts including tutorial reproduction planning", "Codex target and backend boundaries preserved"],
    )
    requirement_coverage = build_requirement_coverage(
        request,
        request_audit,
        request_fingerprint,
        external_result_contracts,
        builder_runtime_audit,
        agent_metadata_audit,
        public_origin_audit,
        module_inventory_audit,
        builder_baseline_audit,
        skill_package_audit,
        request_template_audit,
        discovery_report,
        discovery_match_audit,
        discovery_resolution_audit,
        source_grounding,
        source_grounding_audit,
        source_fetch_boundary_audit,
        source_ingestion_audit,
        source_parsing_audit,
        key_api_coverage_audit,
        task_catalog,
        task_partition_decision_log,
        router,
        task_partition_audit,
        skill_spec,
        backend_contract,
        backend_extension_audit,
        execution_plan,
        tutorial_reproduction_plan,
        execution_replay_orchestrator,
        verification_claim_audit,
        resource_boundary_audit,
        contract_traceability,
        evidence_claim_taxonomy_audit,
        biological_claim_boundary_audit,
        child_reference_coverage,
        child_metadata_audit,
        child_package_purity_audit,
        routing_metadata_audit,
        output_boundary_audit,
        skill_update_plan,
        skill_update_audit,
        forward_test_plan,
        agent_rollout_harness,
        agent_rollout_audit,
        eval_leakage_audit,
        agent_rollout_result_judge,
        e2e_acceptance,
        review_prompt_contracts,
        review_prompt_materials,
        review_prompt_suite_audit,
        review_iteration_log,
        review_remediation_audit,
        review_optimizer_state,
        patch_safety_audit,
        patch_operation_contracts,
        review_discipline_audit,
        review_trajectory_audit,
    )
    record_phase(
        phase_state,
        "requirement_coverage",
        "completed",
        inputs=["builder_runtime_audit.yaml", "agent_metadata_audit.yaml", "public_origin_audit.yaml", "module_inventory_audit.yaml", "skill_package_audit.yaml", "request_template_audit.yaml", "request_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml", "discovery_report.yaml", "discovery_match_audit.yaml", "discovery_resolution_audit.yaml", "source_grounding.yaml", "source_ingestion_audit.yaml", "source_parsing_audit.yaml", "task_catalog.yaml", "task_partition_decision_log.yaml", "task_type_router.yaml", "task_partition_audit.yaml", "skill_spec.yaml", "backend_contract.yaml", "execution_plan.yaml", "tutorial_reproduction_plan.yaml", "verification_claim_audit.yaml", "resource_boundary_audit.yaml", "contract_traceability.yaml", "biological_claim_boundary_audit.yaml", "child_metadata_audit.yaml", "child_package_purity_audit.yaml", "child_reference_coverage.yaml", "routing_metadata_audit.yaml", "output_boundary_audit.yaml", "skill_update_plan.yaml", "skill_update_audit.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml", "agent_rollout_audit.yaml", "eval_leakage_audit.yaml", "agent_rollout_result_judge.yaml", "e2e_acceptance.yaml", "review_iteration_log.yaml", "review_prompt_materials.yaml", "review_prompt_suite_audit.yaml", "review_remediation_audit.yaml", "review_optimizer_state.yaml", "patch_safety_audit.yaml", "patch_operation_contracts.yaml", "review_discipline_audit.yaml", "review_trajectory_audit.yaml"],
        outputs=["requirement_coverage.yaml"],
        gates=["first-principles requirements map to concrete artifacts", "missing requirement coverage blocks publish"],
    )
    completion_evidence_audit = build_completion_evidence_audit(
        request,
        requirement_coverage,
        agent_rollout_result_judge,
        e2e_acceptance,
        execution_trace_validation,
        execution_replay_orchestrator,
    )
    record_phase(
        phase_state,
        "completion_evidence_audit",
        "completed",
        inputs=["requirement_coverage.yaml", "agent_rollout_result_judge.yaml", "e2e_acceptance.yaml", "execution_trace_validation.yaml", "execution_replay_orchestrator.yaml"],
        outputs=["completion_evidence_audit.yaml"],
        gates=["static build completion separated from full real-package completion", "missing external validation evidence is explicit", "execution-grounded completion requires successful execution evidence"],
    )
    acceptance_handoff = build_acceptance_handoff(
        request,
        e2e_acceptance,
        agent_rollout_harness,
        execution_replay_orchestrator,
        completion_evidence_audit,
    )
    acceptance_handoff_markdown = render_acceptance_handoff_markdown(acceptance_handoff)
    record_phase(
        phase_state,
        "acceptance_handoff",
        "completed",
        inputs=["e2e_acceptance.yaml", "agent_rollout_harness.yaml", "execution_replay_orchestrator.yaml", "completion_evidence_audit.yaml"],
        outputs=["acceptance_handoff.yaml", "acceptance_handoff.md"],
        gates=["external validation templates collected", "target request fields declared", "handoff remains plan-only"],
    )
    artifact_contracts = build_artifact_contracts_report(REQUIRED_TOP_LEVEL_ARTIFACTS, PRE_PUBLISH_ARTIFACTS)
    record_phase(
        phase_state,
        "artifact_contracts",
        "completed",
        inputs=["artifact contract definitions"],
        outputs=["artifact_contracts.yaml"],
        gates=["minimum stable artifact fields declared", "list and mapping fields typed"],
    )
    code_fence_audit = audit_child_skill_code_fences(child_skill_dir, api_grounding, interface_grounding)
    record_phase(
        phase_state,
        "code_fence_audit",
        "completed",
        inputs=[public_child_skill_path(child_skill_dir), "api_grounding.yaml", "interface_grounding.yaml"],
        outputs=["code_fence_audit.yaml"],
        gates=["no machine-local paths", "code fence API calls are grounded or warned"],
    )
    public_safety_audit = audit_public_child_skill(child_skill_dir)
    record_phase(
        phase_state,
        "public_safety_audit",
        "completed",
        inputs=[public_child_skill_path(child_skill_dir)],
        outputs=["public_safety_audit.yaml"],
        gates=["no credentials or private keys", "long excerpts flagged before release"],
    )
    record_phase(
        phase_state,
        "phase_state_audit",
        "completed",
        inputs=["phase_state.yaml", "artifact_contracts.yaml"],
        outputs=["phase_state_audit.yaml"],
        gates=["phase ledger has unique names", "completed phases declare gates", "yaml outputs have artifact contracts"],
    )
    phase_state_audit = build_phase_state_audit(request, phase_state, artifact_contracts)
    protocol_artifacts = {
        "phase_state_audit": phase_state_audit,
        "request_fingerprint": request_fingerprint,
        "external_result_contracts": external_result_contracts,
        "output_boundary_audit": output_boundary_audit,
        "discovery_resolution_audit": discovery_resolution_audit,
        "environment_install_plan": environment_install_plan,
        "execution_plan": execution_plan,
        "tutorial_reproduction_plan": tutorial_reproduction_plan,
        "execution_replay_orchestrator": execution_replay_orchestrator,
        "skill_update_plan": skill_update_plan,
        "skill_update_audit": skill_update_audit,
        "forward_test_plan": forward_test_plan,
        "agent_rollout_harness": agent_rollout_harness,
        "agent_rollout_audit": agent_rollout_audit,
        "e2e_acceptance": e2e_acceptance,
        "smoke_test_plan": smoke_test_plan,
        "acceptance_handoff": acceptance_handoff,
        "verification_claim_audit": verification_claim_audit,
        "completion_evidence_audit": completion_evidence_audit,
    }
    protocol_compliance_audit = build_protocol_compliance_audit(request, phase_state, protocol_artifacts)
    record_phase(
        phase_state,
        "protocol_compliance_audit",
        "completed",
        inputs=["phase_state.yaml", "phase_state_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml", "output_boundary_audit.yaml", "plan-only artifacts", "verification_claim_audit.yaml", "completion_evidence_audit.yaml"],
        outputs=["protocol_compliance_audit.yaml"],
        gates=["plan-only artifacts remain plan-only", "request fingerprints do not store raw request values", "external results are request-supplied and contract-audited", "output directory is isolated from skill install roots", "completion claims require external evidence"],
    )
    pre_publish_artifacts = {
        "request": request,
        "phase_state": phase_state,
        "phase_state_audit": phase_state_audit,
        "protocol_compliance_audit": protocol_compliance_audit,
        "builder_runtime_audit": builder_runtime_audit,
        "agent_metadata_audit": agent_metadata_audit,
        "public_origin_audit": public_origin_audit,
        "module_inventory_audit": module_inventory_audit,
        "builder_baseline_audit": builder_baseline_audit,
        "skill_package_audit": skill_package_audit,
        "request_template_audit": request_template_audit,
        "request_audit": request_audit,
        "request_fingerprint": request_fingerprint,
        "external_result_contracts": external_result_contracts,
        "discovery_preflight": discovery_preflight,
        "discovery_report": discovery_report,
        "discovery_audit": discovery_audit,
        "discovery_match_audit": discovery_match_audit,
        "discovery_resolution_audit": discovery_resolution_audit,
        "source_grounding": source_grounding,
        "source_fetch_report": source_fetch_report,
        "source_fetch_boundary_audit": source_fetch_boundary_audit,
        "source_index": source_index,
        "source_parse_report": source_parse_report,
        "source_parsing_coverage": source_parsing_coverage,
        "source_parsing_audit": source_parsing_audit,
        "source_ingestion_audit": source_ingestion_audit,
        "evidence_cards": evidence_cards,
        "source_manifest": source_manifest,
        "evidence_coverage": evidence_coverage,
        "evidence_precedence": evidence_precedence,
        "evidence_claim_taxonomy_audit": evidence_claim_taxonomy_audit,
        "api_grounding": api_grounding,
        "interface_grounding": interface_grounding,
        "key_api_coverage_audit": key_api_coverage_audit,
        "backend_contract": backend_contract,
        "backend_extension_audit": backend_extension_audit,
        "environment_spec": environment_spec,
        "environment_install_plan": environment_install_plan,
        "resource_inventory": resource_inventory,
        "resource_boundary_audit": resource_boundary_audit,
        "tutorial_catalog": tutorial_catalog,
        "parameter_catalog": parameter_catalog,
        "task_catalog": task_catalog,
        "task_partition_decision_log": task_partition_decision_log,
        "task_type_router": router,
        "task_partition_audit": task_partition_audit,
        "task_conflict_matrix": task_conflict_matrix,
        "routing_fixture": routing_fixture,
        "eval_plan": eval_plan,
        "execution_trace_validation": execution_trace_validation,
        "execution_plan": execution_plan,
        "tutorial_reproduction_plan": tutorial_reproduction_plan,
        "execution_replay_orchestrator": execution_replay_orchestrator,
        "verification_claim_audit": verification_claim_audit,
        "contract_traceability": contract_traceability,
        "acceptance_suite": acceptance_suite,
        "eval_splits": eval_splits,
        "eval_result_judge": eval_result_judge,
        "eval_leakage_audit": eval_leakage_audit,
        "agent_rollout_result_judge": agent_rollout_result_judge,
        "draft_candidates": draft_candidates,
        "skill_spec": skill_spec,
        "review_summary": review_summary,
        "review_evolution": review_evolution,
        "review_evolution_plot": review_evolution_plot,
        "review_iteration_log": review_iteration_log,
        "review_prompt_contracts": review_prompt_contracts,
        "review_prompt_materials": review_prompt_materials,
        "review_prompt_suite_audit": review_prompt_suite_audit,
        "review_cursor": review_cursor,
        "patch_application": patch_application,
        "review_remediation_audit": review_remediation_audit,
        "review_optimizer_state": review_optimizer_state,
        "patch_safety_audit": patch_safety_audit,
        "patch_operation_contracts": patch_operation_contracts,
        "review_discipline_audit": review_discipline_audit,
        "rubric_grounding_audit": rubric_grounding_audit,
        "review_trajectory_audit": review_trajectory_audit,
        "skill_lint_report": lint_report,
        "child_metadata_audit": child_metadata_audit,
        "child_package_purity_audit": child_package_purity_audit,
        "draft_readiness": draft_readiness,
        "output_boundary_audit": output_boundary_audit,
        "skill_update_plan": skill_update_plan,
        "skill_update_audit": skill_update_audit,
        "forward_test_plan": forward_test_plan,
        "agent_rollout_harness": agent_rollout_harness,
        "agent_rollout_audit": agent_rollout_audit,
        "e2e_acceptance": e2e_acceptance,
        "smoke_test_plan": smoke_test_plan,
        "grounding_gate": grounding_gate,
        "api_surface_audit": api_surface_audit,
        "claim_consistency_audit": claim_consistency_audit,
        "child_reference_coverage": child_reference_coverage,
        "routing_metadata_audit": routing_metadata_audit,
        "source_grounding_audit": source_grounding_audit,
        "lineage_graph": lineage_graph,
        "workflow_invariant_audit": workflow_invariant_audit,
        "requirement_coverage": requirement_coverage,
        "completion_evidence_audit": completion_evidence_audit,
        "acceptance_handoff": acceptance_handoff,
        "artifact_contracts": artifact_contracts,
        "code_fence_audit": code_fence_audit,
        "public_safety_audit": public_safety_audit,
        "biological_claim_boundary_audit": biological_claim_boundary_audit,
    }
    artifact_validation = validate_artifact_bundle(pre_publish_artifacts, PRE_PUBLISH_ARTIFACTS)
    record_phase(
        phase_state,
        "artifact_validation",
        "completed",
        inputs=["pre-publish build artifacts"],
        outputs=["artifact_validation.yaml"],
        gates=["schema versions match", "phase state audit, protocol compliance audit, child metadata audit, child package purity audit, draft readiness, output boundary, skill update plan, skill update audit, forward test plan, agent rollout harness, E2E acceptance, completion evidence, and external result contracts pass", "discovery match audit, source parsing coverage, source parsing audit, source ingestion audit, source grounding audit, backend extension audit, environment install planning, resource boundary audit, evidence precedence, tutorial reproduction planning, verification claim audit, contract traceability, review prompt suite, review optimizer state, patch safety, patch operation contracts, review discipline, rubric grounding, review trajectory, API surface audit, key API coverage audit, child reference coverage, routing metadata audit, lineage, workflow invariants, and requirement coverage pass", "task routes, routing fixtures, grounding gates, audits, and eval scenarios exist"],
    )
    publish_gate = evaluate_publish_gate(
        request,
        discovery_report,
        discovery_audit,
        discovery_match_audit,
        discovery_resolution_audit,
        review_result,
        lint_report,
        child_metadata_audit,
        child_package_purity_audit,
        builder_runtime_audit,
        agent_metadata_audit,
        public_origin_audit,
        module_inventory_audit,
        builder_baseline_audit,
        skill_package_audit,
        request_template_audit,
        request_audit,
        request_fingerprint,
        external_result_contracts,
        phase_state_audit,
        draft_readiness,
        output_boundary_audit,
        skill_update_plan,
        skill_update_audit,
        forward_test_plan,
        agent_rollout_harness,
        agent_rollout_audit,
        execution_trace_validation,
        verification_claim_audit,
        artifact_validation,
        code_fence_audit,
        public_safety_audit,
        claim_consistency_audit,
        biological_claim_boundary_audit,
        child_reference_coverage,
        routing_metadata_audit,
        source_grounding_audit,
        source_fetch_boundary_audit,
        workflow_invariant_audit,
        requirement_coverage,
        api_surface_audit,
        key_api_coverage_audit,
        eval_splits,
        eval_result_judge,
        eval_leakage_audit,
        agent_rollout_result_judge,
        e2e_acceptance,
        smoke_test_plan,
        review_cursor,
        review_prompt_contracts,
        review_prompt_materials,
        review_prompt_suite_audit,
        review_iteration_log,
        patch_application,
        review_remediation_audit,
        review_optimizer_state,
        patch_safety_audit,
        patch_operation_contracts,
        review_discipline_audit,
        rubric_grounding_audit,
        review_trajectory_audit,
        tutorial_reproduction_plan,
        execution_replay_orchestrator,
        task_catalog,
        task_partition_decision_log,
        task_partition_audit,
        source_parsing_coverage,
        source_parsing_audit,
        source_ingestion_audit,
        backend_extension_audit,
        environment_install_plan,
        resource_boundary_audit,
        evidence_coverage,
        evidence_precedence,
        evidence_claim_taxonomy_audit,
        contract_traceability,
        lineage_graph,
        api_grounding,
        interface_grounding,
        environment_spec,
        tutorial_catalog,
        parameter_catalog,
        eval_plan,
        draft_candidates,
        grounding_gate,
        routing_fixture,
    )
    record_phase(
        phase_state,
        "publish_gate",
        "completed",
        inputs=["request_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml", "phase_state_audit.yaml", "skill_lint_report.yaml", "child_metadata_audit.yaml", "draft_readiness.yaml", "output_boundary_audit.yaml", "skill_update_plan.yaml", "skill_update_audit.yaml", "discovery_resolution_audit.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml", "agent_rollout_audit.yaml", "eval_leakage_audit.yaml", "agent_rollout_result_judge.yaml", "task_partition_decision_log.yaml", "task_partition_audit.yaml", "source_parsing_coverage.yaml", "source_parsing_audit.yaml", "source_ingestion_audit.yaml", "source_grounding_audit.yaml", "backend_extension_audit.yaml", "environment_install_plan.yaml", "resource_boundary_audit.yaml", "evidence_claim_taxonomy_audit.yaml", "review_prompt_contracts.yaml", "review_prompt_materials.yaml", "review_iteration_log.yaml", "review_cursor.yaml", "patch_application.yaml", "review_remediation_audit.yaml", "review_optimizer_state.yaml", "patch_safety_audit.yaml", "review_discipline_audit.yaml", "rubric_grounding_audit.yaml", "review_trajectory_audit.yaml", "contract_traceability.yaml", "tutorial_reproduction_plan.yaml", "verification_claim_audit.yaml", "child_reference_coverage.yaml", "routing_metadata_audit.yaml", "workflow_invariant_audit.yaml", "requirement_coverage.yaml", "review_summary.yaml", "discovery_report.yaml", "discovery_match_audit.yaml", "grounding_gate.yaml", "routing_fixture.yaml"],
        outputs=["publish_gate.yaml"],
        gates=["request audit pass", "request fingerprint pass", "phase state audit pass", "lint pass", "child metadata audit pass", "draft readiness pass", "output boundary pass", "skill update plan pass", "skill update audit pass", "discovery match audit pass", "forward test plan pass", "task partition decision log pass", "task partition audit pass", "source parsing coverage pass", "source parsing audit pass", "source ingestion audit pass", "source grounding audit pass", "backend extension audit pass", "environment install plan pass", "resource boundary audit pass", "evidence claim taxonomy audit pass", "review prompt contracts pass", "review prompt materials pass", "review iteration log pass", "review cursor pass", "patch application pass", "review remediation audit pass", "review optimizer state pass", "patch safety pass", "review discipline pass", "rubric grounding pass", "review trajectory pass", "contract traceability pass", "tutorial reproduction plan pass", "verification claim audit pass", "routing metadata audit pass", "requirement coverage pass", "review pass", "evidence refs present", "grounding gate pass", "verified tasks have trace_ref"],
    )
    candidate_registry = build_candidate_registry(
        request,
        draft_candidates,
        review_result,
        child_skill_dir,
        lint_report,
        publish_gate,
    )
    record_phase(
        phase_state,
        "candidate_registry",
        "completed",
        inputs=["draft_candidates.yaml", "review_summary.yaml", "skill_lint_report.yaml", "publish_gate.yaml"],
        outputs=["candidate_registry.yaml"],
        gates=["candidate version status mirrors publish gate"],
    )
    candidate_selection_audit = build_candidate_selection_audit(
        request,
        draft_candidates,
        candidate_registry,
        publish_gate,
        skill_update_plan,
        review_result,
        lint_report,
        draft_readiness,
        requirement_coverage,
    )
    record_phase(
        phase_state,
        "candidate_selection_audit",
        "completed",
        inputs=["draft_candidates.yaml", "candidate_registry.yaml", "publish_gate.yaml", "skill_update_plan.yaml", "review_summary.yaml", "skill_lint_report.yaml", "draft_readiness.yaml", "requirement_coverage.yaml"],
        outputs=["candidate_selection_audit.yaml"],
        gates=["active candidate selected", "selection rationale recorded", "single child-skill invariant preserved"],
    )
    candidate_promotion_audit = build_candidate_promotion_audit(
        request,
        draft_candidates,
        candidate_registry,
        candidate_selection_audit,
        publish_gate,
        skill_update_plan,
    )
    record_phase(
        phase_state,
        "candidate_promotion_audit",
        "completed",
        inputs=["draft_candidates.yaml", "candidate_registry.yaml", "candidate_selection_audit.yaml", "publish_gate.yaml", "skill_update_plan.yaml"],
        outputs=["candidate_promotion_audit.yaml"],
        gates=["selection audit pass", "active candidate exists", "candidate gate status mirrors publish gate", "reuse does not promote duplicate"],
    )
    release_package = build_release_package(
        request,
        child_skill_dir,
        publish_gate,
        candidate_registry,
        skill_update_plan,
        candidate_promotion_audit,
    )
    record_phase(
        phase_state,
        "release_package",
        "completed",
        inputs=["child_skill directory", "publish_gate.yaml", "candidate_registry.yaml", "candidate_promotion_audit.yaml"],
        outputs=["release_package.yaml"],
        gates=["manifest only", "does not copy files or install skills"],
    )
    final_candidate_audit = build_final_candidate_audit(
        request,
        candidate_registry,
        candidate_selection_audit,
        candidate_promotion_audit,
        release_package,
        skill_update_plan,
        publish_gate,
    )
    record_phase(
        phase_state,
        "final_candidate_audit",
        "completed",
        inputs=["candidate_registry.yaml", "candidate_selection_audit.yaml", "candidate_promotion_audit.yaml", "release_package.yaml", "skill_update_plan.yaml", "publish_gate.yaml"],
        outputs=["final_candidate_audit.yaml"],
        gates=["release package points to active candidate", "reuse does not finalize duplicate release", "required child-skill files match"],
    )
    candidate_evolution_audit = build_candidate_evolution_audit(
        request,
        draft_candidates,
        candidate_registry,
        candidate_selection_audit,
        candidate_promotion_audit,
        release_package,
        final_candidate_audit,
        publish_gate,
        skill_update_plan,
        review_iteration_log,
    )
    record_phase(
        phase_state,
        "candidate_evolution_audit",
        "completed",
        inputs=["draft_candidates.yaml", "candidate_registry.yaml", "candidate_selection_audit.yaml", "candidate_promotion_audit.yaml", "release_package.yaml", "final_candidate_audit.yaml", "review_iteration_log.yaml"],
        outputs=["candidate_evolution_audit.yaml"],
        gates=["candidate identity stable across release chain", "reuse does not promote duplicate", "review iteration count matches candidate registry"],
    )
    quality_report = build_quality_report(
        request,
        review_result,
        lint_report,
        artifact_validation,
        phase_state_audit,
        protocol_compliance_audit,
        builder_runtime_audit,
        agent_metadata_audit,
        public_origin_audit,
        module_inventory_audit,
        builder_baseline_audit,
        skill_package_audit,
        request_template_audit,
        request_audit,
        request_fingerprint,
        external_result_contracts,
        child_metadata_audit,
        child_package_purity_audit,
        output_boundary_audit,
        skill_update_plan,
        skill_update_audit,
        forward_test_plan,
        agent_rollout_harness,
        agent_rollout_audit,
        code_fence_audit,
        public_safety_audit,
        claim_consistency_audit,
        biological_claim_boundary_audit,
        child_reference_coverage,
        source_grounding_audit,
        source_fetch_boundary_audit,
        routing_metadata_audit,
        workflow_invariant_audit,
        requirement_coverage,
        completion_evidence_audit,
        acceptance_handoff,
        api_surface_audit,
        key_api_coverage_audit,
        publish_gate,
        discovery_audit,
        discovery_match_audit,
        discovery_resolution_audit,
        review_cursor,
        patch_application,
        review_remediation_audit,
        review_optimizer_state,
        patch_safety_audit,
        patch_operation_contracts,
        candidate_selection_audit,
        candidate_promotion_audit,
        final_candidate_audit,
        candidate_evolution_audit,
        review_discipline_audit,
        rubric_grounding_audit,
        review_trajectory_audit,
        task_catalog,
        task_partition_decision_log,
        task_partition_audit,
        source_parse_report,
        source_parsing_coverage,
        source_parsing_audit,
        source_ingestion_audit,
        backend_extension_audit,
        environment_install_plan,
        resource_boundary_audit,
        evidence_coverage,
        evidence_precedence,
        evidence_claim_taxonomy_audit,
        execution_trace_validation,
        execution_plan,
        tutorial_reproduction_plan,
        execution_replay_orchestrator,
        verification_claim_audit,
        contract_traceability,
        lineage_graph,
        acceptance_suite,
        eval_splits,
        eval_result_judge,
        eval_leakage_audit,
        agent_rollout_result_judge,
        e2e_acceptance,
        smoke_test_plan,
        draft_readiness,
        grounding_gate,
        routing_fixture,
        review_prompt_contracts,
        review_prompt_materials,
        review_prompt_suite_audit,
        review_iteration_log,
    )
    record_phase(
        phase_state,
        "quality_report",
        "completed",
        inputs=["request_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml", "request_template_audit.yaml", "agent_metadata_audit.yaml", "phase_state_audit.yaml", "review_summary.yaml", "discovery_match_audit.yaml", "discovery_resolution_audit.yaml", "module_inventory_audit.yaml", "builder_baseline_audit.yaml", "skill_package_audit.yaml", "source_parsing_coverage.yaml", "source_parsing_audit.yaml", "source_ingestion_audit.yaml", "source_grounding_audit.yaml", "environment_install_plan.yaml", "review_prompt_contracts.yaml", "review_prompt_materials.yaml", "review_prompt_suite_audit.yaml", "review_iteration_log.yaml", "review_cursor.yaml", "patch_application.yaml", "review_remediation_audit.yaml", "review_optimizer_state.yaml", "patch_safety_audit.yaml", "patch_operation_contracts.yaml", "candidate_selection_audit.yaml", "candidate_promotion_audit.yaml", "release_package.yaml", "final_candidate_audit.yaml", "candidate_evolution_audit.yaml", "review_discipline_audit.yaml", "rubric_grounding_audit.yaml", "review_trajectory_audit.yaml", "skill_lint_report.yaml", "child_metadata_audit.yaml", "draft_readiness.yaml", "output_boundary_audit.yaml", "skill_update_plan.yaml", "skill_update_audit.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml", "agent_rollout_audit.yaml", "agent_rollout_result_judge.yaml", "e2e_acceptance.yaml", "completion_evidence_audit.yaml", "task_partition_decision_log.yaml", "task_partition_audit.yaml", "evidence_precedence.yaml", "evidence_claim_taxonomy_audit.yaml", "tutorial_reproduction_plan.yaml", "verification_claim_audit.yaml", "contract_traceability.yaml", "api_surface_audit.yaml", "key_api_coverage_audit.yaml", "claim_consistency_audit.yaml", "biological_claim_boundary_audit.yaml", "child_reference_coverage.yaml", "routing_metadata_audit.yaml", "workflow_invariant_audit.yaml", "requirement_coverage.yaml", "lineage_graph.yaml", "eval_splits.yaml", "eval_result_judge.yaml", "eval_leakage_audit.yaml", "artifact_validation.yaml", "code_fence_audit.yaml", "public_safety_audit.yaml", "publish_gate.yaml"],
        outputs=["quality_report.yaml"],
        gates=["all quality scorecards summarized", "routing and grounding blockers summarized", "task contract blockers summarized", "candidate selection, promotion, evolution, and finalization summarized"],
    )
    codex_publish_adapter = build_codex_publish_adapter(
        request,
        release_package,
        skill_update_plan,
        candidate_promotion_audit,
        final_candidate_audit,
    )
    record_phase(
        phase_state,
        "codex_publish_adapter",
        "completed",
        inputs=["release_package.yaml", "skill_update_plan.yaml", "candidate_promotion_audit.yaml", "final_candidate_audit.yaml"],
        outputs=["codex_publish_adapter.yaml"],
        gates=["plan only", "Codex action matches reuse/update/create decision", "final candidate audit pass", "required child-skill files are present"],
    )
    install_readiness = build_install_readiness(request, child_skill_dir, release_package)
    record_phase(
        phase_state,
        "install_readiness",
        "completed",
        inputs=["child_skill directory", "release_package.yaml"],
        outputs=["install_readiness.yaml"],
        gates=["required install files exist", "no build artifacts inside public child skill", "release manifest covers required files"],
    )
    manifest = publish_manifest(request, child_skill_dir, lint_report, publish_gate, release_package, skill_update_plan)
    retention_plan = planned_output_retention(request)
    manifest["run_manifest_path"] = "run_manifest.yaml"
    manifest["output_retention_path"] = retention_plan["output_retention_path"]
    manifest["generation_process_doc"] = retention_plan["generation_process_doc"]
    manifest["install_readiness_status"] = install_readiness.get("status")
    manifest["codex_publish_adapter_status"] = codex_publish_adapter.get("status")
    publish_manifest_audit = build_publish_manifest_audit(
        request,
        manifest,
        publish_gate,
        release_package,
        skill_update_plan,
        install_readiness,
        codex_publish_adapter,
        final_candidate_audit,
    )
    record_phase(
        phase_state,
        "publish_manifest",
        "completed",
        inputs=["publish_gate.yaml", "release_package.yaml", "install_readiness.yaml", "codex_publish_adapter.yaml"],
        outputs=["publish_manifest.yaml"],
        gates=["status mirrors publish gate", "install readiness status recorded", "Codex publish adapter status recorded"],
    )
    record_phase(
        phase_state,
        "publish_manifest_audit",
        "completed",
        inputs=["publish_manifest.yaml", "publish_gate.yaml", "release_package.yaml", "skill_update_plan.yaml", "install_readiness.yaml", "final_candidate_audit.yaml"],
        outputs=["publish_manifest_audit.yaml"],
        gates=["recommended action consistency", "final candidate audit pass", "update target retained", "reuse does not publish duplicate"],
    )
    score_report = build_score_report(
        request,
        review_evolution,
        rubric_grounding_audit,
        quality_report,
        publish_gate,
        candidate_selection_audit,
        candidate_promotion_audit,
        final_candidate_audit,
        candidate_evolution_audit,
        codex_publish_adapter,
        install_readiness,
        publish_manifest_audit,
    )
    record_phase(
        phase_state,
        "score_report",
        "completed",
        inputs=["review_evolution.yaml", "rubric_grounding_audit.yaml", "quality_report.yaml", "publish_gate.yaml", "candidate_selection_audit.yaml", "candidate_promotion_audit.yaml", "final_candidate_audit.yaml", "candidate_evolution_audit.yaml", "codex_publish_adapter.yaml", "install_readiness.yaml", "publish_manifest_audit.yaml"],
        outputs=["score_report.yaml"],
        gates=["review, quality, publish, candidate, adapter, install, and manifest gates summarized", "blocking scorecards recorded"],
    )
    builder_version_audit = build_builder_version_audit(
        request,
        {
            "request": request,
            "request_audit": request_audit,
            "request_fingerprint": request_fingerprint,
            "external_result_contracts": external_result_contracts,
        "builder_runtime_audit": builder_runtime_audit,
        "agent_metadata_audit": agent_metadata_audit,
        "public_origin_audit": public_origin_audit,
        "module_inventory_audit": module_inventory_audit,
        "builder_baseline_audit": builder_baseline_audit,
        "skill_package_audit": skill_package_audit,
            "request_template_audit": request_template_audit,
            "discovery_resolution_audit": discovery_resolution_audit,
            "child_package_purity_audit": child_package_purity_audit,
            "source_grounding": source_grounding,
            "source_manifest": source_manifest,
            "source_fetch_boundary_audit": source_fetch_boundary_audit,
            "evidence_claim_taxonomy_audit": evidence_claim_taxonomy_audit,
            "key_api_coverage_audit": key_api_coverage_audit,
            "eval_leakage_audit": eval_leakage_audit,
            "agent_rollout_result_judge": agent_rollout_result_judge,
            "e2e_acceptance": e2e_acceptance,
            "smoke_test_plan": smoke_test_plan,
            "completion_evidence_audit": completion_evidence_audit,
            "acceptance_handoff": acceptance_handoff,
            "protocol_compliance_audit": protocol_compliance_audit,
            "execution_replay_orchestrator": execution_replay_orchestrator,
            "task_catalog": task_catalog,
            "task_type_router": router,
            "biological_claim_boundary_audit": biological_claim_boundary_audit,
            "review_summary": review_summary,
            "draft_candidates": draft_candidates,
            "candidate_registry": candidate_registry,
            "candidate_selection_audit": candidate_selection_audit,
            "candidate_promotion_audit": candidate_promotion_audit,
            "release_package": release_package,
            "final_candidate_audit": final_candidate_audit,
            "candidate_evolution_audit": candidate_evolution_audit,
            "codex_publish_adapter": codex_publish_adapter,
            "install_readiness": install_readiness,
            "publish_manifest_audit": publish_manifest_audit,
            "skill_spec": skill_spec,
            "publish_manifest": manifest,
        },
    )
    record_phase(
        phase_state,
        "builder_version_audit",
        "completed",
        inputs=["core versioned artifacts", "publish_manifest.yaml", "skill_spec.yaml"],
        outputs=["builder_version_audit.yaml"],
        gates=["core artifacts share schema version", "release-facing artifacts carry builder version"],
    )
    release_action_audit = build_release_action_audit(
        request,
        skill_update_plan,
        skill_update_audit,
        publish_gate,
        release_package,
        candidate_promotion_audit,
        final_candidate_audit,
        install_readiness,
        codex_publish_adapter,
        manifest,
        publish_manifest_audit,
    )
    record_phase(
        phase_state,
        "release_action_audit",
        "completed",
        inputs=["skill_update_plan.yaml", "skill_update_audit.yaml", "publish_gate.yaml", "release_package.yaml", "candidate_promotion_audit.yaml", "final_candidate_audit.yaml", "install_readiness.yaml", "codex_publish_adapter.yaml", "publish_manifest.yaml", "publish_manifest_audit.yaml"],
        outputs=["release_action_audit.yaml"],
        gates=["create/update/reuse action statuses agree", "reuse is no-copy", "update target retained", "create/update candidates finalized"],
    )
    record_phase(
        phase_state,
        "artifact_closure_audit",
        "completed",
        inputs=["artifact_contracts.yaml", "phase_state.yaml", "required artifact list", "pre-publish artifact list"],
        outputs=["artifact_closure_audit.yaml"],
        gates=["required artifacts have contracts", "pre-publish artifacts are available", "run write plan covers required artifacts"],
    )
    closure_available_artifacts = {
        **pre_publish_artifacts,
        "artifact_validation": artifact_validation,
        "publish_gate": publish_gate,
        "candidate_registry": candidate_registry,
        "candidate_selection_audit": candidate_selection_audit,
        "candidate_promotion_audit": candidate_promotion_audit,
        "release_package": release_package,
        "final_candidate_audit": final_candidate_audit,
        "candidate_evolution_audit": candidate_evolution_audit,
        "quality_report": quality_report,
        "score_report": score_report,
        "codex_publish_adapter": codex_publish_adapter,
        "install_readiness": install_readiness,
        "publish_manifest": manifest,
        "publish_manifest_audit": publish_manifest_audit,
        "release_action_audit": release_action_audit,
        "builder_version_audit": builder_version_audit,
    }
    artifact_closure_audit = build_artifact_closure_audit(
        request,
        REQUIRED_TOP_LEVEL_ARTIFACTS,
        PRE_PUBLISH_ARTIFACTS,
        artifact_contracts,
        phase_state,
        closure_available_artifacts,
        planned_write_artifacts=REQUIRED_TOP_LEVEL_ARTIFACTS,
    )
    architecture_completeness_audit = build_architecture_completeness_audit(
        request,
        phase_state,
        {
            "builder_runtime_audit": builder_runtime_audit,
            "agent_metadata_audit": agent_metadata_audit,
            "public_origin_audit": public_origin_audit,
            "module_inventory_audit": module_inventory_audit,
            "builder_baseline_audit": builder_baseline_audit,
            "skill_package_audit": skill_package_audit,
            "request_template_audit": request_template_audit,
            "request_audit": request_audit,
            "request_fingerprint": request_fingerprint,
            "external_result_contracts": external_result_contracts,
            "builder_version_audit": builder_version_audit,
            "phase_state_audit": phase_state_audit,
            "protocol_compliance_audit": protocol_compliance_audit,
            "discovery_audit": discovery_audit,
            "discovery_match_audit": discovery_match_audit,
            "discovery_resolution_audit": discovery_resolution_audit,
            "source_parsing_audit": source_parsing_audit,
            "source_fetch_boundary_audit": source_fetch_boundary_audit,
            "source_ingestion_audit": source_ingestion_audit,
            "source_grounding_audit": source_grounding_audit,
            "key_api_coverage_audit": key_api_coverage_audit,
            "verification_claim_audit": verification_claim_audit,
            "evidence_claim_taxonomy_audit": evidence_claim_taxonomy_audit,
            "biological_claim_boundary_audit": biological_claim_boundary_audit,
            "backend_extension_audit": backend_extension_audit,
            "resource_inventory": resource_inventory,
            "resource_boundary_audit": resource_boundary_audit,
            "eval_leakage_audit": eval_leakage_audit,
            "agent_rollout_result_judge": agent_rollout_result_judge,
            "e2e_acceptance": e2e_acceptance,
            "smoke_test_plan": smoke_test_plan,
            "task_partition_decision_log": task_partition_decision_log,
            "task_partition_audit": task_partition_audit,
            "child_metadata_audit": child_metadata_audit,
            "child_package_purity_audit": child_package_purity_audit,
            "routing_metadata_audit": routing_metadata_audit,
            "review_prompt_contracts": review_prompt_contracts,
            "review_prompt_materials": review_prompt_materials,
            "review_prompt_suite_audit": review_prompt_suite_audit,
            "review_iteration_log": review_iteration_log,
            "review_remediation_audit": review_remediation_audit,
            "review_optimizer_state": review_optimizer_state,
            "patch_safety_audit": patch_safety_audit,
            "patch_operation_contracts": patch_operation_contracts,
            "rubric_grounding_audit": rubric_grounding_audit,
            "review_trajectory_audit": review_trajectory_audit,
            "tutorial_reproduction_plan": tutorial_reproduction_plan,
            "execution_replay_orchestrator": execution_replay_orchestrator,
            "contract_traceability": contract_traceability,
            "agent_rollout_audit": agent_rollout_audit,
            "agent_rollout_result_judge": agent_rollout_result_judge,
            "e2e_acceptance": e2e_acceptance,
            "smoke_test_plan": smoke_test_plan,
            "artifact_validation": artifact_validation,
            "workflow_invariant_audit": workflow_invariant_audit,
            "requirement_coverage": requirement_coverage,
            "completion_evidence_audit": completion_evidence_audit,
            "acceptance_handoff": acceptance_handoff,
            "skill_update_audit": skill_update_audit,
            "candidate_selection_audit": candidate_selection_audit,
            "candidate_promotion_audit": candidate_promotion_audit,
            "final_candidate_audit": final_candidate_audit,
            "candidate_evolution_audit": candidate_evolution_audit,
            "codex_publish_adapter": codex_publish_adapter,
            "publish_gate": publish_gate,
            "install_readiness": install_readiness,
            "publish_manifest_audit": publish_manifest_audit,
            "release_action_audit": release_action_audit,
            "artifact_closure_audit": artifact_closure_audit,
        },
    )
    record_phase(
        phase_state,
        "architecture_completeness_audit",
        "completed",
        inputs=["phase_state.yaml", "focused audit artifacts", "publish_manifest_audit.yaml", "artifact_closure_audit.yaml"],
        outputs=["architecture_completeness_audit.yaml"],
        gates=["core architecture phase families covered", "required gate artifacts passed", "publish chain closed", "artifact closure passed"],
    )
    record_phase(
        phase_state,
        "completion_audit",
        "completed",
        inputs=["builder_runtime_audit.yaml", "agent_metadata_audit.yaml", "public_origin_audit.yaml", "module_inventory_audit.yaml", "builder_baseline_audit.yaml", "skill_package_audit.yaml", "request_template_audit.yaml", "builder_version_audit.yaml", "request_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml", "phase_state_audit.yaml", "protocol_compliance_audit.yaml", "requirement_coverage.yaml", "completion_evidence_audit.yaml", "acceptance_handoff.yaml", "architecture_completeness_audit.yaml", "agent_rollout_harness.yaml", "agent_rollout_audit.yaml", "eval_leakage_audit.yaml", "agent_rollout_result_judge.yaml", "e2e_acceptance.yaml", "routing_metadata_audit.yaml", "artifact_validation.yaml", "artifact_closure_audit.yaml", "publish_gate.yaml", "candidate_selection_audit.yaml", "candidate_promotion_audit.yaml", "final_candidate_audit.yaml", "candidate_evolution_audit.yaml", "quality_report.yaml", "score_report.yaml", "release_package.yaml", "release_action_audit.yaml", "codex_publish_adapter.yaml", "install_readiness.yaml", "publish_manifest.yaml", "publish_manifest_audit.yaml", "skill_update_plan.yaml", "skill_update_audit.yaml", "discovery_match_audit.yaml", "discovery_resolution_audit.yaml", "resource_boundary_audit.yaml", "evidence_claim_taxonomy_audit.yaml", "child_metadata_audit.yaml", "child_package_purity_audit.yaml", "biological_claim_boundary_audit.yaml", "review_prompt_contracts.yaml", "review_prompt_materials.yaml", "review_prompt_suite_audit.yaml", "review_iteration_log.yaml", "review_remediation_audit.yaml", "review_optimizer_state.yaml", "patch_safety_audit.yaml", "patch_operation_contracts.yaml", "review_trajectory_audit.yaml", "source_fetch_boundary_audit.yaml", "source_ingestion_audit.yaml", "source_grounding_audit.yaml", "verification_claim_audit.yaml", "backend_extension_audit.yaml", "phase_state.yaml"],
        outputs=["completion_audit.yaml"],
        gates=["final semantic gates pass", "release, install, and manifest actions agree", "artifact closure passes", "run_manifest.yaml path is planned"],
    )
    completion_audit = build_completion_audit(
        request,
        phase_state,
        builder_runtime_audit,
        agent_metadata_audit,
        public_origin_audit,
        module_inventory_audit,
        builder_baseline_audit,
        skill_package_audit,
        request_template_audit,
        builder_version_audit,
        request_audit,
        request_fingerprint,
        external_result_contracts,
        phase_state_audit,
        protocol_compliance_audit,
        requirement_coverage,
        completion_evidence_audit,
        acceptance_handoff,
        architecture_completeness_audit,
        artifact_validation,
        publish_gate,
        quality_report,
        score_report,
        release_package,
        install_readiness,
        manifest,
        publish_manifest_audit,
        skill_update_plan,
        skill_update_audit,
        discovery_match_audit,
        discovery_resolution_audit,
        review_optimizer_state,
        patch_safety_audit,
        patch_operation_contracts,
        candidate_selection_audit,
        candidate_promotion_audit,
        final_candidate_audit,
        candidate_evolution_audit,
        artifact_closure_audit,
        source_fetch_boundary_audit,
        source_ingestion_audit,
        source_grounding_audit,
        key_api_coverage_audit,
        verification_claim_audit,
        execution_replay_orchestrator,
        backend_extension_audit,
        resource_boundary_audit,
        evidence_claim_taxonomy_audit,
        child_metadata_audit,
        child_package_purity_audit,
        biological_claim_boundary_audit,
        review_prompt_contracts,
        review_prompt_materials,
        review_prompt_suite_audit,
        review_iteration_log,
        review_remediation_audit,
        review_trajectory_audit,
        agent_rollout_harness,
        agent_rollout_audit,
        eval_leakage_audit,
        agent_rollout_result_judge,
        e2e_acceptance,
        smoke_test_plan,
        routing_metadata_audit,
        codex_publish_adapter,
        release_action_audit,
    )
    record_phase(
        phase_state,
        "build_timeline",
        "completed",
        inputs=["phase_state.yaml", "review_iterations.jsonl", "publish_gate.yaml", "quality_report.yaml"],
        outputs=["build_timeline.yaml"],
        gates=["phase, review, and gate events summarized"],
    )
    build_timeline_report = build_timeline(request, phase_state, review_result, publish_gate, quality_report)
    build_timeline_audit_report = build_timeline_audit(
        request,
        build_timeline_report,
        phase_state,
        review_result,
        publish_gate,
        quality_report,
    )
    record_phase(
        phase_state,
        "build_timeline_audit",
        "completed",
        inputs=["build_timeline.yaml", "phase_state.yaml", "review_summary.yaml", "publish_gate.yaml", "quality_report.yaml"],
        outputs=["build_timeline_audit.yaml"],
        gates=["timeline event ids unique", "phase and review event counts match source artifacts", "publish and quality gate events present"],
    )
    run_scorecard = build_run_scorecard(
        request,
        score_report,
        quality_report,
        completion_audit,
        release_action_audit,
        manifest,
        build_timeline_report,
        build_timeline_audit_report,
    )
    run_scorecard_markdown = render_run_scorecard_markdown(
        run_scorecard,
        score_report,
        quality_report,
        completion_audit,
        release_action_audit,
        build_timeline_report,
        build_timeline_audit_report,
    )
    record_phase(
        phase_state,
        "run_scorecard",
        "completed",
        inputs=["score_report.yaml", "quality_report.yaml", "completion_audit.yaml", "release_action_audit.yaml", "publish_manifest.yaml", "build_timeline.yaml", "build_timeline_audit.yaml"],
        outputs=["run_scorecard.yaml", "run_scorecard.md"],
        gates=["human-readable run verdict rendered", "run artifact only", "does not override publish gates"],
    )
    record_phase(
        phase_state,
        "run_manifest",
        "completed",
        inputs=["written run artifacts", "child_skill directory"],
        outputs=["run_manifest.yaml"],
        gates=["file hashes recorded", "downloaded sources excluded from public release manifest"],
    )

    write_data(out / "request.yaml", request)
    write_data(out / "phase_state.yaml", phase_state)
    write_data(out / "phase_state_audit.yaml", phase_state_audit)
    write_data(out / "protocol_compliance_audit.yaml", protocol_compliance_audit)
    write_data(out / "builder_runtime_audit.yaml", builder_runtime_audit)
    write_data(out / "agent_metadata_audit.yaml", agent_metadata_audit)
    write_data(out / "public_origin_audit.yaml", public_origin_audit)
    write_data(out / "module_inventory_audit.yaml", module_inventory_audit)
    write_data(out / "builder_baseline_audit.yaml", builder_baseline_audit)
    write_data(out / "skill_package_audit.yaml", skill_package_audit)
    write_data(out / "request_template_audit.yaml", request_template_audit)
    write_data(out / "builder_version_audit.yaml", builder_version_audit)
    write_data(out / "request_audit.yaml", request_audit)
    write_data(out / "request_fingerprint.yaml", request_fingerprint)
    write_data(out / "external_result_contracts.yaml", external_result_contracts)
    write_data(out / "discovery_preflight.yaml", discovery_preflight)
    write_data(out / "discovery_report.yaml", discovery_report)
    write_data(out / "discovery_audit.yaml", discovery_audit)
    write_data(out / "discovery_match_audit.yaml", discovery_match_audit)
    write_data(out / "discovery_resolution_audit.yaml", discovery_resolution_audit)
    write_data(out / "source_grounding.yaml", source_grounding)
    write_data(out / "source_fetch_report.yaml", source_fetch_report)
    write_data(out / "source_fetch_boundary_audit.yaml", source_fetch_boundary_audit)
    write_data(out / "source_index.yaml", source_index)
    write_data(out / "source_parse_report.yaml", source_parse_report)
    write_data(out / "source_parsing_coverage.yaml", source_parsing_coverage)
    write_data(out / "source_parsing_audit.yaml", source_parsing_audit)
    write_data(out / "source_ingestion_audit.yaml", source_ingestion_audit)
    write_data(out / "verification_claim_audit.yaml", verification_claim_audit)
    write_data(out / "evidence_cards.yaml", evidence_cards)
    write_data(out / "evidence_coverage.yaml", evidence_coverage)
    write_data(out / "evidence_precedence.yaml", evidence_precedence)
    write_data(out / "evidence_claim_taxonomy_audit.yaml", evidence_claim_taxonomy_audit)
    write_data(out / "source_manifest.yaml", source_manifest)
    write_data(out / "tutorial_catalog.yaml", tutorial_catalog)
    write_data(out / "api_grounding.yaml", api_grounding)
    write_data(out / "interface_grounding.yaml", interface_grounding)
    write_data(out / "key_api_coverage_audit.yaml", key_api_coverage_audit)
    write_data(out / "backend_contract.yaml", backend_contract)
    write_data(out / "backend_extension_audit.yaml", backend_extension_audit)
    write_data(out / "environment_spec.yaml", environment_spec)
    write_data(out / "environment_install_plan.yaml", environment_install_plan)
    write_data(out / "resource_inventory.yaml", resource_inventory)
    write_data(out / "resource_boundary_audit.yaml", resource_boundary_audit)
    write_data(out / "parameter_catalog.yaml", parameter_catalog)
    write_data(out / "task_catalog.yaml", task_catalog)
    write_data(out / "task_partition_decision_log.yaml", task_partition_decision_log)
    write_data(out / "task_type_router.yaml", router)
    write_data(out / "task_partition_audit.yaml", task_partition_audit)
    write_data(out / "task_conflict_matrix.yaml", task_conflict_matrix)
    write_data(out / "routing_fixture.yaml", routing_fixture)
    write_data(out / "eval_plan.yaml", eval_plan)
    write_data(out / "execution_trace_validation.yaml", execution_trace_validation)
    write_data(out / "execution_plan.yaml", execution_plan)
    write_data(out / "tutorial_reproduction_plan.yaml", tutorial_reproduction_plan)
    write_data(out / "execution_replay_orchestrator.yaml", execution_replay_orchestrator)
    write_data(out / "contract_traceability.yaml", contract_traceability)
    write_data(out / "acceptance_suite.yaml", acceptance_suite)
    write_data(out / "eval_splits.yaml", eval_splits)
    write_data(out / "eval_result_judge.yaml", eval_result_judge)
    write_data(out / "eval_leakage_audit.yaml", eval_leakage_audit)
    write_data(out / "agent_rollout_result_judge.yaml", agent_rollout_result_judge)
    write_data(out / "e2e_acceptance.yaml", e2e_acceptance)
    write_data(out / "smoke_test_plan.yaml", smoke_test_plan)
    write_data(out / "draft_candidates.yaml", draft_candidates)
    write_data(out / "candidate_registry.yaml", candidate_registry)
    write_data(out / "candidate_selection_audit.yaml", candidate_selection_audit)
    write_data(out / "candidate_promotion_audit.yaml", candidate_promotion_audit)
    write_data(out / "release_package.yaml", release_package)
    write_data(out / "final_candidate_audit.yaml", final_candidate_audit)
    write_data(out / "candidate_evolution_audit.yaml", candidate_evolution_audit)
    write_data(out / "codex_publish_adapter.yaml", codex_publish_adapter)
    write_data(out / "install_readiness.yaml", install_readiness)
    write_data(out / "skill_spec.yaml", skill_spec)
    write_text(out / "review_log.jsonl", "")
    write_text(out / "review_iterations.jsonl", "")
    for iteration in review_result["iterations"]:
        append_jsonl(out / "review_iterations.jsonl", iteration)
        for finding in iteration.get("findings", []):
            append_jsonl(
                out / "review_log.jsonl",
                {
                    "iteration": iteration["iteration"],
                    **finding,
                },
            )
    write_data(out / "review_summary.yaml", review_summary)
    write_data(out / "review_evolution.yaml", review_evolution)
    write_data(out / "review_evolution_plot.yaml", review_evolution_plot)
    write_text(out / "review_evolution_plot.svg", review_evolution_svg)
    write_data(out / "review_iteration_log.yaml", review_iteration_log)
    write_text(out / "review_iteration_log.md", review_iteration_log_markdown)
    write_data(out / "review_prompt_contracts.yaml", review_prompt_contracts)
    write_data(out / "review_prompt_materials.yaml", review_prompt_materials)
    write_data(out / "review_prompt_suite_audit.yaml", review_prompt_suite_audit)
    write_data(out / "review_cursor.yaml", review_cursor)
    write_data(out / "patch_application.yaml", patch_application)
    write_data(out / "review_remediation_audit.yaml", review_remediation_audit)
    write_data(out / "review_optimizer_state.yaml", review_optimizer_state)
    write_data(out / "patch_safety_audit.yaml", patch_safety_audit)
    write_data(out / "patch_operation_contracts.yaml", patch_operation_contracts)
    write_data(out / "review_discipline_audit.yaml", review_discipline_audit)
    write_data(out / "rubric_grounding_audit.yaml", rubric_grounding_audit)
    write_data(out / "review_trajectory_audit.yaml", review_trajectory_audit)
    write_data(out / "skill_lint_report.yaml", lint_report)
    write_data(out / "child_metadata_audit.yaml", child_metadata_audit)
    write_data(out / "child_package_purity_audit.yaml", child_package_purity_audit)
    write_data(out / "draft_readiness.yaml", draft_readiness)
    write_data(out / "output_boundary_audit.yaml", output_boundary_audit)
    write_data(out / "skill_update_plan.yaml", skill_update_plan)
    write_data(out / "skill_update_audit.yaml", skill_update_audit)
    write_data(out / "forward_test_plan.yaml", forward_test_plan)
    write_data(out / "agent_rollout_harness.yaml", agent_rollout_harness)
    write_data(out / "agent_rollout_audit.yaml", agent_rollout_audit)
    write_data(out / "grounding_gate.yaml", grounding_gate)
    write_data(out / "api_surface_audit.yaml", api_surface_audit)
    write_data(out / "claim_consistency_audit.yaml", claim_consistency_audit)
    write_data(out / "biological_claim_boundary_audit.yaml", biological_claim_boundary_audit)
    write_data(out / "child_reference_coverage.yaml", child_reference_coverage)
    write_data(out / "routing_metadata_audit.yaml", routing_metadata_audit)
    write_data(out / "source_grounding_audit.yaml", source_grounding_audit)
    write_data(out / "lineage_graph.yaml", lineage_graph)
    write_data(out / "workflow_invariant_audit.yaml", workflow_invariant_audit)
    write_data(out / "requirement_coverage.yaml", requirement_coverage)
    write_data(out / "completion_evidence_audit.yaml", completion_evidence_audit)
    write_data(out / "acceptance_handoff.yaml", acceptance_handoff)
    write_text(out / "acceptance_handoff.md", acceptance_handoff_markdown)
    write_data(out / "architecture_completeness_audit.yaml", architecture_completeness_audit)
    write_data(out / "artifact_contracts.yaml", artifact_contracts)
    write_data(out / "artifact_closure_audit.yaml", artifact_closure_audit)
    write_data(out / "artifact_validation.yaml", artifact_validation)
    write_data(out / "code_fence_audit.yaml", code_fence_audit)
    write_data(out / "public_safety_audit.yaml", public_safety_audit)
    write_data(out / "publish_gate.yaml", publish_gate)
    write_data(out / "quality_report.yaml", quality_report)
    write_data(out / "score_report.yaml", score_report)
    write_data(out / "publish_manifest.yaml", manifest)
    write_data(out / "publish_manifest_audit.yaml", publish_manifest_audit)
    write_data(out / "release_action_audit.yaml", release_action_audit)
    write_data(out / "completion_audit.yaml", completion_audit)
    write_data(out / "build_timeline.yaml", build_timeline_report)
    write_data(out / "build_timeline_audit.yaml", build_timeline_audit_report)
    write_data(out / "run_scorecard.yaml", run_scorecard)
    write_text(out / "run_scorecard.md", run_scorecard_markdown)
    run_manifest = build_run_manifest(request, out, manifest)
    write_data(out / "run_manifest.yaml", run_manifest)
    output_retention = build_output_retention(
        request,
        out,
        run_manifest,
        task_catalog,
        review_result,
        publish_gate,
    )
    manifest["output_retention_status"] = output_retention.get("status")
    record_phase(
        phase_state,
        "output_retention",
        "completed",
        inputs=["run_manifest.yaml", "publish_manifest.yaml", "root build artifacts"],
        outputs=["output_retention.yaml"],
        gates=["final child skill retained", "process artifacts retained or cleaned", "cleanup failures block publish"],
    )
    if output_retention.get("status") != "pass":
        manifest["status"] = "blocked"
        manifest.setdefault("blocking_findings", []).append(
            {
                "severity": "error",
                "code": "output_retention_failed",
                "message": "Output retention or cleanup failed; publish is blocked until retained artifact integrity is fixed.",
            }
        )
    phase_state["phases"] = [phase for phase in phase_state.get("phases", []) if phase.get("name") != "artifact_validation"]
    record_phase(
        phase_state,
        "artifact_validation",
        "completed",
        inputs=["required top-level artifacts", "post-cleanup retained artifacts", "run_manifest.yaml"],
        outputs=["artifact_validation.yaml"],
        gates=["schema versions match", "required final artifacts exist", "post-cleanup lifecycle artifact validates"],
    )
    phase_state_audit = build_phase_state_audit(request, phase_state, artifact_contracts)
    publish_manifest_audit = build_publish_manifest_audit(
        request,
        manifest,
        publish_gate,
        release_package,
        skill_update_plan,
        install_readiness,
        codex_publish_adapter,
        final_candidate_audit,
    )
    write_data(out / "publish_manifest.yaml", manifest)
    write_data(out / "publish_manifest_audit.yaml", publish_manifest_audit)
    write_data(out / "phase_state.yaml", phase_state)
    write_data(out / "phase_state_audit.yaml", phase_state_audit)
    output_retention = refresh_retained_artifacts(
        out,
        output_retention,
        ["publish_manifest.yaml", "publish_manifest_audit.yaml", "phase_state.yaml", "phase_state_audit.yaml"],
    )
    run_manifest = build_run_manifest(request, out, manifest)
    write_data(out / "run_manifest.yaml", run_manifest)
    final_artifacts = load_artifacts_for_final_validation(
        out,
        manifest,
        FINAL_VALIDATION_ARTIFACTS,
    )
    artifact_validation = validate_artifact_bundle(final_artifacts, FINAL_VALIDATION_ARTIFACTS)
    if artifact_validation.get("status") != "pass":
        manifest["status"] = "blocked"
        manifest.setdefault("blocking_findings", []).append(
            {
                "severity": "error",
                "code": "final_artifact_validation_failed",
                "message": "Final retained/root artifact validation failed; publish is blocked until required artifacts are consistent.",
            }
        )
    publish_manifest_audit = build_publish_manifest_audit(
        request,
        manifest,
        publish_gate,
        release_package,
        skill_update_plan,
        install_readiness,
        codex_publish_adapter,
        final_candidate_audit,
    )
    release_action_audit = build_release_action_audit(
        request,
        skill_update_plan,
        skill_update_audit,
        publish_gate,
        release_package,
        candidate_promotion_audit,
        final_candidate_audit,
        install_readiness,
        codex_publish_adapter,
        manifest,
        publish_manifest_audit,
    )
    score_report = build_score_report(
        request,
        review_evolution,
        rubric_grounding_audit,
        quality_report,
        publish_gate,
        candidate_selection_audit,
        candidate_promotion_audit,
        final_candidate_audit,
        candidate_evolution_audit,
        codex_publish_adapter,
        install_readiness,
        publish_manifest_audit,
    )
    completion_audit = build_completion_audit(
        request,
        phase_state,
        builder_runtime_audit,
        agent_metadata_audit,
        public_origin_audit,
        module_inventory_audit,
        builder_baseline_audit,
        skill_package_audit,
        request_template_audit,
        builder_version_audit,
        request_audit,
        request_fingerprint,
        external_result_contracts,
        phase_state_audit,
        protocol_compliance_audit,
        requirement_coverage,
        completion_evidence_audit,
        acceptance_handoff,
        architecture_completeness_audit,
        artifact_validation,
        publish_gate,
        quality_report,
        score_report,
        release_package,
        install_readiness,
        manifest,
        publish_manifest_audit,
        skill_update_plan,
        skill_update_audit,
        discovery_match_audit,
        discovery_resolution_audit,
        review_optimizer_state,
        patch_safety_audit,
        patch_operation_contracts,
        candidate_selection_audit,
        candidate_promotion_audit,
        final_candidate_audit,
        candidate_evolution_audit,
        artifact_closure_audit,
        source_fetch_boundary_audit,
        source_ingestion_audit,
        source_grounding_audit,
        key_api_coverage_audit,
        verification_claim_audit,
        execution_replay_orchestrator,
        backend_extension_audit,
        resource_boundary_audit,
        evidence_claim_taxonomy_audit,
        child_metadata_audit,
        child_package_purity_audit,
        biological_claim_boundary_audit,
        review_prompt_contracts,
        review_prompt_materials,
        review_prompt_suite_audit,
        review_iteration_log,
        review_remediation_audit,
        review_trajectory_audit,
        agent_rollout_harness,
        agent_rollout_audit,
        eval_leakage_audit,
        agent_rollout_result_judge,
        e2e_acceptance,
        smoke_test_plan,
        routing_metadata_audit,
        codex_publish_adapter,
        release_action_audit,
    )
    build_timeline_report = build_timeline(request, phase_state, review_result, publish_gate, quality_report)
    build_timeline_audit_report = build_timeline_audit(
        request,
        build_timeline_report,
        phase_state,
        review_result,
        publish_gate,
        quality_report,
    )
    run_scorecard = build_run_scorecard(
        request,
        score_report,
        quality_report,
        completion_audit,
        release_action_audit,
        manifest,
        build_timeline_report,
        build_timeline_audit_report,
    )
    run_scorecard_markdown = render_run_scorecard_markdown(
        run_scorecard,
        score_report,
        quality_report,
        completion_audit,
        release_action_audit,
        build_timeline_report,
        build_timeline_audit_report,
    )
    write_data(out / "artifact_validation.yaml", artifact_validation)
    write_data(out / "publish_manifest.yaml", manifest)
    write_data(out / "publish_manifest_audit.yaml", publish_manifest_audit)
    write_data(out / "release_action_audit.yaml", release_action_audit)
    write_data(out / "score_report.yaml", score_report)
    write_data(out / "completion_audit.yaml", completion_audit)
    write_data(out / "build_timeline.yaml", build_timeline_report)
    write_data(out / "build_timeline_audit.yaml", build_timeline_audit_report)
    write_data(out / "run_scorecard.yaml", run_scorecard)
    write_text(out / "run_scorecard.md", run_scorecard_markdown)
    output_retention = refresh_retained_artifacts(
        out,
        output_retention,
        [
            "publish_manifest.yaml",
            "publish_manifest_audit.yaml",
            "release_action_audit.yaml",
            "score_report.yaml",
            "completion_audit.yaml",
            "build_timeline.yaml",
            "build_timeline_audit.yaml",
            "run_scorecard.yaml",
            "run_scorecard.md",
            "phase_state.yaml",
            "phase_state_audit.yaml",
        ],
    )
    output_retention = refresh_generation_process_doc(
        request,
        out,
        task_catalog,
        review_result,
        publish_gate,
        output_retention,
    )
    run_manifest = build_run_manifest(request, out, manifest)
    write_data(out / "run_manifest.yaml", run_manifest)
    final_artifacts = load_artifacts_for_final_validation(
        out,
        manifest,
        FINAL_VALIDATION_ARTIFACTS,
    )
    artifact_validation = validate_artifact_bundle(final_artifacts, FINAL_VALIDATION_ARTIFACTS)
    if artifact_validation.get("status") != "pass":
        manifest["status"] = "blocked"
        manifest.setdefault("blocking_findings", []).append(
            {
                "severity": "error",
                "code": "final_artifact_validation_failed",
                "message": "Final retained/root artifact validation failed; publish is blocked until required artifacts are consistent.",
            }
        )
        write_data(out / "publish_manifest.yaml", manifest)
        publish_manifest_audit = build_publish_manifest_audit(
            request,
            manifest,
            publish_gate,
            release_package,
            skill_update_plan,
            install_readiness,
            codex_publish_adapter,
            final_candidate_audit,
        )
        write_data(out / "publish_manifest_audit.yaml", publish_manifest_audit)
        output_retention = refresh_retained_artifacts(
            out,
            output_retention,
            ["publish_manifest.yaml", "publish_manifest_audit.yaml"],
        )
        run_manifest = build_run_manifest(request, out, manifest)
        write_data(out / "run_manifest.yaml", run_manifest)
        final_artifacts = load_artifacts_for_final_validation(
            out,
            manifest,
            FINAL_VALIDATION_ARTIFACTS,
        )
        artifact_validation = validate_artifact_bundle(final_artifacts, FINAL_VALIDATION_ARTIFACTS)
    write_data(out / "artifact_validation.yaml", artifact_validation)
    result_manifest = dict(manifest)
    result_manifest["output_retention"] = output_retention
    return result_manifest
