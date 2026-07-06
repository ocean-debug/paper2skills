"""Static prompt materials for the review-loop roles."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PROMPT_MATERIALS: list[dict[str, Any]] = [
    {
        "prompt_id": "draft_snapshot_prompt",
        "role": "draft_snapshot",
        "purpose": "Summarize current task_type and router shape before critique.",
        "allowed_inputs": ["task_catalog.yaml", "task_type_router.yaml"],
        "required_outputs": ["role", "task_types", "route_count"],
        "forbidden_outputs": ["execution claims", "file edits", "new task_type names without evidence"],
        "template": "Read task_catalog and task_type_router. Return task_types and route_count only.",
    },
    {
        "prompt_id": "record_score_prompt",
        "role": "record_score",
        "purpose": "Record the current candidate score and strict gate metadata.",
        "allowed_inputs": ["review_rubric", "task_catalog.yaml", "task_type_router.yaml"],
        "required_outputs": ["role", "iteration", "candidate_hash", "score", "total", "score_ratio", "score_source", "strict_gate"],
        "forbidden_outputs": ["unscored acceptance", "hidden scoring source"],
        "template": "Record the rubric selection score, candidate hash, and strict-greater-than gate.",
    },
    {
        "prompt_id": "rollout_plan_prompt",
        "role": "rollout_plan",
        "purpose": "Declare plan-only rollout and eval result inputs for agent-driven optimization.",
        "allowed_inputs": ["forward_test_plan.yaml", "agent_rollout_harness.yaml", "eval_splits.yaml"],
        "required_outputs": ["role", "plan_only", "target_agent", "task_types", "external_result_fields", "policy"],
        "forbidden_outputs": ["launch agents", "fabricated rollout results", "package execution"],
        "template": "Name the external result fields and keep rollout work plan-only.",
    },
    {
        "prompt_id": "critic_prompt",
        "role": "critic",
        "purpose": "Critique grounding, task split, operational recipes, contracts, refusals, validation, and verification labels.",
        "allowed_inputs": [
            "request_audit.yaml",
            "discovery_report.yaml",
            "source_grounding.yaml",
            "evidence_cards.yaml",
            "task_catalog.yaml",
            "task_type_router.yaml",
            "api_grounding.yaml",
            "interface_grounding.yaml",
            "environment_spec.yaml",
            "tutorial_catalog.yaml",
            "parameter_catalog.yaml",
        ],
        "required_outputs": ["role", "score", "total", "score_ratio", "severity_counts", "focus_counts", "item_results", "blocking_findings"],
        "forbidden_outputs": ["patch actions", "execution_verified without trace_ref", "claims without evidence_refs"],
        "template": "Score each rubric item from supplied artifacts. Treat missing or abstract operational recipes as draft failures. Emit findings with severity, check, task_type, and message.",
    },
    {
        "prompt_id": "patch_plan_prompt",
        "role": "patch_plan",
        "purpose": "Plan deterministic in-memory repairs for fixable review findings.",
        "allowed_inputs": ["review_iteration.findings", "task_catalog.yaml", "task_type_router.yaml"],
        "required_outputs": ["role", "changed", "actions", "summary"],
        "forbidden_outputs": ["shell commands", "network access", "dependency installation", "filesystem paths"],
        "template": "Map fixable same-iteration finding codes to allowed in-memory operations. Every operation must include a stable operation_id and a non-empty finding_codes list. Do not propose commands or file mutations.",
    },
    {
        "prompt_id": "analyst_error_prompt",
        "role": "analyst_error",
        "purpose": "Analyze failure minibatches or rubric blockers.",
        "allowed_inputs": ["review_iteration.findings", "agent_rollout_results", "eval_results"],
        "required_outputs": ["analysis", "failure_patterns", "proposed_fixes"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["analysis", "error_analysis", "failure_patterns", "proposed_fixes", "findings"],
        "forbidden_outputs": ["commands", "network access", "unbounded edits"],
        "template": "Group failure patterns and propose bounded edits for the current task_catalog/router artifacts.",
    },
    {
        "prompt_id": "analyst_success_prompt",
        "role": "analyst_success",
        "purpose": "Analyze success cases and preserve behavior that should not regress.",
        "allowed_inputs": ["agent_rollout_results", "eval_results", "current task contracts"],
        "required_outputs": ["analysis", "success_patterns", "preserved_behaviors"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["analysis", "success_patterns", "preserve", "preserved_behaviors", "findings"],
        "forbidden_outputs": ["weaken refusals", "remove validation checks"],
        "template": "Summarize successful patterns that proposed edits must preserve.",
    },
    {
        "prompt_id": "merge_failure_prompt",
        "role": "merge_failure",
        "purpose": "Merge failure-derived edit proposals.",
        "allowed_inputs": ["analyst_error"],
        "required_outputs": ["operations"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["operations", "candidate_operations", "merged_operations", "edits"],
        "forbidden_outputs": ["conflicting edits", "edits outside allowed operations"],
        "template": "Deduplicate failure edits and keep only compatible bounded operations.",
    },
    {
        "prompt_id": "merge_success_prompt",
        "role": "merge_success",
        "purpose": "Merge success-derived preservation constraints.",
        "allowed_inputs": ["analyst_success"],
        "required_outputs": ["preserved_constraints"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["operations", "candidate_operations", "preserved_constraints", "edits"],
        "forbidden_outputs": ["unsupported support claims", "hidden regressions"],
        "template": "Convert success observations into preservation constraints for the final merge.",
    },
    {
        "prompt_id": "merge_final_prompt",
        "role": "merge_final",
        "purpose": "Combine failure and success proposals into one final edit pool.",
        "allowed_inputs": ["merge_failure", "merge_success"],
        "required_outputs": ["operations"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["operations", "final_operations", "merged_operations", "selected_operations"],
        "forbidden_outputs": ["duplicate target edits", "over budget edit pools"],
        "template": "Prioritize failure fixes while preserving success constraints.",
    },
    {
        "prompt_id": "ranking_prompt",
        "role": "ranking",
        "purpose": "Rank final edits under the configured edit budget.",
        "allowed_inputs": ["merge_final", "current score", "focus finding codes"],
        "required_outputs": ["operation_ids"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["operation_ids", "selected_operations", "ranked_operations", "chosen_operations", "operation_indices"],
        "forbidden_outputs": ["unranked apply", "unsupported operations"],
        "template": "Select the highest-impact bounded operations by operation_ids or operation_indices; ties and non-improving candidates are rejected after rescoring.",
    },
    {
        "prompt_id": "slow_update_prompt",
        "role": "slow_update",
        "purpose": "Record epoch-level longitudinal guidance for optimizer use only.",
        "allowed_inputs": ["review trajectory", "rejected_buffer", "score_cache"],
        "required_outputs": ["summary", "guidance"],
        "state_outputs": ["role", "status", "prompt_contract", "recorded_output_keys", "required_agent_output"],
        "payload_accepts_any_of": ["summary", "guidance", "lessons", "next_state", "longitudinal_update"],
        "forbidden_outputs": ["public child-skill claims", "runtime commands"],
        "template": "Summarize longitudinal guidance outside the public child skill.",
    },
    {
        "prompt_id": "revision_prompt",
        "role": "revision",
        "purpose": "Record deterministic in-memory changes applied by the patch planner.",
        "allowed_inputs": ["patch_plan", "patched task_catalog", "patched task_type_router"],
        "required_outputs": ["role", "changed", "changed_artifacts", "summary"],
        "forbidden_outputs": ["unplanned edits", "hidden unresolved findings", "runtime claims"],
        "template": "Summarize applied in-memory changes and changed artifacts from the patch plan.",
    },
    {
        "prompt_id": "gate_prompt",
        "role": "gate",
        "purpose": "Close the iteration with pass, patch-for-next-iteration, or no-patch stop reason.",
        "allowed_inputs": ["critic state", "patch_plan", "revision state", "review rubric threshold"],
        "required_outputs": ["role", "passed", "reason"],
        "forbidden_outputs": ["override critic errors", "ignore failed patch audits", "mark untraced execution as verified"],
        "template": "Return passed and reason from critic result, patch availability, and configured score gate.",
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    role: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if role:
        item["role"] = role
    findings.append(item)


def material_by_role() -> dict[str, dict[str, Any]]:
    return {str(material["role"]): material for material in PROMPT_MATERIALS}


def build_review_prompt_materials(
    request: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
) -> dict[str, Any]:
    """Build and audit static prompt materials for review-loop roles."""
    findings: list[dict[str, Any]] = []
    contract_roles = {str(contract.get("role")) for contract in review_prompt_contracts.get("contracts", []) if contract.get("role")}
    material_roles = set(material_by_role())

    if review_prompt_contracts.get("status") != "pass":
        add_finding(findings, "error", "review_prompt_contracts_failed", "Prompt materials require passing review prompt contracts.")

    for role in sorted(contract_roles.difference(material_roles)):
        add_finding(findings, "error", "missing_prompt_material", "A review role lacks prompt material.", role)
    for role in sorted(material_roles.difference(contract_roles)):
        add_finding(findings, "error", "prompt_material_without_contract", "Prompt material has no matching review role contract.", role)

    contract_required = {
        str(contract.get("role")): set(contract.get("required_fields", []))
        for contract in review_prompt_contracts.get("contracts", [])
        if contract.get("role")
    }
    contract_payload_any_of = {
        str(contract.get("role")): set(contract.get("agent_payload_accepts_any_of", []))
        for contract in review_prompt_contracts.get("contracts", [])
        if contract.get("role")
    }
    for material in PROMPT_MATERIALS:
        role = str(material.get("role"))
        state_outputs = set(material.get("state_outputs", material.get("required_outputs", [])))
        missing_outputs = sorted(contract_required.get(role, set()).difference(state_outputs))
        if missing_outputs:
            add_finding(
                findings,
                "error",
                "prompt_material_missing_contract_outputs",
                "Prompt material state_outputs must cover the matching review-state contract fields.",
                role,
            )
        payload_any_of = contract_payload_any_of.get(role, set())
        if payload_any_of and not payload_any_of.intersection(material.get("payload_accepts_any_of", [])):
            add_finding(
                findings,
                "error",
                "prompt_material_missing_payload_schema",
                "Prompt material must describe at least one payload field accepted by the proposal validator.",
                role,
            )
        for field in ["prompt_id", "purpose", "allowed_inputs", "required_outputs", "forbidden_outputs", "template"]:
            if not material.get(field):
                add_finding(
                    findings,
                    "error",
                    "prompt_material_missing_field",
                    "Prompt material is missing a required static field.",
                    role,
                )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_prompt_contracts_status": review_prompt_contracts.get("status"),
        "material_count": len(PROMPT_MATERIALS),
        "contract_role_count": len(contract_roles),
        "materials": PROMPT_MATERIALS,
        "findings": findings,
        "policy": [
            "Prompt materials are static run artifacts; they do not call a model or execute package code.",
            "Each review role with a state contract must have matching prompt material.",
            "Agent-facing payload fields are separate from Python-recorded review-state fields.",
            "Prompt material must declare allowed inputs, required outputs, and forbidden outputs before review duties are audited.",
        ],
    }
