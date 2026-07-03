"""Plan-only agent rollout harness assembled from forward-test artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


REQUIRED_ROLLOUT_KINDS = {
    "task_type_routing",
    "input_output_contract",
    "structured_refusal",
    "execution_boundary",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    scenario_id: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if scenario_id:
        item["scenario_id"] = scenario_id
    findings.append(item)


def rollout_case(scenario: dict[str, Any], index: int) -> dict[str, Any]:
    scenario_id = str(scenario.get("scenario_id") or f"scenario:{index:04d}")
    return {
        "rollout_id": f"rollout:{slugify(scenario_id)}",
        "scenario_id": scenario_id,
        "source_case_id": scenario.get("source_case_id"),
        "split": scenario.get("split"),
        "kind": scenario.get("kind"),
        "task_type": scenario.get("task_type"),
        "agent_prompt": scenario.get("agent_prompt"),
        "judge_metadata": {
            "expected_behavior": scenario.get("expected_behavior", {}),
            "judge_checks": scenario.get("judge_checks", []),
            "case_checks": scenario.get("case_checks", []),
        },
        "leakage_controls": scenario.get("leakage_controls", []),
        "execution_policy": "plan_only",
        "status": "planned",
    }


def prompt_leaks_judge_metadata(case: dict[str, Any]) -> bool:
    prompt = str(case.get("agent_prompt") or "").lower()
    leaked_terms = ["expected_behavior", "final_score", "review finding", "judge_metadata"]
    return any(term in prompt for term in leaked_terms)


def build_agent_rollout_harness(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    routing_fixture: dict[str, Any],
    eval_splits: dict[str, Any],
    forward_test_plan: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scenarios = forward_test_plan.get("scenarios", [])
    cases = [rollout_case(scenario, index) for index, scenario in enumerate(scenarios, start=1)]

    task_types = {str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")}
    covered_tasks = {str(case.get("task_type")) for case in cases if case.get("task_type") not in {None, "global", "ambiguity"}}
    missing_tasks = sorted(task_types.difference(covered_tasks))
    for task_type in missing_tasks:
        add_finding(
            findings,
            "error",
            "task_missing_rollout_case",
            "Task_type has no planned agent rollout case.",
            task_type,
        )

    case_kinds = {str(case.get("kind")) for case in cases if case.get("kind")}
    missing_kinds = sorted(REQUIRED_ROLLOUT_KINDS.difference(case_kinds))
    for kind in missing_kinds:
        add_finding(
            findings,
            "error",
            "missing_required_rollout_kind",
            "Agent rollout harness is missing a required scenario kind.",
            kind,
        )

    split_counts: dict[str, int] = {}
    for case in cases:
        split = str(case.get("split") or "unsplit")
        split_counts[split] = split_counts.get(split, 0) + 1
        scenario_id = str(case.get("scenario_id") or "")
        if not case.get("agent_prompt"):
            add_finding(findings, "error", "rollout_case_missing_prompt", "Rollout case has no agent prompt.", scenario_id)
        if case.get("execution_policy") != "plan_only":
            add_finding(findings, "error", "rollout_case_not_plan_only", "Rollout case must stay plan-only.", scenario_id)
        if prompt_leaks_judge_metadata(case):
            add_finding(findings, "error", "rollout_prompt_leaks_judge_metadata", "Rollout prompt leaks judge-only metadata.", scenario_id)
        if not case.get("judge_metadata", {}).get("judge_checks"):
            add_finding(findings, "error", "rollout_case_missing_judge_checks", "Rollout case has no judge checks.", scenario_id)

    if routing_fixture.get("case_count", 0) == 0:
        add_finding(findings, "error", "missing_routing_fixture", "Agent rollout harness requires routing fixture cases.")
    if eval_splits.get("status") == "fail":
        add_finding(findings, "error", "eval_splits_failed", "Agent rollout harness requires passing eval splits.")
    if forward_test_plan.get("status") != "pass":
        add_finding(findings, "error", "forward_test_plan_failed", "Agent rollout harness requires a passing forward-test plan.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "rollout_count": len(cases),
        "required_kinds": sorted(REQUIRED_ROLLOUT_KINDS),
        "kind_counts": {kind: sum(1 for case in cases if case.get("kind") == kind) for kind in sorted(case_kinds)},
        "split_counts": dict(sorted(split_counts.items())),
        "task_count": len(task_types),
        "covered_task_types": sorted(covered_tasks),
        "missing_task_types": missing_tasks,
        "cases": cases,
        "findings": findings,
        "policy": [
            "Agent rollout harness is a plan-only queue; it does not launch agents or execute package code.",
            "Agent prompts must keep expected behavior and judge checks out of the agent-visible prompt.",
            "Rollout cases must cover task routing, contracts, refusal, and execution-boundary behavior before publish.",
        ],
    }
