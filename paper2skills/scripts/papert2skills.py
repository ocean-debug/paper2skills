#!/usr/bin/env python3
"""Papert2Skills command-line entrypoint.

The CLI is intentionally thin. Engineering logic lives in stage modules next to
this file: builder runtime auditing, agent metadata auditing, request auditing, discovery, discovery audit, discovery resolution auditing, source grounding, source indexing, API/interface
grounding, source fetch boundary auditing, key API coverage auditing, source parsing coverage, source parsing audit, evidence coverage, evidence precedence, evidence claim taxonomy auditing, backend contracts, backend extension auditing, resource inventory, resource boundary auditing, task partitioning, task partition decision logging, task partition auditing, routing, eval planning,
execution planning, environment install planning, tutorial reproduction planning, contract traceability, lineage graphing, acceptance suite generation, eval splitting, external result contract auditing, result judging, drafting, self-review,
execution trace handling, execution trace validation, verification claim auditing, routing fixtures, routing metadata audits, child metadata auditing, linting, draft readiness, skill update planning, agent rollout harness planning, claim consistency audits, source grounding audits, workflow invariant audits, grounding gates,
review evolution, eval leakage auditing, requirement coverage, artifact contracts, artifact validation,
completion evidence auditing, acceptance handoff packaging, review prompt contract auditing, review prompt suite auditing, discovery match auditing, review iteration-log rendering, review cursor tracking, patch application auditing, review optimizer-state tracking, patch safety auditing, patch operation contract auditing, forward-test planning, code-fence audits, public safety audits, candidate selection auditing, candidate promotion auditing, candidate evolution auditing, quality reporting, score reporting, candidate registry, publish gating, final completion auditing, run scorecard rendering, run manifest generation,
install readiness, publish manifest auditing, builder skill package auditing, module inventory auditing, timeline reporting, and build orchestration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_metadata_audit import build_agent_metadata_audit
from agent_rollout_result_judge import build_agent_rollout_result_judge
from acceptance_handoff import build_acceptance_handoff, render_acceptance_handoff_markdown
from artifact_validator import REQUIRED_TOP_LEVEL_ARTIFACTS, validate_artifact_bundle
from build_pipeline import build
from build_timeline_audit import build_timeline_audit
from biological_claim_boundary_audit import build_biological_claim_boundary_audit
from builder_baseline_audit import build_builder_baseline_audit
from child_package_purity_audit import build_child_package_purity_audit
from code_fence_audit import audit_child_skill_code_fences
from common import BuildError, load_data, write_data, write_text
from completion_audit import build_completion_audit
from completion_evidence_audit import build_completion_evidence_audit
from discovery_resolution_audit import build_discovery_resolution_audit
from e2e_acceptance import build_e2e_acceptance
from evidence_claim_taxonomy_audit import build_evidence_claim_taxonomy_audit
from eval_leakage_audit import build_eval_leakage_audit
from external_result_contracts import build_external_result_contracts
from execution_replay_orchestrator import build_execution_replay_orchestrator
from forward_test_plan import validate_forward_test_plan
from key_api_coverage_audit import build_key_api_coverage_audit
from lint_skill import lint_child_skill
from module_inventory_audit import audit_module_inventory
from public_origin_audit import build_public_origin_audit
from public_safety_audit import audit_public_child_skill
from protocol_compliance_audit import build_protocol_compliance_audit
from run_manifest import verify_run_manifest
from skill_package_audit import audit_skill_package
from smoke_test_plan import build_smoke_test_plan
from source_fetch_boundary_audit import audit_source_fetch_boundaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build lightweight Papert2Skills child skills with review trajectory auditing.")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="Build artifacts and a lightweight child skill.")
    build_parser.add_argument("--request", required=True, help="Path to build_request.yaml or JSON.")
    build_parser.add_argument("--out", required=True, help="Run artifact directory.")

    lint_parser = sub.add_parser("lint-child", help="Lint a generated child skill structure.")
    lint_parser.add_argument("--skill", required=True, help="Child skill directory.")
    lint_parser.add_argument("--out", default=None, help="Optional lint report path.")

    validate_parser = sub.add_parser("validate-run", help="Validate a generated run artifact directory.")
    validate_parser.add_argument("--run", required=True, help="Run artifact directory.")
    validate_parser.add_argument("--out", default=None, help="Optional validation report path.")

    audit_parser = sub.add_parser("audit-child", help="Audit generated child skill markdown.")
    audit_parser.add_argument("--skill", required=True, help="Child skill directory.")
    audit_parser.add_argument("--api-grounding", required=True, help="api_grounding.yaml path.")
    audit_parser.add_argument("--interface-grounding", required=True, help="interface_grounding.yaml path.")
    audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    public_audit_parser = sub.add_parser("audit-public-child", help="Audit generated public child skill markdown for release safety.")
    public_audit_parser.add_argument("--skill", required=True, help="Child skill directory.")
    public_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    purity_audit_parser = sub.add_parser("audit-child-package-purity", help="Audit generated child skill file-set purity.")
    purity_audit_parser.add_argument("--skill", required=True, help="Child skill directory.")
    purity_audit_parser.add_argument("--skill-spec", required=True, help="skill_spec.yaml path.")
    purity_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    biological_audit_parser = sub.add_parser("audit-biological-claims", help="Audit rendered child skill biological claim boundaries.")
    biological_audit_parser.add_argument("--skill", required=True, help="Child skill directory.")
    biological_audit_parser.add_argument("--task-catalog", required=True, help="task_catalog.yaml path.")
    biological_audit_parser.add_argument("--source-grounding", required=True, help="source_grounding.yaml path.")
    biological_audit_parser.add_argument("--evidence-cards", required=True, help="evidence_cards.yaml path.")
    biological_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    verify_manifest_parser = sub.add_parser("verify-run-manifest", help="Verify files recorded in run_manifest.yaml.")
    verify_manifest_parser.add_argument("--run", required=True, help="Run artifact directory.")
    verify_manifest_parser.add_argument("--manifest", default=None, help="Optional run_manifest.yaml path.")
    verify_manifest_parser.add_argument("--out", default=None, help="Optional verification report path.")

    timeline_audit_parser = sub.add_parser("audit-build-timeline", help="Audit build_timeline.yaml integrity for a run directory.")
    timeline_audit_parser.add_argument("--run", required=True, help="Run artifact directory.")
    timeline_audit_parser.add_argument("--out", default=None, help="Optional build timeline audit report path.")

    completion_parser = sub.add_parser("audit-completion", help="Recompute the final completion audit for a run directory.")
    completion_parser.add_argument("--run", required=True, help="Run artifact directory.")
    completion_parser.add_argument("--out", default=None, help="Optional completion audit report path.")

    protocol_parser = sub.add_parser("audit-protocol-compliance", help="Recompute cross-stage protocol compliance for a run directory.")
    protocol_parser.add_argument("--run", required=True, help="Run artifact directory.")
    protocol_parser.add_argument("--out", default=None, help="Optional protocol compliance audit report path.")

    agent_metadata_parser = sub.add_parser("audit-agent-metadata", help="Audit SKILL.md and agents/openai.yaml metadata alignment.")
    agent_metadata_parser.add_argument("--skill", required=True, help="Skill package directory.")
    agent_metadata_parser.add_argument("--out", default=None, help="Optional audit report path.")

    public_origin_parser = sub.add_parser("audit-public-origin", help="Audit README and skill package text for private origin markers.")
    public_origin_parser.add_argument("--repo-root", required=True, help="Repository root containing README.md.")
    public_origin_parser.add_argument("--skill", required=True, help="Skill package directory.")
    public_origin_parser.add_argument("--out", default=None, help="Optional audit report path.")

    fetch_boundary_parser = sub.add_parser("audit-source-fetch-boundaries", help="Audit source fetch opt-in and run-directory boundaries.")
    fetch_boundary_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    fetch_boundary_parser.add_argument("--source-fetch-report", required=True, help="source_fetch_report.yaml path.")
    fetch_boundary_parser.add_argument("--out", default=None, help="Optional audit report path.")

    key_api_parser = sub.add_parser("audit-key-api-coverage", help="Audit explicit key API coverage against parsed grounding.")
    key_api_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    key_api_parser.add_argument("--api-grounding", required=True, help="api_grounding.yaml path.")
    key_api_parser.add_argument("--interface-grounding", required=True, help="interface_grounding.yaml path.")
    key_api_parser.add_argument("--out", default=None, help="Optional audit report path.")

    discovery_resolution_parser = sub.add_parser("audit-discovery-resolution", help="Audit final Discovery resolution against preflight and update planning.")
    discovery_resolution_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    discovery_resolution_parser.add_argument("--discovery-preflight", required=True, help="discovery_preflight.yaml path.")
    discovery_resolution_parser.add_argument("--discovery-report", required=True, help="discovery_report.yaml path.")
    discovery_resolution_parser.add_argument("--discovery-match-audit", required=True, help="discovery_match_audit.yaml path.")
    discovery_resolution_parser.add_argument("--skill-update-plan", required=True, help="skill_update_plan.yaml path.")
    discovery_resolution_parser.add_argument("--out", default=None, help="Optional audit report path.")

    eval_leakage_parser = sub.add_parser("audit-eval-leakage", help="Audit eval split isolation and rollout prompt leakage.")
    eval_leakage_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    eval_leakage_parser.add_argument("--eval-splits", required=True, help="eval_splits.yaml path.")
    eval_leakage_parser.add_argument("--forward-test-plan", required=True, help="forward_test_plan.yaml path.")
    eval_leakage_parser.add_argument("--agent-rollout-harness", required=True, help="agent_rollout_harness.yaml path.")
    eval_leakage_parser.add_argument("--eval-result-judge", required=True, help="eval_result_judge.yaml path.")
    eval_leakage_parser.add_argument("--out", default=None, help="Optional audit report path.")

    external_result_parser = sub.add_parser("audit-external-results", help="Audit supplied external eval and rollout result contracts.")
    external_result_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    external_result_parser.add_argument("--out", default=None, help="Optional audit report path.")

    evidence_taxonomy_parser = sub.add_parser("audit-evidence-claim-taxonomy", help="Audit evidence claim taxonomy and source priority by task_type.")
    evidence_taxonomy_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    evidence_taxonomy_parser.add_argument("--task-catalog", required=True, help="task_catalog.yaml path.")
    evidence_taxonomy_parser.add_argument("--evidence-cards", required=True, help="evidence_cards.yaml path.")
    evidence_taxonomy_parser.add_argument("--source-grounding", required=True, help="source_grounding.yaml path.")
    evidence_taxonomy_parser.add_argument("--evidence-precedence", required=True, help="evidence_precedence.yaml path.")
    evidence_taxonomy_parser.add_argument("--execution-trace-validation", required=True, help="execution_trace_validation.yaml path.")
    evidence_taxonomy_parser.add_argument("--out", default=None, help="Optional audit report path.")

    replay_orchestrator_parser = sub.add_parser("audit-execution-replay", help="Build and audit plan-only execution replay orchestration.")
    replay_orchestrator_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    replay_orchestrator_parser.add_argument("--tutorial-reproduction-plan", required=True, help="tutorial_reproduction_plan.yaml path.")
    replay_orchestrator_parser.add_argument("--execution-plan", required=True, help="execution_plan.yaml path.")
    replay_orchestrator_parser.add_argument("--environment-install-plan", required=True, help="environment_install_plan.yaml path.")
    replay_orchestrator_parser.add_argument("--out", default=None, help="Optional orchestration report path.")

    e2e_parser = sub.add_parser("audit-e2e-acceptance", help="Build and audit plan-only E2E acceptance scenarios.")
    e2e_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    e2e_parser.add_argument("--task-catalog", required=True, help="task_catalog.yaml path.")
    e2e_parser.add_argument("--acceptance-suite", required=True, help="acceptance_suite.yaml path.")
    e2e_parser.add_argument("--eval-splits", required=True, help="eval_splits.yaml path.")
    e2e_parser.add_argument("--forward-test-plan", required=True, help="forward_test_plan.yaml path.")
    e2e_parser.add_argument("--agent-rollout-harness", required=True, help="agent_rollout_harness.yaml path.")
    e2e_parser.add_argument("--agent-rollout-result-judge", required=True, help="agent_rollout_result_judge.yaml path.")
    e2e_parser.add_argument("--execution-replay-orchestrator", required=True, help="execution_replay_orchestrator.yaml path.")
    e2e_parser.add_argument("--verification-claim-audit", required=True, help="verification_claim_audit.yaml path.")
    e2e_parser.add_argument("--out", default=None, help="Optional E2E acceptance report path.")

    smoke_parser = sub.add_parser("audit-smoke-test-plan", help="Build and audit plan-only smoke test scenarios.")
    smoke_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    smoke_parser.add_argument("--task-catalog", required=True, help="task_catalog.yaml path.")
    smoke_parser.add_argument("--out", default=None, help="Optional smoke test plan report path.")

    completion_evidence_parser = sub.add_parser("audit-completion-evidence", help="Audit whether completion claims are supported by supplied evidence.")
    completion_evidence_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    completion_evidence_parser.add_argument("--requirement-coverage", required=True, help="requirement_coverage.yaml path.")
    completion_evidence_parser.add_argument("--agent-rollout-result-judge", required=True, help="agent_rollout_result_judge.yaml path.")
    completion_evidence_parser.add_argument("--e2e-acceptance", required=True, help="e2e_acceptance.yaml path.")
    completion_evidence_parser.add_argument("--execution-trace-validation", required=True, help="execution_trace_validation.yaml path.")
    completion_evidence_parser.add_argument("--execution-replay-orchestrator", required=True, help="execution_replay_orchestrator.yaml path.")
    completion_evidence_parser.add_argument("--out", default=None, help="Optional completion evidence audit report path.")

    acceptance_handoff_parser = sub.add_parser("build-acceptance-handoff", help="Build a plan-only external acceptance handoff package.")
    acceptance_handoff_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    acceptance_handoff_parser.add_argument("--e2e-acceptance", required=True, help="e2e_acceptance.yaml path.")
    acceptance_handoff_parser.add_argument("--agent-rollout-harness", required=True, help="agent_rollout_harness.yaml path.")
    acceptance_handoff_parser.add_argument("--execution-replay-orchestrator", required=True, help="execution_replay_orchestrator.yaml path.")
    acceptance_handoff_parser.add_argument("--completion-evidence-audit", required=True, help="completion_evidence_audit.yaml path.")
    acceptance_handoff_parser.add_argument("--publish-manifest", default=None, help="Optional publish_manifest.yaml path.")
    acceptance_handoff_parser.add_argument("--out", default=None, help="Optional handoff YAML path.")
    acceptance_handoff_parser.add_argument("--markdown-out", default=None, help="Optional handoff Markdown path.")

    rollout_result_parser = sub.add_parser("judge-agent-rollout-results", help="Judge explicitly supplied agent rollout results.")
    rollout_result_parser.add_argument("--request", required=True, help="Normalized request or build request path.")
    rollout_result_parser.add_argument("--agent-rollout-harness", required=True, help="agent_rollout_harness.yaml path.")
    rollout_result_parser.add_argument("--eval-leakage-audit", required=True, help="eval_leakage_audit.yaml path.")
    rollout_result_parser.add_argument("--out", default=None, help="Optional judge report path.")

    forward_test_parser = sub.add_parser("validate-forward-test-plan", help="Validate a saved plan-only forward-test artifact.")
    forward_test_parser.add_argument("--plan", required=True, help="forward_test_plan.yaml path.")
    forward_test_parser.add_argument("--out", default=None, help="Optional validation report path.")

    package_audit_parser = sub.add_parser("audit-skill-package", help="Audit a Codex skill package structure.")
    package_audit_parser.add_argument("--skill", required=True, help="Skill package directory.")
    package_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    inventory_audit_parser = sub.add_parser("audit-module-inventory", help="Audit builder script module inventory docs.")
    inventory_audit_parser.add_argument("--skill", required=True, help="Skill package directory.")
    inventory_audit_parser.add_argument("--repo-root", default=None, help="Repository root containing README.md.")
    inventory_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    baseline_audit_parser = sub.add_parser("audit-builder-baseline", help="Audit builder engineering baseline family coverage.")
    baseline_audit_parser.add_argument("--skill", required=True, help="Skill package directory.")
    baseline_audit_parser.add_argument("--repo-root", default=None, help="Repository root containing README.md.")
    baseline_audit_parser.add_argument("--out", default=None, help="Optional audit report path.")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            manifest = build(Path(args.request), Path(args.out))
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 0
        if args.command == "lint-child":
            report = lint_child_skill(Path(args.skill))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "validate-run":
            run_dir = Path(args.run)
            artifacts = {}
            for name in REQUIRED_TOP_LEVEL_ARTIFACTS:
                path = run_dir / f"{name}.yaml"
                if path.exists():
                    artifacts[name] = load_data(path)
            report = validate_artifact_bundle(artifacts)
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-child":
            report = audit_child_skill_code_fences(
                Path(args.skill),
                load_data(Path(args.api_grounding)),
                load_data(Path(args.interface_grounding)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-public-child":
            report = audit_public_child_skill(Path(args.skill))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-child-package-purity":
            skill_spec = load_data(Path(args.skill_spec))
            report = build_child_package_purity_audit(skill_spec.get("request", {}), Path(args.skill), skill_spec)
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-biological-claims":
            report = build_biological_claim_boundary_audit(
                Path(args.skill),
                load_data(Path(args.task_catalog)),
                load_data(Path(args.source_grounding)),
                load_data(Path(args.evidence_cards)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "verify-run-manifest":
            run_dir = Path(args.run)
            manifest_path = Path(args.manifest) if args.manifest else run_dir / "run_manifest.yaml"
            report = verify_run_manifest(run_dir, load_data(manifest_path))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-build-timeline":
            run_dir = Path(args.run)
            report = build_timeline_audit(
                load_data(run_dir / "request.yaml"),
                load_data(run_dir / "build_timeline.yaml"),
                load_data(run_dir / "phase_state.yaml"),
                load_data(run_dir / "review_summary.yaml"),
                load_data(run_dir / "publish_gate.yaml"),
                load_data(run_dir / "quality_report.yaml"),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-completion":
            run_dir = Path(args.run)
            request = load_data(run_dir / "request.yaml")
            publish_manifest = load_data(run_dir / "publish_manifest.yaml")
            report = build_completion_audit(
                request,
                load_data(run_dir / "phase_state.yaml"),
                load_data(run_dir / "builder_runtime_audit.yaml"),
                load_data(run_dir / "agent_metadata_audit.yaml"),
                load_data(run_dir / "public_origin_audit.yaml"),
                load_data(run_dir / "module_inventory_audit.yaml"),
                load_data(run_dir / "builder_baseline_audit.yaml"),
                load_data(run_dir / "skill_package_audit.yaml"),
                load_data(run_dir / "request_template_audit.yaml"),
                load_data(run_dir / "builder_version_audit.yaml"),
                load_data(run_dir / "request_audit.yaml"),
                load_data(run_dir / "request_fingerprint.yaml"),
                load_data(run_dir / "external_result_contracts.yaml"),
                load_data(run_dir / "phase_state_audit.yaml"),
                load_data(run_dir / "protocol_compliance_audit.yaml"),
                load_data(run_dir / "requirement_coverage.yaml"),
                load_data(run_dir / "completion_evidence_audit.yaml"),
                load_data(run_dir / "acceptance_handoff.yaml"),
                load_data(run_dir / "architecture_completeness_audit.yaml"),
                load_data(run_dir / "artifact_validation.yaml"),
                load_data(run_dir / "publish_gate.yaml"),
                load_data(run_dir / "quality_report.yaml"),
                load_data(run_dir / "score_report.yaml"),
                load_data(run_dir / "release_package.yaml"),
                load_data(run_dir / "install_readiness.yaml"),
                publish_manifest,
                load_data(run_dir / "publish_manifest_audit.yaml"),
                load_data(run_dir / "skill_update_plan.yaml"),
                load_data(run_dir / "skill_update_audit.yaml"),
                load_data(run_dir / "discovery_match_audit.yaml"),
                load_data(run_dir / "discovery_resolution_audit.yaml"),
                load_data(run_dir / "review_optimizer_state.yaml"),
                load_data(run_dir / "patch_safety_audit.yaml"),
                load_data(run_dir / "patch_operation_contracts.yaml"),
                load_data(run_dir / "candidate_selection_audit.yaml"),
                load_data(run_dir / "candidate_promotion_audit.yaml"),
                load_data(run_dir / "final_candidate_audit.yaml"),
                load_data(run_dir / "candidate_evolution_audit.yaml"),
                load_data(run_dir / "artifact_closure_audit.yaml"),
                load_data(run_dir / "source_fetch_boundary_audit.yaml"),
                load_data(run_dir / "source_ingestion_audit.yaml"),
                load_data(run_dir / "source_grounding_audit.yaml"),
                load_data(run_dir / "key_api_coverage_audit.yaml"),
                load_data(run_dir / "verification_claim_audit.yaml"),
                load_data(run_dir / "execution_replay_orchestrator.yaml"),
                load_data(run_dir / "backend_extension_audit.yaml"),
                load_data(run_dir / "resource_boundary_audit.yaml"),
                load_data(run_dir / "evidence_claim_taxonomy_audit.yaml"),
                load_data(run_dir / "child_metadata_audit.yaml"),
                load_data(run_dir / "child_package_purity_audit.yaml"),
                load_data(run_dir / "biological_claim_boundary_audit.yaml"),
                load_data(run_dir / "review_prompt_contracts.yaml"),
                load_data(run_dir / "review_prompt_materials.yaml"),
                load_data(run_dir / "review_prompt_suite_audit.yaml"),
                load_data(run_dir / "review_iteration_log.yaml"),
                load_data(run_dir / "review_remediation_audit.yaml"),
                load_data(run_dir / "review_trajectory_audit.yaml"),
                load_data(run_dir / "agent_rollout_harness.yaml"),
                load_data(run_dir / "agent_rollout_audit.yaml"),
                load_data(run_dir / "eval_leakage_audit.yaml"),
                load_data(run_dir / "agent_rollout_result_judge.yaml"),
                load_data(run_dir / "e2e_acceptance.yaml"),
                load_data(run_dir / "smoke_test_plan.yaml"),
                load_data(run_dir / "routing_metadata_audit.yaml"),
                load_data(run_dir / "codex_publish_adapter.yaml"),
                load_data(run_dir / "release_action_audit.yaml"),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-protocol-compliance":
            run_dir = Path(args.run)
            artifacts = {
                "phase_state_audit": load_data(run_dir / "phase_state_audit.yaml"),
                "request_fingerprint": load_data(run_dir / "request_fingerprint.yaml"),
                "external_result_contracts": load_data(run_dir / "external_result_contracts.yaml"),
                "output_boundary_audit": load_data(run_dir / "output_boundary_audit.yaml"),
                "discovery_resolution_audit": load_data(run_dir / "discovery_resolution_audit.yaml"),
                "environment_install_plan": load_data(run_dir / "environment_install_plan.yaml"),
                "execution_plan": load_data(run_dir / "execution_plan.yaml"),
                "tutorial_reproduction_plan": load_data(run_dir / "tutorial_reproduction_plan.yaml"),
                "execution_replay_orchestrator": load_data(run_dir / "execution_replay_orchestrator.yaml"),
                "skill_update_plan": load_data(run_dir / "skill_update_plan.yaml"),
                "skill_update_audit": load_data(run_dir / "skill_update_audit.yaml"),
                "forward_test_plan": load_data(run_dir / "forward_test_plan.yaml"),
                "agent_rollout_harness": load_data(run_dir / "agent_rollout_harness.yaml"),
                "agent_rollout_audit": load_data(run_dir / "agent_rollout_audit.yaml"),
                "e2e_acceptance": load_data(run_dir / "e2e_acceptance.yaml"),
                "smoke_test_plan": load_data(run_dir / "smoke_test_plan.yaml"),
                "acceptance_handoff": load_data(run_dir / "acceptance_handoff.yaml"),
                "verification_claim_audit": load_data(run_dir / "verification_claim_audit.yaml"),
                "completion_evidence_audit": load_data(run_dir / "completion_evidence_audit.yaml"),
            }
            report = build_protocol_compliance_audit(
                load_data(run_dir / "request.yaml"),
                load_data(run_dir / "phase_state.yaml"),
                artifacts,
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-agent-metadata":
            report = build_agent_metadata_audit(Path(args.skill))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-public-origin":
            report = build_public_origin_audit(Path(args.repo_root), Path(args.skill))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-source-fetch-boundaries":
            report = audit_source_fetch_boundaries(
                load_data(Path(args.request)),
                load_data(Path(args.source_fetch_report)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-key-api-coverage":
            report = build_key_api_coverage_audit(
                load_data(Path(args.request)),
                load_data(Path(args.api_grounding)),
                load_data(Path(args.interface_grounding)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-discovery-resolution":
            report = build_discovery_resolution_audit(
                load_data(Path(args.request)),
                load_data(Path(args.discovery_preflight)),
                load_data(Path(args.discovery_report)),
                load_data(Path(args.discovery_match_audit)),
                load_data(Path(args.skill_update_plan)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-eval-leakage":
            report = build_eval_leakage_audit(
                load_data(Path(args.request)),
                load_data(Path(args.eval_splits)),
                load_data(Path(args.forward_test_plan)),
                load_data(Path(args.agent_rollout_harness)),
                load_data(Path(args.eval_result_judge)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-external-results":
            report = build_external_result_contracts(load_data(Path(args.request)))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-evidence-claim-taxonomy":
            report = build_evidence_claim_taxonomy_audit(
                load_data(Path(args.request)),
                load_data(Path(args.task_catalog)),
                load_data(Path(args.evidence_cards)),
                load_data(Path(args.source_grounding)),
                load_data(Path(args.evidence_precedence)),
                load_data(Path(args.execution_trace_validation)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-execution-replay":
            report = build_execution_replay_orchestrator(
                load_data(Path(args.request)),
                load_data(Path(args.tutorial_reproduction_plan)),
                load_data(Path(args.execution_plan)),
                load_data(Path(args.environment_install_plan)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-e2e-acceptance":
            report = build_e2e_acceptance(
                load_data(Path(args.request)),
                load_data(Path(args.task_catalog)),
                load_data(Path(args.acceptance_suite)),
                load_data(Path(args.eval_splits)),
                load_data(Path(args.forward_test_plan)),
                load_data(Path(args.agent_rollout_harness)),
                load_data(Path(args.agent_rollout_result_judge)),
                load_data(Path(args.execution_replay_orchestrator)),
                load_data(Path(args.verification_claim_audit)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-smoke-test-plan":
            report = build_smoke_test_plan(
                load_data(Path(args.request)),
                load_data(Path(args.task_catalog)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-completion-evidence":
            report = build_completion_evidence_audit(
                load_data(Path(args.request)),
                load_data(Path(args.requirement_coverage)),
                load_data(Path(args.agent_rollout_result_judge)),
                load_data(Path(args.e2e_acceptance)),
                load_data(Path(args.execution_trace_validation)),
                load_data(Path(args.execution_replay_orchestrator)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "build-acceptance-handoff":
            report = build_acceptance_handoff(
                load_data(Path(args.request)),
                load_data(Path(args.e2e_acceptance)),
                load_data(Path(args.agent_rollout_harness)),
                load_data(Path(args.execution_replay_orchestrator)),
                load_data(Path(args.completion_evidence_audit)),
                load_data(Path(args.publish_manifest)) if args.publish_manifest else None,
            )
            if args.out:
                write_data(Path(args.out), report)
            if args.markdown_out:
                write_text(Path(args.markdown_out), render_acceptance_handoff_markdown(report))
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "judge-agent-rollout-results":
            report = build_agent_rollout_result_judge(
                load_data(Path(args.request)),
                load_data(Path(args.agent_rollout_harness)),
                load_data(Path(args.eval_leakage_audit)),
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] in {"pass", "not_run"} else 1
        if args.command == "validate-forward-test-plan":
            report = validate_forward_test_plan(load_data(Path(args.plan)))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-skill-package":
            report = audit_skill_package(Path(args.skill))
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-module-inventory":
            report = audit_module_inventory(
                Path(args.skill),
                Path(args.repo_root) if args.repo_root else None,
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
        if args.command == "audit-builder-baseline":
            report = build_builder_baseline_audit(
                Path(args.skill),
                Path(args.repo_root) if args.repo_root else None,
            )
            if args.out:
                write_data(Path(args.out), report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["status"] == "pass" else 1
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
