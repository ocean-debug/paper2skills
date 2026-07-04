"""Requirement-to-artifact coverage matrix for Papert2Skills builds."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    requirement_id: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if requirement_id:
        item["requirement_id"] = requirement_id
    findings.append(item)


def status_from(checks: list[bool]) -> str:
    return "covered" if all(checks) else "missing"


def task_count(task_catalog: dict[str, Any]) -> int:
    return len(task_catalog.get("tasks", []))


def task_has_contracts(task_catalog: dict[str, Any]) -> bool:
    for task in task_catalog.get("tasks", []):
        input_contract = task.get("input_contract") or {}
        output_contract = task.get("output_contract") or {}
        if not input_contract.get("required_from_user"):
            return False
        if not output_contract.get("expected_outputs"):
            return False
        if not output_contract.get("minimum_validation"):
            return False
        if not task.get("refusal_boundaries"):
            return False
    return bool(task_catalog.get("tasks"))


def task_has_router(task_catalog: dict[str, Any], router: dict[str, Any]) -> bool:
    tasks = {task.get("task_type") for task in task_catalog.get("tasks", []) if task.get("task_type")}
    routes = {route.get("task_type") for route in router.get("routes", []) if route.get("task_type")}
    return bool(tasks) and tasks.issubset(routes)


def child_file_coverage(skill_spec: dict[str, Any]) -> bool:
    child = skill_spec.get("child_skill") or {}
    required = set(child.get("required_files", []))
    expected = {"SKILL.md"} | {f"references/{name}" for name in REQUIRED_CHILD_REFERENCES}
    return expected.issubset(required)


def execution_boundary_covered(
    request: dict[str, Any],
    execution_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
    verification_claim_audit: dict[str, Any],
) -> bool:
    if bool(execution_plan.get("execution_grounded_requested")) != bool(request.get("execution_grounded")):
        return False
    if verification_claim_audit.get("status") != "pass":
        return False
    if tutorial_reproduction_plan.get("plan_only") is not True:
        return False
    if execution_replay_orchestrator.get("plan_only") is not True:
        return False
    if execution_replay_orchestrator.get("status") != "pass":
        return False
    if request.get("execution_grounded"):
        return tutorial_reproduction_plan.get("replay_count", 0) > 0 and execution_replay_orchestrator.get("ready_job_count", 0) > 0
    return True


def build_requirement_coverage(
    request: dict[str, Any],
    request_audit: dict[str, Any],
    request_fingerprint: dict[str, Any],
    external_result_contracts: dict[str, Any],
    builder_runtime_audit: dict[str, Any],
    agent_metadata_audit: dict[str, Any],
    public_origin_audit: dict[str, Any],
    module_inventory_audit: dict[str, Any],
    builder_baseline_audit: dict[str, Any],
    skill_package_audit: dict[str, Any],
    request_template_audit: dict[str, Any],
    discovery_report: dict[str, Any],
    discovery_match_audit: dict[str, Any],
    discovery_resolution_audit: dict[str, Any],
    source_grounding: dict[str, Any],
    source_grounding_audit: dict[str, Any],
    source_fetch_boundary_audit: dict[str, Any],
    source_ingestion_audit: dict[str, Any],
    source_parsing_audit: dict[str, Any],
    key_api_coverage_audit: dict[str, Any],
    task_catalog: dict[str, Any],
    task_partition_decision_log: dict[str, Any],
    router: dict[str, Any],
    task_partition_audit: dict[str, Any],
    skill_spec: dict[str, Any],
    backend_contract: dict[str, Any],
    backend_extension_audit: dict[str, Any],
    execution_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
    verification_claim_audit: dict[str, Any],
    resource_boundary_audit: dict[str, Any],
    contract_traceability: dict[str, Any],
    evidence_claim_taxonomy_audit: dict[str, Any],
    biological_claim_boundary_audit: dict[str, Any],
    child_reference_coverage: dict[str, Any],
    child_metadata_audit: dict[str, Any],
    child_package_purity_audit: dict[str, Any],
    routing_metadata_audit: dict[str, Any],
    output_boundary_audit: dict[str, Any],
    skill_update_plan: dict[str, Any],
    skill_update_audit: dict[str, Any],
    forward_test_plan: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    agent_rollout_audit: dict[str, Any],
    eval_leakage_audit: dict[str, Any],
    agent_rollout_result_judge: dict[str, Any],
    e2e_acceptance: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
    review_prompt_materials: dict[str, Any],
    review_prompt_suite_audit: dict[str, Any],
    review_iteration_log: dict[str, Any],
    review_remediation_audit: dict[str, Any],
    review_optimizer_state: dict[str, Any],
    patch_safety_audit: dict[str, Any],
    patch_operation_contracts: dict[str, Any],
    review_discipline_audit: dict[str, Any],
    review_trajectory_audit: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "requirement_id": "build_request_contract",
            "requirement": "Build request fields, source support, execution environment boundaries, and reproducible request identity are audited.",
            "status": status_from([
                request_audit.get("status") == "pass",
                request_fingerprint.get("status") == "pass",
                request_fingerprint.get("stores_raw_request") is False,
                external_result_contracts.get("status") == "pass",
            ]),
            "evidence_artifacts": ["request_audit.yaml", "request_fingerprint.yaml", "external_result_contracts.yaml"],
        },
        {
            "requirement_id": "builder_runtime_surface",
            "requirement": "The builder skill has callable Codex metadata, a complete build request template, required CLI commands, documented script inventory, engineering baseline coverage, and standard skill package shape.",
            "status": status_from([
                builder_runtime_audit.get("status") == "pass",
                agent_metadata_audit.get("status") == "pass",
                public_origin_audit.get("status") == "pass",
                module_inventory_audit.get("status") == "pass",
                builder_baseline_audit.get("status") == "pass",
                skill_package_audit.get("status") == "pass",
                request_template_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["builder_runtime_audit.yaml", "agent_metadata_audit.yaml", "public_origin_audit.yaml", "module_inventory_audit.yaml", "builder_baseline_audit.yaml", "skill_package_audit.yaml", "request_template_audit.yaml"],
        },
        {
            "requirement_id": "codex_target",
            "requirement": "Generated child skills target Codex-style skills.",
            "status": status_from([request.get("target_agent") == "codex", skill_spec.get("target_agent") == "codex"]),
            "evidence_artifacts": ["request", "skill_spec.yaml"],
        },
        {
            "requirement_id": "discovery_no_duplicate",
            "requirement": "Discovery decides reuse, update, or create before publishing, with audited match strength.",
            "status": status_from([
                discovery_report.get("decision") in {"reuse", "update", "create"},
                discovery_match_audit.get("status") == "pass",
                discovery_resolution_audit.get("status") == "pass",
                skill_update_plan.get("status") == "pass",
                skill_update_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["discovery_report.yaml", "discovery_match_audit.yaml", "discovery_resolution_audit.yaml", "skill_update_plan.yaml", "skill_update_audit.yaml"],
        },
        {
            "requirement_id": "source_grounding_priority",
            "requirement": "Source grounding records evidence priority, official sources, and traceable rendering into the child skill.",
            "status": status_from([
                bool(source_grounding.get("evidence_priority")),
                bool(source_grounding.get("sources")),
                source_grounding_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["source_grounding.yaml", "source_grounding_audit.yaml"],
        },
        {
            "requirement_id": "key_api_coverage",
            "requirement": "Explicit key APIs from the build request are grounded exactly against parsed API or interface evidence.",
            "status": status_from([
                key_api_coverage_audit.get("status") == "pass",
                key_api_coverage_audit.get("coverage_ratio", 0) >= key_api_coverage_audit.get("minimum_coverage_ratio", 1.0),
            ]),
            "evidence_artifacts": ["key_api_coverage_audit.yaml", "api_grounding.yaml", "interface_grounding.yaml"],
        },
        {
            "requirement_id": "static_source_parsing_boundary",
            "requirement": "Source fetching, ingestion, and parsing are opt-in, run-bounded, static, provenance-preserving, count-consistent, and non-executing.",
            "status": status_from([
                source_parsing_audit.get("status") == "pass",
                source_fetch_boundary_audit.get("status") == "pass",
                source_ingestion_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["source_fetch_boundary_audit.yaml", "source_ingestion_audit.yaml", "source_parsing_audit.yaml"],
        },
        {
            "requirement_id": "one_package_one_skill",
            "requirement": "One package produces one lightweight child skill.",
            "status": status_from([task_catalog.get("one_package_one_skill") is True, child_file_coverage(skill_spec)]),
            "evidence_artifacts": ["task_catalog.yaml", "skill_spec.yaml"],
        },
        {
            "requirement_id": "task_type_partition",
            "requirement": "Package capabilities are represented as task_type entries, not separate child skills.",
            "status": status_from([
                task_count(task_catalog) > 0,
                task_partition_decision_log.get("status") == "pass",
                task_partition_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["task_catalog.yaml", "task_partition_decision_log.yaml", "task_partition_audit.yaml"],
        },
        {
            "requirement_id": "task_type_router",
            "requirement": "A router chooses task_type inside the same child skill.",
            "status": status_from([task_has_router(task_catalog, router), routing_metadata_audit.get("status") == "pass"]),
            "evidence_artifacts": ["task_type_router.yaml", "routing_metadata_audit.yaml"],
        },
        {
            "requirement_id": "contracts_refusal_validation",
            "requirement": "Each task_type has input, output, refusal, validation, traceability, and high-risk biological claim boundary records.",
            "status": status_from([
                task_has_contracts(task_catalog),
                contract_traceability.get("status") == "pass",
                evidence_claim_taxonomy_audit.get("status") == "pass",
                biological_claim_boundary_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["task_catalog.yaml", "contract_traceability.yaml", "evidence_claim_taxonomy_audit.yaml", "biological_claim_boundary_audit.yaml"],
        },
        {
            "requirement_id": "python_first_r_reserved",
            "requirement": "Python backend is implemented first; R remains an explicit extension boundary.",
            "status": status_from([
                backend_contract.get("status") in {"supported", "extension_reserved"},
                backend_extension_audit.get("status") == "pass",
                "python" in backend_extension_audit.get("implemented_backends", []),
                "r" in backend_extension_audit.get("reserved_backends", []),
            ]),
            "evidence_artifacts": ["backend_contract.yaml", "backend_extension_audit.yaml"],
        },
        {
            "requirement_id": "execution_grounding_opt_in",
            "requirement": "Execution grounding is explicit, tutorial replay and replay orchestration remain plan-only, and verified task claims require validated execution evidence.",
            "status": status_from([execution_boundary_covered(request, execution_plan, tutorial_reproduction_plan, execution_replay_orchestrator, verification_claim_audit)]),
            "evidence_artifacts": ["execution_plan.yaml", "tutorial_reproduction_plan.yaml", "execution_replay_orchestrator.yaml", "verification_claim_audit.yaml"],
        },
        {
            "requirement_id": "resource_boundaries",
            "requirement": "Model, checkpoint, external data, permission, license, token, and large-download boundaries are audited and rendered before execution.",
            "status": status_from([resource_boundary_audit.get("status") == "pass"]),
            "evidence_artifacts": ["resource_inventory.yaml", "resource_boundary_audit.yaml", "environment_install_plan.yaml"],
        },
        {
            "requirement_id": "lightweight_child_structure",
            "requirement": "Child skill uses lightweight SKILL.md plus required references.",
            "status": status_from([
                child_file_coverage(skill_spec),
                child_metadata_audit.get("status") == "pass",
                child_package_purity_audit.get("status") == "pass",
                child_reference_coverage.get("status") == "pass",
                output_boundary_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["skill_spec.yaml", "child_metadata_audit.yaml", "child_package_purity_audit.yaml", "child_reference_coverage.yaml", "output_boundary_audit.yaml"],
        },
        {
            "requirement_id": "self_review_iteration",
            "requirement": "Agent-driven SkillOpt-style self-review records review state, agent proposal plan, optimizer state, patch safety, and gate discipline.",
            "status": status_from([
                review_optimizer_state.get("status") == "pass",
                review_prompt_contracts.get("status") == "pass",
                review_prompt_materials.get("status") == "pass",
                review_prompt_suite_audit.get("status") == "pass",
                review_iteration_log.get("status") == "pass",
                review_remediation_audit.get("status") == "pass",
                patch_safety_audit.get("status") == "pass",
                patch_operation_contracts.get("status") == "pass",
                review_discipline_audit.get("status") == "pass",
                review_trajectory_audit.get("status") == "pass",
            ]),
            "evidence_artifacts": ["review_prompt_contracts.yaml", "review_prompt_materials.yaml", "review_prompt_suite_audit.yaml", "review_iteration_log.yaml", "review_iteration_log.md", "review_remediation_audit.yaml", "review_optimizer_state.yaml", "patch_safety_audit.yaml", "patch_operation_contracts.yaml", "review_discipline_audit.yaml", "review_trajectory_audit.yaml", "review_iterations.jsonl"],
        },
        {
            "requirement_id": "forward_test_plan",
            "requirement": "Generated child skill includes plan-only forward-test scenarios and rollout harness cases for independent validation.",
            "status": status_from([
                forward_test_plan.get("status") == "pass",
                forward_test_plan.get("scenario_count", 0) > 0,
                agent_rollout_harness.get("status") == "pass",
                agent_rollout_harness.get("rollout_count", 0) > 0,
                agent_rollout_audit.get("status") == "pass",
                eval_leakage_audit.get("status") == "pass",
                eval_leakage_audit.get("holdout_forward_scenario_count", 0) > 0,
                eval_leakage_audit.get("leaked_prompt_count", 0) == 0,
                external_result_contracts.get("status") == "pass",
                agent_rollout_result_judge.get("status") in {"pass", "not_run"},
            ]),
            "evidence_artifacts": ["forward_test_plan.yaml", "agent_rollout_harness.yaml", "agent_rollout_audit.yaml", "eval_leakage_audit.yaml", "external_result_contracts.yaml", "agent_rollout_result_judge.yaml"],
        },
        {
            "requirement_id": "e2e_acceptance_contract",
            "requirement": "Real end-to-end acceptance has a plan-only scenario contract and only explicit supplied E2E results can prove full E2E acceptance.",
            "status": status_from([
                e2e_acceptance.get("status") == "pass",
                e2e_acceptance.get("plan_only") is True,
                e2e_acceptance.get("scenario_count", 0) > 0,
                (not request.get("require_e2e_acceptance")) or e2e_acceptance.get("e2e_verdict") == "passed",
            ]),
            "evidence_artifacts": ["e2e_acceptance.yaml", "external_result_contracts.yaml"],
        },
    ]

    findings: list[dict[str, Any]] = []
    for row in rows:
        if row["status"] != "covered":
            add_finding(
                findings,
                "error",
                "requirement_not_covered",
                "A core Papert2Skills requirement lacks artifact coverage.",
                str(row["requirement_id"]),
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "requirement_count": len(rows),
        "covered_count": sum(1 for row in rows if row["status"] == "covered"),
        "requirements": rows,
        "findings": findings,
        "policy": "Requirement coverage maps first-principles product requirements to concrete build artifacts and gates.",
    }
