"""Audit end-to-end architecture completeness for a build run."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from action_policy import expected_install_statuses, expected_publish_statuses
from common import now_utc
from constants import SCHEMA_VERSION


ARCHITECTURE_REQUIREMENTS: list[dict[str, Any]] = [
    {
        "requirement_id": "request_and_discovery",
        "description": "Builder runtime, agent metadata, public origin safety, module inventory, engineering baseline coverage, skill package shape, request template, request boundaries, request identity, external result contracts, cross-stage protocol compliance, existing child-skill discovery, resolution, and update safety are audited before release.",
        "phases": ["request", "request_fingerprint", "external_result_contracts", "builder_runtime_audit", "agent_metadata_audit", "public_origin_audit", "module_inventory_audit", "builder_baseline_audit", "skill_package_audit", "request_template_audit", "phase_state_audit", "protocol_compliance_audit", "discovery_preflight", "discovery_audit", "discovery_match_audit", "discovery_resolution_audit", "skill_update_audit"],
        "artifacts": {
            "builder_runtime_audit": {"pass"},
            "agent_metadata_audit": {"pass"},
            "public_origin_audit": {"pass"},
            "module_inventory_audit": {"pass"},
            "builder_baseline_audit": {"pass"},
            "skill_package_audit": {"pass"},
            "request_template_audit": {"pass"},
            "request_audit": {"pass"},
            "request_fingerprint": {"pass"},
            "external_result_contracts": {"pass"},
            "phase_state_audit": {"pass"},
            "protocol_compliance_audit": {"pass"},
            "discovery_audit": {"pass"},
            "discovery_match_audit": {"pass"},
            "discovery_resolution_audit": {"pass"},
            "skill_update_audit": {"pass"},
        },
    },
    {
        "requirement_id": "source_grounding",
        "description": "Source fetching, parsing, and source-grounding evidence are opt-in, run-bounded, traceable, and non-executing by default.",
        "phases": ["source_grounding", "source_fetch_boundary_audit", "source_ingestion_audit", "source_parsing_audit", "source_grounding_audit", "key_api_coverage_audit"],
        "artifacts": {"source_fetch_boundary_audit": {"pass"}, "source_ingestion_audit": {"pass"}, "source_parsing_audit": {"pass"}, "source_grounding_audit": {"pass"}, "key_api_coverage_audit": {"pass"}},
    },
    {
        "requirement_id": "task_type_partitioning",
        "description": "Package capabilities are partitioned into task_type entries inside one child skill.",
        "phases": ["task_partition", "task_partition_decision_log", "task_partition_audit", "routing_metadata_audit"],
        "artifacts": {
            "task_partition_decision_log": {"pass"},
            "task_partition_audit": {"pass"},
            "routing_metadata_audit": {"pass"},
        },
    },
    {
        "requirement_id": "self_review_loop",
        "description": "The self-review loop has prompt contracts, prompt materials, prompt duty coverage, remediation accounting, optimizer state, patch safety, patch operation contracts, rubric grounding, iteration log, and trajectory checks.",
        "phases": ["self_review", "review_iteration_log", "review_prompt_contracts", "review_prompt_materials", "review_remediation_audit", "review_optimizer_state", "review_prompt_suite_audit", "patch_safety_audit", "patch_operation_contracts", "rubric_grounding_audit", "review_trajectory_audit"],
        "artifacts": {
            "review_iteration_log": {"pass"},
            "review_prompt_contracts": {"pass"},
            "review_prompt_materials": {"pass"},
            "review_prompt_suite_audit": {"pass"},
            "review_remediation_audit": {"pass"},
            "review_optimizer_state": {"pass"},
            "patch_safety_audit": {"pass"},
            "patch_operation_contracts": {"pass"},
            "rubric_grounding_audit": {"pass"},
            "review_trajectory_audit": {"pass"},
        },
    },
    {
        "requirement_id": "contracts_and_validation",
        "description": "Input/output/refusal contracts, evidence claim taxonomy, biological claim boundaries, resource boundaries, tutorial replay planning, replay orchestration, verification claim checks, acceptance cases, rollout audit, eval leakage audit, rollout result judging, E2E acceptance, smoke test planning, completion evidence, acceptance handoff, artifact validation, and artifact closure exist.",
        "phases": ["resource_inventory", "resource_boundary_audit", "evidence_claim_taxonomy_audit", "tutorial_reproduction_plan", "execution_replay_orchestrator", "verification_claim_audit", "biological_claim_boundary_audit", "contract_traceability", "acceptance_suite", "agent_rollout_audit", "eval_leakage_audit", "agent_rollout_result_judge", "e2e_acceptance", "smoke_test_plan", "completion_evidence_audit", "acceptance_handoff", "artifact_validation", "artifact_closure_audit"],
        "artifacts": {
            "resource_inventory": {"pass"},
            "resource_boundary_audit": {"pass"},
            "evidence_claim_taxonomy_audit": {"pass"},
            "tutorial_reproduction_plan": {"pass"},
            "execution_replay_orchestrator": {"pass"},
            "verification_claim_audit": {"pass"},
            "biological_claim_boundary_audit": {"pass"},
            "contract_traceability": {"pass"},
            "agent_rollout_audit": {"pass"},
            "eval_leakage_audit": {"pass"},
            "agent_rollout_result_judge": {"pass", "not_run"},
            "e2e_acceptance": {"pass"},
            "smoke_test_plan": {"pass"},
            "completion_evidence_audit": {"pass"},
            "acceptance_handoff": {"pass"},
            "artifact_validation": {"pass"},
            "artifact_closure_audit": {"pass"},
        },
    },
    {
        "requirement_id": "product_invariants",
        "description": "One-package-one-child-skill, lightweight child package purity, Codex target, backend, task_type, and workflow invariants are audited.",
        "phases": ["backend_extension_audit", "child_metadata_audit", "child_package_purity_audit", "workflow_invariant_audit", "requirement_coverage"],
        "artifacts": {
            "backend_extension_audit": {"pass"},
            "child_metadata_audit": {"pass"},
            "child_package_purity_audit": {"pass"},
            "workflow_invariant_audit": {"pass"},
            "requirement_coverage": {"pass"},
        },
    },
    {
        "requirement_id": "candidate_release_chain",
        "description": "Candidate selection, promotion, evolution, finalization, release package, and Codex publish adapter agree.",
        "phases": ["candidate_selection_audit", "candidate_promotion_audit", "release_package", "final_candidate_audit", "candidate_evolution_audit", "codex_publish_adapter"],
        "artifacts": {
            "candidate_selection_audit": {"pass"},
            "candidate_promotion_audit": {"pass"},
            "final_candidate_audit": {"pass"},
            "candidate_evolution_audit": {"pass"},
            "codex_publish_adapter": {"pass"},
        },
    },
    {
        "requirement_id": "publish_completion_chain",
        "description": "Publish, install-readiness, version, publish manifest, release action, and manifest audit gates agree before completion.",
        "phases": ["publish_gate", "install_readiness", "builder_version_audit", "publish_manifest", "publish_manifest_audit", "release_action_audit"],
        "artifacts": {
            "publish_gate": {"publishable"},
            "install_readiness": {"pass"},
            "builder_version_audit": {"pass"},
            "publish_manifest_audit": {"pass"},
            "release_action_audit": {"pass"},
        },
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    requirement_id: str | None = None,
    artifact: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if requirement_id:
        item["requirement_id"] = requirement_id
    if artifact:
        item["artifact"] = artifact
    findings.append(item)


def phase_names(phase_state: dict[str, Any]) -> set[str]:
    return {str(phase.get("name")) for phase in phase_state.get("phases", []) if phase.get("name")}


def artifact_status(artifacts: dict[str, dict[str, Any]], name: str) -> Any:
    return (artifacts.get(name) or {}).get("status")


def requirement_row(
    requirement: dict[str, Any],
    phases: set[str],
    artifacts: dict[str, dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    requirement_id = str(requirement["requirement_id"])
    required_phases = list(requirement.get("phases", []))
    required_artifacts = dict(requirement.get("artifacts", {}))
    missing_phases = sorted(phase for phase in required_phases if phase not in phases)
    failed_artifacts = []

    for artifact, expected in required_artifacts.items():
        status = artifact_status(artifacts, artifact)
        if str(status) not in {str(item) for item in expected}:
            failed_artifacts.append(
                {
                    "artifact": artifact,
                    "status": status,
                    "expected": sorted(expected),
                }
            )

    if missing_phases:
        add_finding(
            findings,
            "error",
            "architecture_phase_missing",
            "Required architecture phase is missing from phase_state.",
            requirement_id,
        )
    for item in failed_artifacts:
        add_finding(
            findings,
            "error",
            "architecture_artifact_status_failed",
            "Required architecture artifact status does not match expected values.",
            requirement_id,
            str(item["artifact"]),
        )

    return {
        "requirement_id": requirement_id,
        "description": requirement.get("description"),
        "status": "covered" if not missing_phases and not failed_artifacts else "missing_or_failed",
        "required_phases": required_phases,
        "missing_phases": missing_phases,
        "artifact_statuses": [
            {
                "artifact": artifact,
                "status": artifact_status(artifacts, artifact),
                "expected": sorted(expected),
            }
            for artifact, expected in required_artifacts.items()
        ],
        "failed_artifacts": failed_artifacts,
    }


def build_architecture_completeness_audit(
    request: dict[str, Any],
    phase_state: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate high-level workflow completeness without replacing specific audits."""
    findings: list[dict[str, Any]] = []
    phases = phase_names(phase_state)
    action = (artifacts.get("skill_update_plan") or {}).get("recommended_action")
    requirements = deepcopy(ARCHITECTURE_REQUIREMENTS)
    for requirement in requirements:
        if requirement.get("requirement_id") == "publish_completion_chain":
            requirement["artifacts"]["publish_gate"] = expected_publish_statuses(action)
            requirement["artifacts"]["install_readiness"] = expected_install_statuses(action)
    rows = [
        requirement_row(requirement, phases, artifacts, findings)
        for requirement in requirements
    ]
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
        "policy": [
            "Architecture completeness is a run-level audit over phase and artifact coverage.",
            "It checks high-level workflow shape; detailed semantics remain in each focused audit artifact.",
            "It is non-executing and does not copy, install, or mutate generated child skills.",
        ],
    }
