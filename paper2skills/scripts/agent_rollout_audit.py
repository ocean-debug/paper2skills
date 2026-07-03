"""Cross-artifact audit for plan-only agent rollout harnesses."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    item_id: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if item_id:
        item["item_id"] = item_id
    findings.append(item)


def prompt_leaks_judge_metadata(prompt: str) -> bool:
    lowered = prompt.lower()
    leaked_terms = ["expected_behavior", "judge_metadata", "judge_checks", "final_score", "review finding"]
    return any(term in lowered for term in leaked_terms)


def build_agent_rollout_audit(
    request: dict[str, Any],
    forward_test_plan: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
) -> dict[str, Any]:
    """Audit forward-test to rollout-case mapping without executing agents."""
    findings: list[dict[str, Any]] = []
    scenarios = forward_test_plan.get("scenarios", [])
    cases = agent_rollout_harness.get("cases", [])

    if forward_test_plan.get("status") != "pass":
        add_finding(findings, "error", "forward_test_plan_failed", "Rollout audit requires a passing forward-test plan.")
    if agent_rollout_harness.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_harness_failed", "Rollout audit requires a passing rollout harness.")
    if not forward_test_plan.get("plan_only"):
        add_finding(findings, "error", "forward_test_not_plan_only", "Forward-test plan must be plan-only.")
    if not agent_rollout_harness.get("plan_only"):
        add_finding(findings, "error", "rollout_harness_not_plan_only", "Agent rollout harness must be plan-only.")

    scenario_ids = {str(scenario.get("scenario_id")) for scenario in scenarios if scenario.get("scenario_id")}
    case_scenario_ids = {str(case.get("scenario_id")) for case in cases if case.get("scenario_id")}
    for scenario_id in sorted(scenario_ids.difference(case_scenario_ids)):
        add_finding(findings, "error", "scenario_missing_rollout_case", "Forward-test scenario has no rollout case.", scenario_id)
    for scenario_id in sorted(case_scenario_ids.difference(scenario_ids)):
        add_finding(findings, "error", "rollout_case_without_scenario", "Rollout case does not map to a forward-test scenario.", scenario_id)

    rollout_ids: set[str] = set()
    duplicate_rollout_ids: set[str] = set()
    for case in cases:
        rollout_id = str(case.get("rollout_id") or "")
        scenario_id = str(case.get("scenario_id") or rollout_id or "unknown")
        if rollout_id in rollout_ids:
            duplicate_rollout_ids.add(rollout_id)
        if rollout_id:
            rollout_ids.add(rollout_id)
        if case.get("execution_policy") != "plan_only" or case.get("status") != "planned":
            add_finding(findings, "error", "rollout_case_not_plan_only", "Rollout case must remain planned and plan-only.", scenario_id)
        if not case.get("agent_prompt"):
            add_finding(findings, "error", "rollout_case_missing_prompt", "Rollout case is missing an agent prompt.", scenario_id)
        if prompt_leaks_judge_metadata(str(case.get("agent_prompt") or "")):
            add_finding(findings, "error", "rollout_prompt_leaks_judge_metadata", "Agent prompt leaks judge-only metadata.", scenario_id)
        judge_metadata = case.get("judge_metadata") or {}
        if not judge_metadata.get("expected_behavior"):
            add_finding(findings, "error", "rollout_case_missing_expected_behavior", "Rollout case lacks judge-side expected behavior.", scenario_id)
        if not judge_metadata.get("judge_checks"):
            add_finding(findings, "error", "rollout_case_missing_judge_checks", "Rollout case lacks judge-side checks.", scenario_id)
        if not case.get("leakage_controls"):
            add_finding(findings, "error", "rollout_case_missing_leakage_controls", "Rollout case lacks leakage controls.", scenario_id)

    for rollout_id in sorted(duplicate_rollout_ids):
        add_finding(findings, "error", "duplicate_rollout_id", "Rollout ids must be unique.", rollout_id)

    if agent_rollout_harness.get("rollout_count") != len(cases):
        add_finding(findings, "error", "rollout_count_mismatch", "rollout_count must equal the number of cases.")
    if forward_test_plan.get("scenario_count") != len(scenarios):
        add_finding(findings, "error", "scenario_count_mismatch", "scenario_count must equal the number of scenarios.")

    scenario_kinds = {str(scenario.get("kind")) for scenario in scenarios if scenario.get("kind")}
    rollout_kinds = {str(case.get("kind")) for case in cases if case.get("kind")}
    missing_kinds = sorted(scenario_kinds.difference(rollout_kinds))
    for kind in missing_kinds:
        add_finding(findings, "error", "rollout_missing_scenario_kind", "Rollout harness lacks a scenario kind from forward-test plan.", kind)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "forward_test_plan_status": forward_test_plan.get("status"),
        "agent_rollout_harness_status": agent_rollout_harness.get("status"),
        "scenario_count": len(scenarios),
        "rollout_count": len(cases),
        "mapped_scenario_count": len(scenario_ids.intersection(case_scenario_ids)),
        "scenario_kinds": sorted(scenario_kinds),
        "rollout_kinds": sorted(rollout_kinds),
        "findings": findings,
        "policy": [
            "Agent rollout audit is plan-only and never launches agents or package code.",
            "Each forward-test scenario must map to exactly one rollout case.",
            "Agent-visible prompts must not include judge-only expected behavior, checks, or review context.",
        ],
    }
