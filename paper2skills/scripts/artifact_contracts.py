"""Machine-readable contracts for build artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


ARTIFACT_CONTRACTS: dict[str, dict[str, Any]] = {
    "request": {
        "description": "Normalized build request reused by follow-up audits and handoff commands.",
        "required_fields": ["schema_version", "repo_url", "target_agent", "language_backend", "output_dir", "execution_grounded", "execution_environment", "fetch_sources", "max_fetch_bytes", "max_index_files", "max_index_bytes", "review_iterations", "review_min_score_ratio", "require_smoke_test"],
        "dict_fields": ["execution_environment"],
        "list_fields": ["tutorial_links", "doc_links", "paper_links", "paper_dois", "api_names", "source_material_paths", "existing_skills_dirs", "requested_task_types", "execution_traces", "execution_replay_results", "eval_results", "agent_rollout_results", "smoke_test_results", "e2e_acceptance_results"],
    },
    "request_audit": {
        "description": "Normalized build request contract, source-support, and execution-boundary audit.",
        "required_fields": ["schema_version", "status", "target_agent", "language_backend", "source_support_fields", "has_supporting_sources", "execution_grounded_requested", "remote_environment_required", "findings", "policy"],
        "list_fields": ["source_support_fields", "findings", "policy"],
    },
    "request_fingerprint": {
        "description": "Stable redacted build-request fingerprint for reproducible run identity.",
        "required_fields": ["schema_version", "status", "request_hash", "identifier_hash", "control_hash", "request_key_count", "request_keys", "identifier_fields", "control_fields", "sensitive_field_paths", "redacted_sensitive_value_count", "stores_raw_request", "request_audit_status", "findings", "policy"],
        "list_fields": ["request_keys", "identifier_fields", "control_fields", "sensitive_field_paths", "findings", "policy"],
    },
    "external_result_contracts": {
        "description": "Static schema and leakage-boundary audit for supplied external eval, rollout, replay, and E2E result evidence.",
        "required_fields": ["schema_version", "status", "eval_result_count", "agent_rollout_result_count", "smoke_test_result_count", "execution_replay_result_count", "e2e_acceptance_result_count", "supplied_result_count", "forbidden_result_fields", "findings", "policy"],
        "list_fields": ["forbidden_result_fields", "findings", "policy"],
    },
    "phase_state": {
        "description": "Pipeline phase ledger.",
        "required_fields": ["schema_version", "created_at", "updated_at", "phases"],
        "list_fields": ["phases"],
    },
    "phase_state_audit": {
        "description": "Static audit of phase ledger structure and output ownership.",
        "required_fields": ["schema_version", "status", "phase_count", "unique_phase_count", "output_count", "contract_count", "records", "findings", "policy"],
        "list_fields": ["records", "findings", "policy"],
    },
    "protocol_compliance_audit": {
        "description": "Cross-stage audit that plan-only, external-result, output-boundary, verification, and completion-evidence protocols remain separated.",
        "required_fields": ["schema_version", "status", "plan_only_artifact_count", "plan_only_pass_count", "protocol_record_count", "protocol_pass_count", "plan_only_records", "protocol_records", "findings", "policy"],
        "list_fields": ["plan_only_records", "protocol_records", "findings", "policy"],
    },
    "builder_runtime_audit": {
        "description": "Static audit of the builder skill callable surface, template request, CLI commands, and UI metadata.",
        "required_fields": ["schema_version", "builder_version", "status", "skill_dir", "required_files", "file_records", "required_template_fields", "required_execution_environment_fields", "template_field_count", "required_cli_commands", "observed_cli_commands", "required_openai_interface_fields", "openai_interface_fields", "findings", "policy"],
        "list_fields": ["required_files", "file_records", "required_template_fields", "required_execution_environment_fields", "required_cli_commands", "observed_cli_commands", "required_openai_interface_fields", "openai_interface_fields", "findings", "policy"],
    },
    "agent_metadata_audit": {
        "description": "Static audit that SKILL.md trigger metadata and agents/openai.yaml UI metadata stay aligned.",
        "required_fields": ["schema_version", "status", "skill_dir", "skill_path", "openai_path", "allowed_frontmatter_fields", "frontmatter_fields", "required_interface_fields", "interface_fields", "display_name", "short_description_length", "default_prompt_has_skill_token", "required_concepts", "missing_skill_concepts", "missing_openai_concepts", "findings", "policy"],
        "list_fields": ["allowed_frontmatter_fields", "frontmatter_fields", "required_interface_fields", "interface_fields", "required_concepts", "missing_skill_concepts", "missing_openai_concepts", "findings", "policy"],
    },
    "public_origin_audit": {
        "description": "Static audit that public project files avoid private origin markers and machine-specific execution details.",
        "required_fields": ["schema_version", "status", "repo_root", "skill_dir", "checked_files", "checked_file_count", "pattern_records", "findings", "policy"],
        "list_fields": ["checked_files", "pattern_records", "findings", "policy"],
    },
    "module_inventory_audit": {
        "description": "Static audit that builder script modules have docstrings and are discoverable from inventory docs.",
        "required_fields": ["schema_version", "status", "skill_dir", "repo_root", "module_count", "required_docs", "modules", "findings", "policy"],
        "list_fields": ["required_docs", "modules", "findings", "policy"],
    },
    "builder_baseline_audit": {
        "description": "Static audit that expected builder engineering baseline families are covered by concrete modules and public inventory docs.",
        "required_fields": ["schema_version", "builder_version", "status", "skill_dir", "repo_root", "family_count", "covered_family_count", "module_count", "covered_module_count", "families", "findings", "policy"],
        "list_fields": ["families", "findings", "policy"],
    },
    "skill_package_audit": {
        "description": "Static audit of the builder skill package top-level shape and required files.",
        "required_fields": ["schema_version", "status", "skill_dir", "allowed_top_level_files", "allowed_top_level_dirs", "required_files", "checked_files", "findings", "policy"],
        "list_fields": ["allowed_top_level_files", "allowed_top_level_dirs", "required_files", "checked_files", "findings", "policy"],
    },
    "request_template_audit": {
        "description": "Static audit that the build request template matches normalization and request-audit contracts.",
        "required_fields": ["schema_version", "status", "skill_dir", "template_path", "template_field_count", "normalized_default_fields", "request_audit_list_fields", "request_audit_positive_int_fields", "remote_required_fields", "runtime_required_template_fields", "missing_template_fields", "missing_runtime_required_fields", "missing_environment_fields", "findings", "policy"],
        "list_fields": ["normalized_default_fields", "request_audit_list_fields", "request_audit_positive_int_fields", "remote_required_fields", "runtime_required_template_fields", "missing_template_fields", "missing_runtime_required_fields", "missing_environment_fields", "findings", "policy"],
    },
    "builder_version_audit": {
        "description": "Static audit of schema_version and builder_version consistency across core artifacts.",
        "required_fields": ["schema_version", "builder_version", "status", "required_artifacts", "required_builder_version_artifacts", "record_count", "records", "findings", "policy"],
        "list_fields": ["required_artifacts", "required_builder_version_artifacts", "records", "findings", "policy"],
    },
    "discovery_preflight": {
        "description": "Pre-source check for existing child skills.",
        "required_fields": ["schema_version", "decision", "matches", "requested_or_inferred_task_types"],
        "list_fields": ["matches", "requested_or_inferred_task_types"],
    },
    "discovery_report": {
        "description": "Final check for existing child skills after task inference.",
        "required_fields": ["schema_version", "decision", "matches", "requested_or_inferred_task_types"],
        "list_fields": ["matches", "requested_or_inferred_task_types"],
    },
    "discovery_audit": {
        "description": "Audit of reuse, update, or create Discovery decisions.",
        "required_fields": ["schema_version", "status", "preflight_decision", "final_decision", "checked_existing_skill_dirs", "requested_or_inferred_task_types", "match_count", "findings", "recommendations"],
        "list_fields": ["checked_existing_skill_dirs", "requested_or_inferred_task_types", "findings", "recommendations"],
    },
    "discovery_match_audit": {
        "description": "Audit of existing-skill match strength, ambiguity, and lightweight child-skill shape.",
        "required_fields": ["schema_version", "status", "decision", "match_count", "requested_or_inferred_task_types", "required_standard_references", "best_match", "matches", "findings", "policy"],
        "dict_fields": ["best_match"],
        "list_fields": ["requested_or_inferred_task_types", "required_standard_references", "matches", "findings", "policy"],
    },
    "discovery_resolution_audit": {
        "description": "Audit that final Discovery resolution agrees with preflight, match audit, and update planning without duplicate publish risk.",
        "required_fields": ["schema_version", "status", "plan_only", "preflight_decision", "final_decision", "recommended_action", "expected_action", "final_best_match_path", "plan_target_existing_skill_path", "shape_update_required", "preflight_strong_match_count", "final_strong_match_count", "ambiguous_high_confidence", "findings", "policy"],
        "list_fields": ["findings", "policy"],
    },
    "source_grounding": {
        "description": "Input source catalog and evidence priority policy.",
        "required_fields": ["schema_version", "evidence_priority", "sources"],
        "list_fields": ["evidence_priority", "sources"],
    },
    "source_fetch_report": {
        "description": "Bounded fetch or local registration report.",
        "required_fields": ["schema_version", "fetch_enabled", "sources"],
        "list_fields": ["sources"],
    },
    "source_fetch_boundary_audit": {
        "description": "Audit of source fetch opt-in, run-directory, and archive extraction boundaries.",
        "required_fields": ["schema_version", "status", "fetch_enabled", "max_fetch_bytes", "output_dir", "allowed_sources_root", "source_count", "path_record_count", "path_records", "findings", "policy"],
        "list_fields": ["path_records", "findings", "policy"],
    },
    "source_index": {
        "description": "Compact static source-file index.",
        "required_fields": ["schema_version", "file_count", "scanned_file_count", "max_files", "truncated", "files"],
        "list_fields": ["files"],
    },
    "source_parse_report": {
        "description": "Source parsing strategy, counts, samples, and limitations.",
        "required_fields": ["schema_version", "strategy", "counts", "capability_matrix", "parsed_records", "limitations"],
        "dict_fields": ["strategy", "counts"],
        "list_fields": ["capability_matrix", "parsed_records", "limitations"],
    },
    "source_parsing_coverage": {
        "description": "Static source parsing coverage by source kind and parser capability.",
        "required_fields": ["schema_version", "status", "fetch_enabled", "source_status_counts", "file_count", "scanned_file_count", "source_index_truncated", "indexed_file_count", "parseable_file_count", "coverage_by_kind", "findings"],
        "dict_fields": ["source_status_counts"],
        "list_fields": ["coverage_by_kind", "findings"],
    },
    "source_parsing_audit": {
        "description": "Audit of static source parsing strategy, provenance fields, and non-execution boundary.",
        "required_fields": ["schema_version", "status", "required_strategy_fields", "strategy_fields", "capability_kind_count", "indexed_file_count", "api_candidate_count", "interface_count", "tutorial_count", "findings", "policy"],
        "list_fields": ["required_strategy_fields", "strategy_fields", "findings", "policy"],
    },
    "source_ingestion_audit": {
        "description": "Audit of source identity and count lineage across grounding, fetch, index, parse, manifest, and evidence cards.",
        "required_fields": ["schema_version", "status", "source_count", "fetch_source_count", "manifest_source_count", "indexed_file_count", "indexed_record_count", "evidence_card_count", "indexed_by_source", "cards_by_source", "source_parsing_coverage_status", "source_parsing_audit_status", "findings", "policy"],
        "dict_fields": ["indexed_by_source", "cards_by_source"],
        "list_fields": ["findings", "policy"],
    },
    "source_grounding_audit": {
        "description": "Audit that source grounding remains prioritized, non-executing, traceable to task contracts, and rendered into child references.",
        "required_fields": ["schema_version", "status", "source_count", "evidence_card_count", "task_count", "rendered_markdown_count", "evidence_priority", "required_evidence_priority", "findings", "policy"],
        "list_fields": ["evidence_priority", "required_evidence_priority", "findings", "policy"],
    },
    "evidence_cards": {
        "description": "Concise claim-level evidence hints.",
        "required_fields": ["schema_version", "card_count", "cards"],
        "list_fields": ["cards"],
    },
    "evidence_coverage": {
        "description": "Task-level evidence priority and claim-type coverage report.",
        "required_fields": ["schema_version", "status", "task_count", "tasks", "findings"],
        "list_fields": ["tasks", "findings"],
    },
    "evidence_precedence": {
        "description": "Task-level evidence precedence resolution by source priority.",
        "required_fields": ["schema_version", "status", "evidence_priority", "task_count", "tasks", "findings"],
        "list_fields": ["evidence_priority", "tasks", "findings"],
    },
    "evidence_claim_taxonomy_audit": {
        "description": "Task-level claim-type taxonomy and evidence-priority audit.",
        "required_fields": ["schema_version", "status", "task_count", "evidence_card_count", "required_operational_claim_types", "source_required_claim_types", "observed_claim_types", "tasks", "findings", "policy"],
        "list_fields": ["required_operational_claim_types", "source_required_claim_types", "observed_claim_types", "tasks", "findings", "policy"],
    },
    "source_manifest": {
        "description": "Source provenance summary for the build.",
        "required_fields": ["schema_version", "source_count", "sources"],
        "list_fields": ["sources"],
    },
    "api_grounding": {
        "description": "Parsed API candidates linked to evidence and task types.",
        "required_fields": ["schema_version", "api_candidate_count", "api_candidates", "by_task_type"],
        "dict_fields": ["by_task_type"],
        "list_fields": ["api_candidates"],
    },
    "interface_grounding": {
        "description": "Static Python interface signatures and task links.",
        "required_fields": ["schema_version", "interface_count", "interfaces", "by_task_type"],
        "dict_fields": ["by_task_type"],
        "list_fields": ["interfaces"],
    },
    "key_api_coverage_audit": {
        "description": "Audit that explicit build-request key APIs are covered by parsed API or interface grounding.",
        "required_fields": ["schema_version", "status", "minimum_coverage_ratio", "coverage_ratio", "required_key_api_count", "grounded_key_api_count", "grounded_symbol_count", "records", "findings", "policy"],
        "list_fields": ["records", "findings", "policy"],
    },
    "backend_contract": {
        "description": "Implemented backend boundary.",
        "required_fields": ["schema_version", "requested_backend", "status", "implemented_backends", "reserved_backends", "execution_policy", "refusal_boundary", "findings"],
        "dict_fields": ["execution_policy", "refusal_boundary"],
        "list_fields": ["implemented_backends", "reserved_backends", "findings"],
    },
    "backend_extension_audit": {
        "description": "Audit of Python-first backend support and reserved backend extension boundaries.",
        "required_fields": ["schema_version", "status", "requested_backend", "backend_contract_status", "environment_install_plan_status", "install_strategy", "implemented_backends", "reserved_backends", "r_source_count", "task_count", "findings", "policy"],
        "list_fields": ["implemented_backends", "reserved_backends", "findings", "policy"],
    },
    "environment_spec": {
        "description": "Static dependency, import, Python, and GPU hints.",
        "required_fields": ["schema_version", "declared_dependencies", "imported_modules", "findings"],
        "list_fields": ["declared_dependencies", "imported_modules", "findings"],
    },
    "environment_install_plan": {
        "description": "Plan-only environment installation boundary for optional execution grounding.",
        "required_fields": ["schema_version", "status", "plan_only", "execution_grounded_requested", "environment", "missing_environment_fields", "install_strategy", "requires_user_approval", "planned_steps", "refusal_if_missing", "findings"],
        "dict_fields": ["environment"],
        "list_fields": ["missing_environment_fields", "planned_steps", "refusal_if_missing", "findings"],
    },
    "resource_inventory": {
        "description": "Static inventory of model, checkpoint, external data, and registry resource boundaries.",
        "required_fields": ["schema_version", "status", "resource_count", "resource_types", "risk_counts", "resources", "findings", "policy"],
        "dict_fields": ["risk_counts"],
        "list_fields": ["resource_types", "resources", "findings", "policy"],
    },
    "resource_boundary_audit": {
        "description": "Audit that detected external resources are represented as environment and refusal boundaries.",
        "required_fields": ["schema_version", "status", "resource_count", "risk_counts", "required_refusal_boundaries", "environment_refusal_if_missing", "rendered_files_checked", "findings", "policy"],
        "dict_fields": ["risk_counts"],
        "list_fields": ["required_refusal_boundaries", "environment_refusal_if_missing", "rendered_files_checked", "findings", "policy"],
    },
    "tutorial_catalog": {
        "description": "Static tutorial/example step summary.",
        "required_fields": ["schema_version", "tutorial_count", "tutorials", "findings"],
        "list_fields": ["tutorials", "findings"],
    },
    "parameter_catalog": {
        "description": "Static parameter constraints mined from inspected interfaces.",
        "required_fields": ["schema_version", "parameter_count", "parameters"],
        "list_fields": ["parameters"],
    },
    "task_catalog": {
        "description": "Capability partition represented as task_type entries.",
        "required_fields": ["schema_version", "tasks"],
        "list_fields": ["tasks"],
    },
    "task_partition_decision_log": {
        "description": "Decision log for accepted, merged, deferred, and rejected task_type candidates.",
        "required_fields": ["schema_version", "status", "accepted_task_types", "decision_count", "accepted_decision_count", "rejected_tutorial_split_count", "decisions", "findings", "policy"],
        "list_fields": ["accepted_task_types", "decisions", "findings", "policy"],
    },
    "task_type_router": {
        "description": "Rules for choosing task_type inside one child skill.",
        "required_fields": ["schema_version", "routes", "selection_order"],
        "list_fields": ["routes", "selection_order"],
    },
    "task_partition_audit": {
        "description": "Capability partition audit for task_type granularity and tutorial-split anti-patterns.",
        "required_fields": ["schema_version", "status", "task_count", "tutorial_count", "task_types", "checked_anti_patterns", "ambiguous_pair_count", "findings", "policy"],
        "list_fields": ["task_types", "checked_anti_patterns", "findings", "policy"],
    },
    "task_conflict_matrix": {
        "description": "Pairwise task ambiguity and precedence guidance.",
        "required_fields": ["schema_version", "pair_count", "pairs"],
        "list_fields": ["pairs"],
    },
    "routing_fixture": {
        "description": "Static task_type routing fixtures for select, refuse, unsupported, and ambiguity cases.",
        "required_fields": ["schema_version", "case_count", "case_kinds", "cases"],
        "list_fields": ["case_kinds", "cases"],
    },
    "eval_plan": {
        "description": "Static evaluation scenarios per task_type.",
        "required_fields": ["schema_version", "scenario_count", "scenarios"],
        "list_fields": ["scenarios"],
    },
    "execution_trace_validation": {
        "description": "Validation report for supplied execution traces and replay results.",
        "required_fields": ["schema_version", "status", "execution_grounded_requested", "trace_count", "execution_trace_count", "execution_replay_result_count", "valid_success_count", "valid_success_trace_count", "valid_success_replay_result_count", "records", "findings"],
        "list_fields": ["records", "findings"],
    },
    "execution_replay_orchestrator": {
        "description": "Plan-only tutorial replay job queue and supplied replay-result audit.",
        "required_fields": ["schema_version", "status", "execution_grounded_requested", "plan_only", "job_count", "ready_job_count", "blocked_job_count", "result_count", "successful_result_count", "failed_result_count", "jobs", "result_records", "skill_revision_actions", "findings", "policy"],
        "list_fields": ["jobs", "result_records", "skill_revision_actions", "findings", "policy"],
    },
    "verification_claim_audit": {
        "description": "Audit that task_type verification claims match validated traces and rendered child-skill text.",
        "required_fields": ["schema_version", "status", "execution_grounded_requested", "task_count", "trace_count", "valid_success_count", "execution_plan_status", "tutorial_reproduction_plan_status", "tasks", "findings", "policy"],
        "list_fields": ["tasks", "findings", "policy"],
    },
    "execution_plan": {
        "description": "Plan-only execution grounding boundary.",
        "required_fields": ["schema_version", "task_count", "tasks"],
        "list_fields": ["tasks"],
    },
    "tutorial_reproduction_plan": {
        "description": "Plan-only tutorial reproduction queue for optional execution grounding.",
        "required_fields": ["schema_version", "status", "execution_grounded_requested", "plan_only", "tutorial_count", "task_count", "replay_count", "replays", "findings"],
        "list_fields": ["replays", "findings"],
    },
    "contract_traceability": {
        "description": "Evidence traceability ledger for task input, output, validation, and refusal contracts.",
        "required_fields": ["schema_version", "status", "record_count", "records", "findings"],
        "list_fields": ["records", "findings"],
    },
    "lineage_graph": {
        "description": "Compact source-to-task-to-child-file provenance graph.",
        "required_fields": ["schema_version", "status", "node_count", "edge_count", "nodes", "edges", "findings"],
        "list_fields": ["nodes", "edges", "findings"],
    },
    "acceptance_suite": {
        "description": "Acceptance cases for routing, contracts, refusal, ambiguity, and execution boundaries.",
        "required_fields": ["schema_version", "case_count", "cases"],
        "list_fields": ["cases"],
    },
    "eval_splits": {
        "description": "Stable train, selection, and test splits for static eval and acceptance cases.",
        "required_fields": ["schema_version", "status", "case_count", "split_counts", "cases", "findings"],
        "dict_fields": ["split_counts"],
        "list_fields": ["cases", "findings"],
    },
    "eval_result_judge": {
        "description": "Judgement report for explicitly supplied eval results.",
        "required_fields": ["schema_version", "status", "result_count", "pass_count", "fail_count", "unknown_count", "records", "findings"],
        "list_fields": ["records", "findings"],
    },
    "eval_leakage_audit": {
        "description": "Static audit of eval split isolation and agent prompt leakage boundaries.",
        "required_fields": ["schema_version", "status", "eval_splits_status", "forward_test_plan_status", "agent_rollout_harness_status", "eval_result_judge_status", "split_counts", "eval_case_count", "forward_scenario_count", "rollout_case_count", "prompt_record_count", "leaked_prompt_count", "holdout_forward_scenario_count", "records", "findings", "policy"],
        "dict_fields": ["split_counts"],
        "list_fields": ["records", "findings", "policy"],
    },
    "agent_rollout_result_judge": {
        "description": "Judgement report for explicitly supplied agent rollout results.",
        "required_fields": ["schema_version", "status", "agent_rollout_harness_status", "eval_leakage_audit_status", "result_count", "pass_count", "fail_count", "unknown_count", "records", "findings", "policy"],
        "list_fields": ["records", "findings", "policy"],
    },
    "e2e_acceptance": {
        "description": "Plan-only end-to-end acceptance scenarios and supplied result audit.",
        "required_fields": ["schema_version", "status", "plan_only", "require_e2e_acceptance", "e2e_verdict", "scenario_count", "required_scenario_count", "result_count", "result_template_count", "passed_required_scenario_count", "missing_required_scenarios", "scenarios", "result_templates", "result_records", "findings", "policy"],
        "list_fields": ["missing_required_scenarios", "scenarios", "result_templates", "result_records", "findings", "policy"],
    },
    "smoke_test_plan": {
        "description": "Plan-only smoke test scenarios and supplied-result audit for generated child-skill package shape.",
        "required_fields": ["schema_version", "status", "plan_only", "require_smoke_test", "smoke_verdict", "scenario_count", "result_count", "passed_scenario_count", "missing_required_scenarios", "scenarios", "result_records", "findings", "policy"],
        "list_fields": ["missing_required_scenarios", "scenarios", "result_records", "findings", "policy"],
    },
    "draft_candidates": {
        "description": "Generated child-skill candidate summaries.",
        "required_fields": ["schema_version", "candidate_count", "candidates"],
        "list_fields": ["candidates"],
    },
    "candidate_registry": {
        "description": "Candidate-version registry for generated child skill outputs.",
        "required_fields": ["schema_version", "builder_version", "status", "active_version_id", "versions", "findings", "policy"],
        "list_fields": ["versions", "findings", "policy"],
    },
    "candidate_selection_audit": {
        "description": "Audit of active child-skill candidate selection rationale and quality signals.",
        "required_fields": ["schema_version", "status", "selection_mode", "candidate_count", "selected_version_id", "selected_candidate_id", "publish_gate_status", "recommended_action", "quality_signals", "rationale", "findings", "policy"],
        "list_fields": ["quality_signals", "rationale", "findings", "policy"],
    },
    "candidate_promotion_audit": {
        "description": "Final active-candidate promotion audit before release packaging.",
        "required_fields": ["schema_version", "status", "candidate_count", "active_version_id", "active_candidate_status", "candidate_selection_audit_status", "selected_candidate_id", "publish_gate_status", "skill_update_recommended_action", "promoted_to_release", "required_files", "active_files", "findings", "policy"],
        "list_fields": ["required_files", "active_files", "findings", "policy"],
    },
    "candidate_evolution_audit": {
        "description": "Cross-artifact candidate identity and gate evolution audit across selection, promotion, release, and final candidate records.",
        "required_fields": ["schema_version", "status", "recommended_action", "active_version_id", "active_candidate_id", "publish_gate_status", "review_iteration_count", "stage_count", "records", "findings", "policy"],
        "list_fields": ["records", "findings", "policy"],
    },
    "skill_spec": {
        "description": "Generated child skill file specification.",
        "required_fields": ["schema_version", "builder_version", "child_skill", "backend"],
    },
    "review_summary": {
        "description": "Self-review loop final status and findings.",
        "required_fields": ["schema_version", "status", "final_score", "final_findings", "iteration_count"],
        "list_fields": ["final_findings"],
    },
    "review_evolution": {
        "description": "Self-review score, patch, and gate trajectory summary.",
        "required_fields": ["schema_version", "status", "iteration_count", "iterations", "final_score"],
        "dict_fields": ["final_score"],
        "list_fields": ["iterations"],
    },
    "review_evolution_plot": {
        "description": "Run-level SVG metadata for the review-loop evolution plot.",
        "required_fields": ["schema_version", "status", "svg_path", "iteration_count", "review_status", "stop_reason", "final_score", "plot_policy"],
        "dict_fields": ["final_score"],
        "list_fields": ["plot_policy"],
    },
    "review_iteration_log": {
        "description": "Run-level Markdown metadata for the human-readable review iteration log.",
        "required_fields": ["schema_version", "status", "markdown_path", "review_status", "stop_reason", "iteration_count", "changed_iteration_count", "passed_iteration_count", "final_score", "iterations", "findings", "policy"],
        "dict_fields": ["final_score"],
        "list_fields": ["iterations", "findings", "policy"],
    },
    "review_prompt_contracts": {
        "description": "Static prompt/state contracts for the SkillOpt-style review loop.",
        "required_fields": ["schema_version", "status", "review_status", "contract_count", "required_every_iteration", "contracts", "iteration_count", "findings", "policy"],
        "list_fields": ["required_every_iteration", "contracts", "findings", "policy"],
    },
    "review_prompt_materials": {
        "description": "Static prompt materials for each review-loop role.",
        "required_fields": ["schema_version", "status", "review_prompt_contracts_status", "material_count", "contract_role_count", "materials", "findings", "policy"],
        "list_fields": ["materials", "findings", "policy"],
    },
    "review_prompt_suite_audit": {
        "description": "Static audit that each review iteration covers required review-loop duties.",
        "required_fields": ["schema_version", "status", "review_status", "review_prompt_contracts_status", "review_prompt_materials_status", "review_optimizer_state_status", "duty_count", "iteration_count", "record_count", "covered_count", "duties", "records", "findings", "policy"],
        "list_fields": ["duties", "records", "findings", "policy"],
    },
    "review_cursor": {
        "description": "Review-loop cursor state for resumable iteration.",
        "required_fields": ["schema_version", "status", "review_status", "stop_reason", "current", "iteration_count", "iterations", "findings"],
        "dict_fields": ["current"],
        "list_fields": ["iterations", "findings"],
    },
    "patch_application": {
        "description": "Audit of planned and applied deterministic review patches.",
        "required_fields": ["schema_version", "status", "iteration_count", "changed_iteration_count", "changed_artifacts", "records", "findings"],
        "list_fields": ["changed_artifacts", "records", "findings"],
    },
    "review_remediation_audit": {
        "description": "Audit that review findings are remediated, cleared, accepted by gate, or carried as final blockers.",
        "required_fields": ["schema_version", "status", "review_status", "stop_reason", "iteration_count", "record_count", "remediation_status_counts", "final_error_count", "records", "findings", "policy"],
        "dict_fields": ["remediation_status_counts"],
        "list_fields": ["records", "findings", "policy"],
    },
    "review_optimizer_state": {
        "description": "Optimizer state, hashes, cache key, and rejected-edit buffer for the review loop.",
        "required_fields": ["schema_version", "status", "review_status", "stop_reason", "configured_iteration_budget", "min_score_ratio", "strict_improvement_gate", "cache_key", "iteration_count", "iterations", "rejected_edit_count", "rejected_edits", "final_score", "findings", "policy"],
        "dict_fields": ["final_score"],
        "list_fields": ["iterations", "rejected_edits", "findings", "policy"],
    },
    "patch_safety_audit": {
        "description": "Safety audit for deterministic review patch actions.",
        "required_fields": ["schema_version", "status", "review_status", "optimizer_state_status", "allowed_patch_artifacts", "patch_action_count", "records", "findings", "policy"],
        "list_fields": ["allowed_patch_artifacts", "records", "findings", "policy"],
    },
    "patch_operation_contracts": {
        "description": "Contract audit for deterministic review patch operation names, fields, and finding traceability.",
        "required_fields": ["schema_version", "status", "review_status", "patch_application_status", "patch_safety_status", "contract_count", "operation_contracts", "allowed_artifacts", "iteration_count", "action_count", "records", "findings", "policy"],
        "dict_fields": ["operation_contracts"],
        "list_fields": ["allowed_artifacts", "records", "findings", "policy"],
    },
    "review_discipline_audit": {
        "description": "Audit of review-loop state-machine discipline and stop-condition consistency.",
        "required_fields": ["schema_version", "status", "review_status", "stop_reason", "configured_iteration_budget", "iteration_count", "findings"],
        "list_fields": ["findings"],
    },
    "rubric_grounding_audit": {
        "description": "Audit of rubric item results and grounding signals for awarded points.",
        "required_fields": ["schema_version", "status", "review_status", "rubric_items", "record_count", "records", "findings"],
        "list_fields": ["rubric_items", "records", "findings"],
    },
    "review_trajectory_audit": {
        "description": "Cross-artifact integrity audit for review-loop trajectory records.",
        "required_fields": ["schema_version", "status", "iteration_count", "evolution_iteration_ids", "patch_iteration_ids", "optimizer_iteration_ids", "review_status", "review_stop_reason", "final_score", "findings", "policy"],
        "dict_fields": ["final_score"],
        "list_fields": ["evolution_iteration_ids", "patch_iteration_ids", "optimizer_iteration_ids", "findings", "policy"],
    },
    "skill_lint_report": {
        "description": "Child-skill lint report.",
        "required_fields": ["schema_version", "builder_version", "status", "findings"],
        "list_fields": ["findings"],
    },
    "child_metadata_audit": {
        "description": "Audit of generated child-skill frontmatter, Codex trigger description, and one-skill metadata shape.",
        "required_fields": ["schema_version", "status", "frontmatter", "task_types", "top_level_dirs", "nested_skill_files", "findings", "policy"],
        "dict_fields": ["frontmatter"],
        "list_fields": ["task_types", "top_level_dirs", "nested_skill_files", "findings", "policy"],
    },
    "child_package_purity_audit": {
        "description": "Strict audit that public child skills contain only SKILL.md and standard references.",
        "required_fields": ["schema_version", "status", "child_skill_path", "required_public_files", "actual_public_files", "actual_public_directories", "missing_public_files", "unexpected_public_files", "unexpected_public_directories", "forbidden_trace_paths", "findings", "policy"],
        "list_fields": ["required_public_files", "actual_public_files", "actual_public_directories", "missing_public_files", "unexpected_public_files", "unexpected_public_directories", "forbidden_trace_paths", "findings", "policy"],
    },
    "draft_readiness": {
        "description": "Generated child-skill draft marker and template-value readiness check.",
        "required_fields": ["schema_version", "status", "checked_file_count", "findings"],
        "list_fields": ["findings"],
    },
    "output_boundary_audit": {
        "description": "Generated output directory and public child-skill boundary audit.",
        "required_fields": ["schema_version", "status", "output_dir", "child_skill_path", "expected_child_root", "output_dir_inside_install_root", "install_root_markers", "expected_public_files", "actual_public_files", "findings", "policy"],
        "list_fields": ["install_root_markers", "expected_public_files", "actual_public_files", "findings", "policy"],
    },
    "skill_update_plan": {
        "description": "Plan-only reuse, update, or create guidance from Discovery decisions.",
        "required_fields": ["schema_version", "status", "plan_only", "discovery_decision", "recommended_action", "candidate_child_skill_path", "covered_task_types", "missing_task_types", "shape_update_required", "shape_findings", "inferred_task_types", "merge_actions", "manual_review_required", "findings", "policy"],
        "list_fields": ["covered_task_types", "missing_task_types", "shape_findings", "inferred_task_types", "merge_actions", "findings", "policy"],
    },
    "skill_update_audit": {
        "description": "Plan-only audit of non-destructive create, update, and reuse skill-update guidance.",
        "required_fields": ["schema_version", "status", "plan_only", "discovery_decision", "recommended_action", "target_existing_skill_path", "candidate_child_skill_path", "required_public_files", "merge_action_count", "missing_task_types", "shape_update_required", "covered_task_types", "inferred_task_types", "findings", "policy"],
        "list_fields": ["required_public_files", "missing_task_types", "covered_task_types", "inferred_task_types", "findings", "policy"],
    },
    "forward_test_plan": {
        "description": "Plan-only independent forward-test prompts and judging controls for the generated child skill.",
        "required_fields": ["schema_version", "status", "plan_only", "child_skill_path", "scenario_count", "scenario_kinds", "scenarios", "findings", "policy"],
        "list_fields": ["scenario_kinds", "scenarios", "findings", "policy"],
    },
    "agent_rollout_harness": {
        "description": "Plan-only agent rollout queue assembled from forward-test, routing, and eval artifacts.",
        "required_fields": ["schema_version", "status", "plan_only", "rollout_count", "required_kinds", "kind_counts", "split_counts", "task_count", "covered_task_types", "missing_task_types", "cases", "findings", "policy"],
        "dict_fields": ["kind_counts", "split_counts"],
        "list_fields": ["required_kinds", "covered_task_types", "missing_task_types", "cases", "findings", "policy"],
    },
    "agent_rollout_audit": {
        "description": "Cross-artifact audit for plan-only agent rollout scenario mapping and leakage controls.",
        "required_fields": ["schema_version", "status", "plan_only", "forward_test_plan_status", "agent_rollout_harness_status", "scenario_count", "rollout_count", "mapped_scenario_count", "scenario_kinds", "rollout_kinds", "findings", "policy"],
        "list_fields": ["scenario_kinds", "rollout_kinds", "findings", "policy"],
    },
    "claim_consistency_audit": {
        "description": "Rendered child-skill claim consistency audit.",
        "required_fields": ["schema_version", "status", "checked_file_count", "task_count", "allowed_task_types", "allowed_statuses", "findings"],
        "list_fields": ["allowed_task_types", "allowed_statuses", "findings"],
    },
    "biological_claim_boundary_audit": {
        "description": "Rendered high-risk biological claim boundary audit.",
        "required_fields": ["schema_version", "status", "checked_file_count", "risky_claim_count", "cross_modal_evidence_supported", "risky_claims", "required_refusal_keys", "missing_refusal_keys", "findings", "policy"],
        "list_fields": ["risky_claims", "required_refusal_keys", "missing_refusal_keys", "findings", "policy"],
    },
    "child_reference_coverage": {
        "description": "Audit that generated child references consume key build artifacts.",
        "required_fields": ["schema_version", "status", "checked_file_count", "task_count", "rendered_reference_files", "findings"],
        "list_fields": ["rendered_reference_files", "findings"],
    },
    "routing_metadata_audit": {
        "description": "Audit that task_type routing metadata is complete and rendered into child routing guidance.",
        "required_fields": ["schema_version", "status", "routing_scope", "task_count", "route_count", "conflict_pair_count", "fixture_case_kinds", "rendered_files_checked", "findings", "policy"],
        "list_fields": ["fixture_case_kinds", "rendered_files_checked", "findings", "policy"],
    },
    "workflow_invariant_audit": {
        "description": "First-principles workflow invariant audit.",
        "required_fields": ["schema_version", "status", "task_count", "checked_invariants", "findings"],
        "list_fields": ["checked_invariants", "findings"],
    },
    "requirement_coverage": {
        "description": "Requirement-to-artifact coverage matrix for core Papert2Skills requirements.",
        "required_fields": ["schema_version", "status", "requirement_count", "covered_count", "requirements", "findings", "policy"],
        "list_fields": ["requirements", "findings"],
    },
    "completion_evidence_audit": {
        "description": "Non-executing audit of whether static, rollout, E2E, and execution evidence support completion claims.",
        "required_fields": ["schema_version", "status", "claim_verdict", "can_claim_static_build_complete", "can_claim_full_goal_complete", "requirement_coverage_status", "agent_rollout_result_judge_status", "agent_rollout_result_count", "e2e_acceptance_status", "e2e_verdict", "e2e_result_count", "required_e2e_scenario_count", "passed_required_e2e_scenario_count", "execution_grounded_requested", "execution_trace_validation_status", "successful_execution_evidence_count", "successful_execution_trace_count", "execution_replay_orchestrator_status", "successful_execution_replay_result_count", "missing_evidence", "findings", "policy"],
        "list_fields": ["missing_evidence", "findings", "policy"],
    },
    "acceptance_handoff": {
        "description": "Plan-only handoff package of external result templates for rollout, replay, and E2E acceptance.",
        "required_fields": ["schema_version", "status", "plan_only", "publish_manifest_supplied", "completion_claim_verdict", "can_claim_full_goal_complete", "handoff_item_count", "e2e_template_count", "rollout_template_count", "replay_template_count", "target_request_fields", "handoff_items", "findings", "policy"],
        "list_fields": ["target_request_fields", "handoff_items", "findings", "policy"],
    },
    "architecture_completeness_audit": {
        "description": "Run-level audit that core workflow phase families and gate artifacts are present and passing.",
        "required_fields": ["schema_version", "status", "requirement_count", "covered_count", "requirements", "findings", "policy"],
        "list_fields": ["requirements", "findings", "policy"],
    },
    "grounding_gate": {
        "description": "Pre-publish API/interface grounding gate for task_type entries.",
        "required_fields": ["schema_version", "status", "task_grounding", "findings"],
        "list_fields": ["task_grounding", "findings"],
    },
    "api_surface_audit": {
        "description": "Rendered API-surface audit for grounded code-fence calls, inline API mentions, and requested API names.",
        "required_fields": ["schema_version", "status", "allowed_symbol_count", "code_fence_call_count", "inline_api_mention_count", "requested_api_count", "grounded_requested_api_names", "missing_requested_api_names", "task_without_api_surface", "findings"],
        "list_fields": ["grounded_requested_api_names", "missing_requested_api_names", "task_without_api_surface", "findings"],
    },
    "artifact_contracts": {
        "description": "Machine-readable artifact contract catalog.",
        "required_fields": ["schema_version", "contracts", "required_top_level_artifacts", "pre_publish_artifacts"],
        "dict_fields": ["contracts"],
        "list_fields": ["required_top_level_artifacts", "pre_publish_artifacts"],
    },
    "artifact_closure_audit": {
        "description": "Static closure audit for required artifacts, contracts, phase outputs, and write-plan coverage.",
        "required_fields": ["schema_version", "status", "required_artifact_count", "pre_publish_artifact_count", "contract_count", "planned_write_count", "available_artifact_count", "phase_output_count", "records", "findings", "policy"],
        "list_fields": ["records", "findings", "policy"],
    },
    "artifact_validation": {
        "description": "Artifact contract and cross-artifact validation report.",
        "required_fields": ["schema_version", "status", "required_artifacts", "findings"],
        "list_fields": ["required_artifacts", "findings"],
    },
    "code_fence_audit": {
        "description": "Generated code-fence grounding audit.",
        "required_fields": ["schema_version", "status", "findings"],
        "list_fields": ["findings"],
    },
    "public_safety_audit": {
        "description": "Generated public child-skill safety audit.",
        "required_fields": ["schema_version", "status", "checked_file_count", "findings", "policy"],
        "list_fields": ["findings"],
    },
    "publish_gate": {
        "description": "Final publishability decision.",
        "required_fields": ["schema_version", "status", "builder_runtime_audit_status", "agent_metadata_audit_status", "public_origin_audit_status", "builder_baseline_audit_status", "discovery_resolution_audit_status", "execution_replay_orchestrator_status", "e2e_acceptance_status", "e2e_verdict", "require_e2e_acceptance", "smoke_test_plan_status", "smoke_verdict", "require_smoke_test", "evidence_claim_taxonomy_audit_status", "findings"],
        "list_fields": ["findings"],
    },
    "quality_report": {
        "description": "Aggregated quality scorecards and task quality report.",
        "required_fields": ["schema_version", "status", "protocol_compliance_audit_status", "scorecards", "task_quality"],
        "list_fields": ["scorecards", "task_quality"],
    },
    "score_report": {
        "description": "Run-level score report summarizing review, rubric, quality, publish, and candidate gates.",
        "required_fields": ["schema_version", "status", "final_score", "review_status", "review_iteration_count", "review_trajectory", "rubric_grounding_status", "quality_status", "quality_blocking_scorecards", "task_blockers", "publish_gate_status", "publish_blockers", "candidate_selection_status", "candidate_promotion_status", "final_candidate_status", "candidate_evolution_status", "codex_publish_adapter_status", "install_readiness_status", "publish_manifest_audit_status", "promoted_to_release", "finalized_for_release", "findings", "policy"],
        "dict_fields": ["final_score"],
        "list_fields": ["review_trajectory", "quality_blocking_scorecards", "task_blockers", "publish_blockers", "findings", "policy"],
    },
    "release_package": {
        "description": "Manifest-only release package description.",
        "required_fields": ["schema_version", "builder_version", "status", "recommended_action", "candidate_promotion_audit_status", "files", "install_plan"],
        "list_fields": ["files", "install_plan"],
    },
    "release_action_audit": {
        "description": "Final create, update, or reuse release-action semantic audit.",
        "required_fields": ["schema_version", "status", "recommended_action", "expected_publish_statuses", "expected_install_statuses", "publish_gate_status", "skill_update_audit_status", "release_package_status", "install_readiness_status", "codex_publish_adapter_status", "publish_manifest_audit_status", "promoted_to_release", "finalized_for_release", "publish_steps", "findings", "policy"],
        "list_fields": ["expected_publish_statuses", "expected_install_statuses", "publish_steps", "findings", "policy"],
    },
    "final_candidate_audit": {
        "description": "Final consistency audit linking release package metadata to the selected and promoted candidate.",
        "required_fields": ["schema_version", "status", "finalized_for_release", "active_version_id", "release_candidate_version", "selected_candidate_id", "candidate_selection_audit_status", "candidate_promotion_audit_status", "publish_gate_status", "release_package_status", "recommended_action", "release_recommended_action", "required_files", "active_files", "release_files", "missing_release_files", "findings", "policy"],
        "list_fields": ["required_files", "active_files", "release_files", "missing_release_files", "findings", "policy"],
    },
    "codex_publish_adapter": {
        "description": "Plan-only Codex publish adapter for create, update, or reuse release actions.",
        "required_fields": ["schema_version", "status", "plan_only", "target_agent", "adapter_name", "recommended_action", "child_skill_path", "final_candidate_audit_status", "required_files", "publish_steps", "findings", "policy"],
        "list_fields": ["required_files", "publish_steps", "findings", "policy"],
    },
    "install_readiness": {
        "description": "Final copy/install readiness check for the generated public child skill.",
        "required_fields": ["schema_version", "status", "expected_files", "actual_files", "release_manifest_files", "findings"],
        "list_fields": ["expected_files", "actual_files", "release_manifest_files", "findings"],
    },
    "publish_manifest": {
        "description": "Top-level publish manifest.",
        "required_fields": ["schema_version", "builder_version", "status", "child_skill_path", "publish_gate_status", "recommended_action", "discovery_decision", "release_recommended_action", "skill_update_recommended_action", "install_readiness_status", "codex_publish_adapter_status"],
    },
    "publish_manifest_audit": {
        "description": "Final consistency audit for publish manifest, release action, and install readiness status.",
        "required_fields": ["schema_version", "status", "publish_status", "publish_gate_status", "install_readiness_status", "codex_publish_adapter_status", "final_candidate_audit_status", "skill_update_recommended_action", "release_recommended_action", "manifest_recommended_action", "manifest_release_recommended_action", "manifest_skill_update_recommended_action", "findings", "policy"],
        "list_fields": ["findings", "policy"],
    },
    "completion_audit": {
        "description": "Final run-level semantic completion verdict.",
        "required_fields": ["schema_version", "status", "recommended_action", "discovery_decision", "builder_runtime_audit_status", "agent_metadata_audit_status", "public_origin_audit_status", "module_inventory_audit_status", "builder_baseline_audit_status", "skill_package_audit_status", "request_template_audit_status", "builder_version_audit_status", "request_fingerprint_status", "external_result_contracts_status", "phase_state_audit_status", "protocol_compliance_audit_status", "completion_evidence_audit_status", "acceptance_handoff_status", "can_claim_full_goal_complete", "completion_claim_verdict", "publish_gate_status", "quality_status", "agent_rollout_audit_status", "eval_leakage_audit_status", "agent_rollout_result_judge_status", "e2e_acceptance_status", "e2e_verdict", "smoke_test_plan_status", "smoke_verdict", "install_readiness_status", "release_action_audit_status", "candidate_evolution_audit_status", "artifact_closure_audit_status", "source_fetch_boundary_audit_status", "skill_update_audit_status", "discovery_match_audit_status", "discovery_resolution_audit_status", "source_ingestion_audit_status", "key_api_coverage_audit_status", "verification_claim_audit_status", "execution_replay_orchestrator_status", "backend_extension_audit_status", "resource_boundary_audit_status", "evidence_claim_taxonomy_audit_status", "child_metadata_audit_status", "child_package_purity_audit_status", "biological_claim_boundary_audit_status", "review_prompt_materials_status", "review_prompt_suite_audit_status", "review_remediation_audit_status", "patch_operation_contracts_status", "publish_manifest_audit_status", "run_manifest_path", "run_manifest_planned", "checks", "findings", "policy"],
        "list_fields": ["checks", "findings", "policy"],
    },
    "run_scorecard": {
        "description": "Human-readable run scorecard metadata for the Markdown scorecard.",
        "required_fields": ["schema_version", "status", "markdown_path", "verdict_status", "recommended_action", "discovery_decision", "publish_gate_status", "quality_status", "protocol_compliance_audit_status", "score_report_status", "release_action_audit_status", "install_readiness_status", "build_timeline_audit_status", "final_score", "blocking_summary", "timeline_event_count", "report_sections", "findings", "policy"],
        "dict_fields": ["final_score", "blocking_summary"],
        "list_fields": ["report_sections", "findings", "policy"],
    },
    "build_timeline": {
        "description": "Compact timeline of phase, review, and gate events.",
        "required_fields": ["schema_version", "event_count", "events"],
        "list_fields": ["events"],
    },
    "build_timeline_audit": {
        "description": "Static integrity audit for phase, review, and gate events in the build timeline.",
        "required_fields": ["schema_version", "status", "event_count", "declared_event_count", "phase_event_count", "expected_phase_event_count", "phase_scope", "review_event_count", "expected_review_event_count", "gate_event_ids", "event_kinds", "duplicate_event_ids", "findings", "policy"],
        "list_fields": ["gate_event_ids", "event_kinds", "duplicate_event_ids", "findings", "policy"],
    },
    "run_manifest": {
        "description": "Generated-file manifest with hashes.",
        "required_fields": ["schema_version", "builder_version", "created_at", "package_name", "method_name", "output_dir", "publish_status", "publish_manifest_path", "artifact_count", "child_skill_file_count", "file_count", "files", "policy"],
        "list_fields": ["files", "policy"],
    },
}


def build_artifact_contracts_report(
    required_top_level_artifacts: list[str],
    pre_publish_artifacts: list[str],
) -> dict[str, Any]:
    """Return the contract catalog as a build artifact."""
    contracts = {
        name: deepcopy(ARTIFACT_CONTRACTS[name])
        for name in sorted(ARTIFACT_CONTRACTS)
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "artifact_count": len(contracts),
        "required_top_level_artifacts": required_top_level_artifacts,
        "pre_publish_artifacts": pre_publish_artifacts,
        "contracts": contracts,
        "policy": "Contracts define the minimum stable artifact shape; detailed semantic checks remain in artifact validation and publish gates.",
    }


def validate_artifact_contracts(
    artifacts: dict[str, Any],
    required_artifacts: list[str],
) -> list[dict[str, Any]]:
    """Validate available artifacts against their declared minimum contracts."""
    findings: list[dict[str, Any]] = []
    for name in required_artifacts:
        artifact = artifacts.get(name)
        if artifact is None:
            continue
        contract = ARTIFACT_CONTRACTS.get(name)
        if contract is None:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_artifact_contract",
                    "artifact": name,
                    "message": "Required artifact has no declared contract.",
                }
            )
            continue
        if not isinstance(artifact, dict):
            findings.append(
                {
                    "severity": "error",
                    "code": "artifact_not_mapping",
                    "artifact": name,
                    "message": "Artifact must be a mapping.",
                }
            )
            continue
        for field in contract.get("required_fields", []):
            if field not in artifact:
                findings.append(
                    {
                        "severity": "error",
                        "code": "missing_required_field",
                        "artifact": name,
                        "field": field,
                        "message": "Artifact is missing a contract-required field.",
                    }
                )
        for field in contract.get("list_fields", []):
            if field in artifact and not isinstance(artifact[field], list):
                findings.append(
                    {
                        "severity": "error",
                        "code": "field_type_mismatch",
                        "artifact": name,
                        "field": field,
                        "message": "Contract field must be a list.",
                    }
                )
        for field in contract.get("dict_fields", []):
            if field in artifact and not isinstance(artifact[field], dict):
                findings.append(
                    {
                        "severity": "error",
                        "code": "field_type_mismatch",
                        "artifact": name,
                        "field": field,
                        "message": "Contract field must be a mapping.",
                    }
                )
    return findings
