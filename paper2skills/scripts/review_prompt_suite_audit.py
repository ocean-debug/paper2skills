"""Audit review-loop duty coverage across prompt/state contracts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REVIEW_DUTIES: list[dict[str, Any]] = [
    {
        "duty": "source_grounding",
        "required_signals": ["source_grounding", "api_grounding", "interface_grounding", "evidence", "sources", "evidence_refs"],
        "required_roles": ["critic"],
        "purpose": "Check source, evidence, API, and interface grounding before claims are accepted.",
    },
    {
        "duty": "record_score",
        "required_signals": ["record_score"],
        "required_roles": ["record_score"],
        "purpose": "Record candidate scoring before any optimizer decision.",
    },
    {
        "duty": "rollout_plan",
        "required_signals": ["rollout_plan"],
        "required_roles": ["rollout_plan"],
        "purpose": "Expose plan-only rollout/eval inputs for agent-driven optimization.",
    },
    {
        "duty": "task_partition_and_routing",
        "required_signals": ["task_partition", "task_routing", "task_split", "routing"],
        "required_roles": ["draft_snapshot", "critic"],
        "purpose": "Check task_type partitioning and same-skill routing coverage.",
    },
    {
        "duty": "input_output_contracts",
        "required_signals": ["input_contracts", "output_contracts", "input_contract", "output_contract", "parameter_constraints", "operational_recipe", "operational_recipes"],
        "required_roles": ["critic"],
        "purpose": "Check task input requirements, output expectations, parameter constraints, and agent-usable operational recipes.",
    },
    {
        "duty": "refusal_boundaries",
        "required_signals": ["refusal_boundaries", "refusal", "backend"],
        "required_roles": ["critic"],
        "purpose": "Check unsupported backend, wrong task, and missing-input refusal boundaries.",
    },
    {
        "duty": "validation_rules",
        "required_signals": ["validation_rules", "validation"],
        "required_roles": ["critic"],
        "purpose": "Check minimum technical validation rules for every task_type.",
    },
    {
        "duty": "verification_boundaries",
        "required_signals": ["verification_labels", "verification"],
        "required_roles": ["critic", "gate"],
        "purpose": "Check that execution_verified is never claimed without successful execution evidence.",
    },
    {
        "duty": "patch_planning",
        "required_signals": ["patch_plan"],
        "required_roles": ["patch_plan"],
        "purpose": "Check agent-driven patch planning is represented as a bounded state.",
    },
    {
        "duty": "optimizer_reflection",
        "required_signals": ["analyst_error", "analyst_success", "merge_failure", "merge_success"],
        "required_roles": ["analyst_error", "analyst_success", "merge_failure", "merge_success"],
        "purpose": "Check non-passing iterations expose failure and success reflection phases.",
        "when": "not_passed",
    },
    {
        "duty": "ranking_and_slow_update",
        "required_signals": ["merge_final", "ranking", "slow_update"],
        "required_roles": ["merge_final", "ranking", "slow_update"],
        "purpose": "Check non-passing iterations expose final merge, ranking, and slow-update phases.",
        "when": "not_passed",
    },
    {
        "duty": "gate_discipline",
        "required_signals": ["gate"],
        "required_roles": ["gate"],
        "purpose": "Check pass, patch-for-next-iteration, and no-patch stop decisions are explicit.",
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
    duty: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        finding["iteration"] = iteration
    if duty:
        finding["duty"] = duty
    findings.append(finding)


def state_roles(iteration: dict[str, Any]) -> set[str]:
    return {str(state.get("role")) for state in iteration.get("states", []) if state.get("role")}


def review_signals(iteration: dict[str, Any]) -> set[str]:
    signals: set[str] = set()
    for finding in iteration.get("findings", []):
        signal = finding.get("check") or finding.get("code")
        if signal:
            signals.add(str(signal))
    for state in iteration.get("states", []):
        role = state.get("role")
        if role:
            signals.add(str(role))
        if state.get("role") == "critic":
            for item in state.get("item_results", []):
                item_name = item.get("item")
                if item_name:
                    signals.add(str(item_name))
            for focus in (state.get("focus_counts") or {}):
                signals.add(str(focus))
    patch_plan = iteration.get("patch_plan") or {}
    if "changed" in patch_plan and "actions" in patch_plan:
        signals.add("patch_plan")
    if any(state.get("role") == "gate" for state in iteration.get("states", [])):
        signals.add("gate")
    return signals


def duty_record(iteration: dict[str, Any], duty: dict[str, Any]) -> dict[str, Any]:
    signals = review_signals(iteration)
    roles = state_roles(iteration)
    required_signals = set(duty["required_signals"])
    required_roles = set(duty["required_roles"])
    observed_signals = sorted(required_signals.intersection(signals))
    missing_roles = sorted(required_roles.difference(roles))
    return {
        "iteration": iteration.get("iteration"),
        "duty": duty["duty"],
        "purpose": duty["purpose"],
        "required_signals": sorted(duty["required_signals"]),
        "observed_signals": observed_signals,
        "required_roles": sorted(duty["required_roles"]),
        "missing_roles": missing_roles,
        "covered": bool(observed_signals) and not missing_roles,
    }


def build_review_prompt_suite_audit(
    request: dict[str, Any],
    review_result: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
    review_prompt_materials: dict[str, Any],
    review_optimizer_state: dict[str, Any],
) -> dict[str, Any]:
    """Audit that each review iteration covers the required review duties."""
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    if review_prompt_contracts.get("status") != "pass":
        add_finding(findings, "error", "review_prompt_contracts_failed", "Review duty coverage requires passing state-role contracts.")
    if review_prompt_materials.get("status") != "pass":
        add_finding(findings, "error", "review_prompt_materials_failed", "Review duty coverage requires passing prompt materials.")
    if review_optimizer_state.get("status") != "pass":
        add_finding(findings, "error", "review_optimizer_state_failed", "Review duty coverage requires passing optimizer-state audit.")

    iterations = review_result.get("iterations", [])
    if not iterations:
        add_finding(findings, "error", "missing_review_iterations", "Review prompt suite audit requires at least one review iteration.")

    for iteration in iterations:
        iteration_index = int(iteration.get("iteration") or 0)
        for duty in REVIEW_DUTIES:
            if duty.get("when") == "not_passed" and iteration.get("passed"):
                continue
            record = duty_record(iteration, duty)
            records.append(record)
            if not record["observed_signals"]:
                add_finding(
                    findings,
                    "error",
                    "review_duty_missing_signal",
                    "Review iteration does not expose any signal for this required duty.",
                    iteration_index,
                    duty["duty"],
                )
            if record["missing_roles"]:
                add_finding(
                    findings,
                    "error",
                    "review_duty_missing_role",
                    "Review iteration is missing a state role required for this duty.",
                    iteration_index,
                    duty["duty"],
                )

    covered_count = sum(1 for record in records if record["covered"])
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "review_prompt_contracts_status": review_prompt_contracts.get("status"),
        "review_prompt_materials_status": review_prompt_materials.get("status"),
        "review_optimizer_state_status": review_optimizer_state.get("status"),
        "duty_count": len(REVIEW_DUTIES),
        "iteration_count": len(iterations),
        "record_count": len(records),
        "covered_count": covered_count,
        "duties": REVIEW_DUTIES,
        "records": records,
        "findings": findings,
        "policy": [
            "Review prompt suite audit checks duty coverage, not generated child-skill content.",
            "Every review iteration must expose signals for grounding, partitioning, contracts, refusals, validation, verification, patch planning, and gate discipline.",
            "The audit is static and non-executing; it only reads review-loop artifacts.",
        ],
    }
