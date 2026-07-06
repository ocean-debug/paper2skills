"""Audit builder coverage for the expected engineering baseline families."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc
from constants import BUILDER_VERSION, SCHEMA_VERSION


BASELINE_FAMILIES: list[dict[str, Any]] = [
    {
        "family": "request_and_cli",
        "modules": ["request_model.py", "request_audit.py", "request_fingerprint.py", "request_template_audit.py", "paper2skills.py"],
    },
    {
        "family": "core_orchestration",
        "modules": ["common.py", "constants.py", "action_policy.py", "build_pipeline.py"],
    },
    {
        "family": "builder_self_audits",
        "modules": ["builder_runtime_audit.py", "agent_metadata_audit.py", "public_origin_audit.py", "module_inventory_audit.py", "builder_baseline_audit.py", "builder_version_audit.py", "skill_package_audit.py"],
    },
    {
        "family": "discovery_and_update",
        "modules": ["discovery.py", "discovery_audit.py", "discovery_match_audit.py", "discovery_resolution_audit.py", "skill_update_plan.py", "skill_update_audit.py"],
    },
    {
        "family": "source_ingestion_and_grounding",
        "modules": ["source_fetch.py", "source_fetch_boundary_audit.py", "source_index.py", "source_parser.py", "source_manifest.py", "source_grounding.py", "source_grounding_audit.py", "source_ingestion_audit.py"],
    },
    {
        "family": "source_parsing_quality",
        "modules": ["tutorial_miner.py", "source_parsing_coverage.py", "source_parsing_audit.py"],
    },
    {
        "family": "evidence_traceability",
        "modules": ["evidence_cards.py", "evidence_coverage.py", "evidence_precedence.py", "evidence_claim_taxonomy_audit.py", "contract_traceability.py", "lineage_graph.py"],
    },
    {
        "family": "interface_and_environment",
        "modules": ["api_grounding.py", "interface_inspector.py", "parameter_miner.py", "environment_miner.py", "environment_install_plan.py", "backend_contracts.py", "backend_extension_audit.py"],
    },
    {
        "family": "api_and_resource_boundaries",
        "modules": ["key_api_coverage_audit.py", "api_surface_audit.py", "resource_inventory.py", "resource_boundary_audit.py", "grounding_gate.py"],
    },
    {
        "family": "task_partition_and_routing",
        "modules": ["task_partition.py", "task_partition_decision_log.py", "task_partition_audit.py", "task_router.py", "task_conflict.py", "routing_fixture.py", "routing_metadata_audit.py"],
    },
    {
        "family": "skill_draft_and_child_audits",
        "modules": ["skill_draft.py", "child_metadata_audit.py", "child_package_purity_audit.py", "child_reference_coverage.py", "lint_skill.py", "draft_readiness.py"],
    },
    {
        "family": "self_review_and_patch_loop",
        "modules": ["self_review.py", "review_loop.py", "review_cursor.py", "review_iteration_log.py", "review_optimizer_state.py", "patch_planner.py", "patch_application.py", "patch_safety_audit.py", "patch_operation_contracts.py"],
    },
    {
        "family": "self_review_quality_audits",
        "modules": ["review_evolution.py", "review_evolution_plot.py", "review_prompt_contracts.py", "review_prompt_materials.py", "review_prompt_suite_audit.py", "review_remediation_audit.py", "review_discipline_audit.py", "review_rubric.py", "rubric_grounding_audit.py", "review_trajectory_audit.py"],
    },
    {
        "family": "candidate_and_release",
        "modules": ["draft_candidate.py", "candidate_registry.py", "candidate_selection_audit.py", "candidate_promotion_audit.py", "candidate_evolution_audit.py", "final_candidate_audit.py", "release_packager.py", "release_action_audit.py"],
    },
    {
        "family": "execution_and_validation_boundaries",
        "modules": ["execution_grounding.py", "execution_trace_validation.py", "execution_plan.py", "tutorial_reproduction_plan.py", "execution_replay_orchestrator.py", "verification_claim_audit.py", "acceptance_suite.py", "e2e_acceptance.py", "smoke_test_plan.py"],
    },
    {
        "family": "rollout_and_evaluation",
        "modules": ["eval_plan.py", "eval_splits.py", "eval_result_judge.py", "eval_leakage_audit.py", "forward_test_plan.py", "agent_rollout_harness.py", "agent_rollout_audit.py", "agent_rollout_result_judge.py"],
    },
    {
        "family": "claim_and_public_safety",
        "modules": ["claim_consistency_audit.py", "biological_claim_boundary_audit.py", "output_boundary_audit.py", "code_fence_audit.py", "public_safety_audit.py"],
    },
    {
        "family": "publish_and_manifest",
        "modules": ["publish_gate.py", "codex_publish_adapter.py", "publish_manifest_audit.py", "install_readiness.py", "run_manifest.py", "output_retention.py", "run_scorecard.py", "score_report.py", "quality_report.py"],
    },
    {
        "family": "timeline_and_protocol",
        "modules": ["phase_state.py", "phase_state_audit.py", "build_timeline.py", "build_timeline_audit.py", "protocol_compliance_audit.py", "artifact_contracts.py", "artifact_validator.py", "artifact_closure_audit.py"],
    },
    {
        "family": "completion_and_handoff",
        "modules": ["external_result_contracts.py", "workflow_invariant_audit.py", "requirement_coverage.py", "completion_evidence_audit.py", "acceptance_handoff.py", "architecture_completeness_audit.py", "completion_audit.py"],
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    family: str | None = None,
    module: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if family:
        finding["family"] = family
    if module:
        finding["module"] = module
    findings.append(finding)


def module_has_docstring(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    while lines and (lines[0].startswith("#!") or "coding:" in lines[0]):
        lines.pop(0)
    text = "\n".join(lines).lstrip()
    return text.startswith('"""') or text.startswith("'''")


def doc_mentions_module(docs: dict[str, str], module: str) -> bool:
    return any(module in text for text in docs.values())


def family_record(
    scripts_dir: Path,
    docs: dict[str, str],
    family: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    family_name = str(family["family"])
    modules = [str(item) for item in family.get("modules", [])]
    module_records = []
    for module in modules:
        path = scripts_dir / module
        exists = path.exists()
        has_docstring = exists and module_has_docstring(path)
        documented = doc_mentions_module(docs, module)
        if not exists:
            add_finding(findings, "error", "baseline_module_missing", "Engineering baseline module is missing.", family_name, module)
        elif not has_docstring:
            add_finding(findings, "error", "baseline_module_missing_docstring", "Engineering baseline module is missing a top-level docstring.", family_name, module)
        if not documented:
            add_finding(findings, "error", "baseline_module_undocumented", "Engineering baseline module is not mentioned in public inventory docs.", family_name, module)
        module_records.append(
            {
                "module": module,
                "exists": exists,
                "has_docstring": has_docstring,
                "documented": documented,
                "passed": exists and has_docstring and documented,
            }
        )
    return {
        "family": family_name,
        "module_count": len(module_records),
        "covered_module_count": sum(1 for record in module_records if record["passed"]),
        "passed": all(record["passed"] for record in module_records),
        "modules": module_records,
    }


def load_docs(repo_root: Path, skill_dir: Path) -> dict[str, str]:
    paths = {
        "README.md": repo_root / "README.md",
        "SKILL.md": skill_dir / "SKILL.md",
        "builder-architecture.md": skill_dir / "references" / "builder-architecture.md",
    }
    docs: dict[str, str] = {}
    for name, path in paths.items():
        docs[name] = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return docs


def build_builder_baseline_audit(skill_dir: Path, repo_root: Path | None = None) -> dict[str, Any]:
    """Return a static audit for engineering baseline module-family coverage."""
    repo_root = repo_root or skill_dir.parent
    scripts_dir = skill_dir / "scripts"
    docs = load_docs(repo_root, skill_dir)
    findings: list[dict[str, Any]] = []
    families = [family_record(scripts_dir, docs, family, findings) for family in BASELINE_FAMILIES]
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "skill_dir": ".",
        "repo_root": ".",
        "family_count": len(families),
        "covered_family_count": sum(1 for family in families if family["passed"]),
        "module_count": sum(family["module_count"] for family in families),
        "covered_module_count": sum(family["covered_module_count"] for family in families),
        "families": families,
        "findings": findings,
        "policy": [
            "Builder baseline audit checks engineering-family coverage, not domain correctness.",
            "Each baseline module must exist, have a top-level docstring, and appear in public inventory docs.",
            "The audit is static and does not run package code, install environments, publish skills, or mutate files.",
        ],
    }
