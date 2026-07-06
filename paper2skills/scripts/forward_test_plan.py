"""Plan-only forward-test prompts for generated child skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, public_child_skill_path, slugify
from constants import SCHEMA_VERSION


FORWARD_TEST_KINDS = {
    "task_type_routing",
    "input_output_contract",
    "structured_refusal",
    "unsupported_task",
    "ambiguity_resolution",
    "execution_boundary",
    "tutorial_reproduction_plan",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        item["task_type"] = task_type
    findings.append(item)


def case_task_type(case: dict[str, Any]) -> str:
    task_type = case.get("task_type") or case.get("expected_task_type")
    if not task_type and case.get("candidate_task_types"):
        task_type = "ambiguity"
    return str(task_type or "global")


def prompt_for_case(child_skill_dir: Path, case: dict[str, Any]) -> str:
    prompt_shape = str(case.get("prompt_shape") or "User asks for a supported package workflow.")
    return (
        f"Use the generated skill at {child_skill_dir} to handle this user request shape: "
        f"{prompt_shape} Do not inspect build artifacts unless the skill itself tells you to. "
        "Return the decision, any task_type you select, required clarifying questions, "
        "structured refusal fields if refusing, and the validation checks you would apply."
    )


def scenario_from_case(child_skill_dir: Path, case: dict[str, Any], split: str) -> dict[str, Any]:
    task_type = case_task_type(case)
    kind = str(case.get("kind") or "unknown")
    case_id = str(case.get("case_id") or f"case:{slugify(task_type)}:{slugify(kind)}")
    return {
        "scenario_id": f"forward-test:{slugify(task_type)}:{slugify(kind)}:{slugify(case_id)}",
        "source_case_id": case_id,
        "split": split,
        "kind": kind,
        "task_type": task_type,
        "agent_prompt": prompt_for_case(child_skill_dir, case),
        "expected_behavior": {
            "decision": case.get("expected_decision"),
            "task_type": case.get("expected_task_type") or case.get("task_type"),
            "reason_key": case.get("expected_reason_key"),
        },
        "judge_checks": [
            "agent uses the generated child skill as the only procedural source",
            "agent does not invent unsupported task_type entries",
            "agent asks or refuses when required inputs are absent",
            "agent separates plan-only execution from verified execution",
        ],
        "case_checks": case.get("must_check") or case.get("required_checks") or case.get("validation_checks") or [],
        "leakage_controls": [
            "do not include expected_behavior in the prompt sent to the test agent",
            "do not include build-time review findings in the prompt sent to the test agent",
            "judge the response only after the agent has answered",
        ],
        "execution_policy": "plan_only",
    }


def build_forward_test_plan(
    request: dict[str, Any],
    child_skill_dir: Path,
    task_catalog: dict[str, Any],
    acceptance_suite: dict[str, Any],
    eval_splits: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    cases_by_id = {
        str(case.get("case_id")): case
        for case in acceptance_suite.get("cases", [])
        if case.get("case_id")
    }
    split_by_case_id = {
        str(case.get("source_case_id")): str(case.get("split") or "unsplit")
        for case in eval_splits.get("cases", [])
        if case.get("source_case_id")
    }

    selected_cases: list[tuple[dict[str, Any], str]] = []
    for case_id, case in sorted(cases_by_id.items()):
        kind = str(case.get("kind") or "")
        if kind in FORWARD_TEST_KINDS:
            selected_cases.append((case, split_by_case_id.get(case_id, "unsplit")))

    scenarios = [scenario_from_case(child_skill_dir, case, split) for case, split in selected_cases]
    task_types = {str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")}
    scenario_tasks = {str(scenario.get("task_type")) for scenario in scenarios}
    for task_type in sorted(task_types):
        if task_type not in scenario_tasks:
            add_finding(
                findings,
                "error",
                "task_without_forward_test",
                "Task_type has no forward-test scenario.",
                task_type,
            )

    if not scenarios:
        add_finding(
            findings,
            "error",
            "missing_forward_test_scenarios",
            "No plan-only forward-test scenarios were produced.",
        )

    if not any(scenario.get("kind") == "structured_refusal" for scenario in scenarios):
        add_finding(
            findings,
            "error",
            "missing_refusal_forward_test",
            "Forward-test plan must include at least one structured-refusal scenario.",
        )
    if not any(scenario.get("kind") in {"unsupported_task", "ambiguity_resolution"} for scenario in scenarios):
        add_finding(
            findings,
            "warning",
            "missing_global_boundary_forward_test",
            "Forward-test plan has no unsupported-task or ambiguity scenario.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "child_skill_path": public_child_skill_path(child_skill_dir),
        "scenario_count": len(scenarios),
        "scenario_kinds": sorted({str(scenario.get("kind")) for scenario in scenarios}),
        "scenarios": scenarios,
        "findings": findings,
        "policy": [
            "Forward tests are planned but not executed by the builder.",
            "Prompts sent to test agents must not include expected behavior or review conclusions.",
            "Execution-grounded behavior still requires explicit user approval and trace capture.",
        ],
    }


def validate_forward_test_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate a saved forward-test plan without executing test agents."""
    findings: list[dict[str, Any]] = []
    if plan.get("schema_version") != SCHEMA_VERSION:
        add_finding(
            findings,
            "error",
            "schema_version_mismatch",
            "Forward-test plan schema_version is missing or wrong.",
        )
    if not plan.get("plan_only"):
        add_finding(
            findings,
            "error",
            "forward_test_plan_not_plan_only",
            "Forward-test plan must be plan-only.",
        )
    scenarios = plan.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        add_finding(
            findings,
            "error",
            "missing_forward_test_scenarios",
            "Forward-test plan must contain scenarios.",
        )
        scenarios = []
    if plan.get("scenario_count") != len(scenarios):
        add_finding(
            findings,
            "error",
            "scenario_count_mismatch",
            "scenario_count must equal the number of scenarios.",
        )

    required_fields = {"scenario_id", "source_case_id", "kind", "agent_prompt", "judge_checks", "leakage_controls"}
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id") or "unknown")
        for field in sorted(required_fields):
            if field not in scenario:
                add_finding(
                    findings,
                    "error",
                    "scenario_missing_required_field",
                    "Forward-test scenario is missing a required field.",
                    scenario_id,
                )
        prompt = str(scenario.get("agent_prompt") or "")
        if "expected_behavior" in prompt or "review finding" in prompt.lower() or "final_score" in prompt:
            add_finding(
                findings,
                "error",
                "prompt_leaks_judging_context",
                "Agent prompt appears to leak expected behavior or review context.",
                scenario_id,
            )
        if scenario.get("execution_policy") != "plan_only":
            add_finding(
                findings,
                "error",
                "scenario_not_plan_only",
                "Forward-test scenario must be plan-only.",
                scenario_id,
            )
        if "expected_behavior" not in scenario:
            add_finding(
                findings,
                "error",
                "scenario_missing_expected_behavior",
                "Expected behavior must be available to the judge but kept out of the agent prompt.",
                scenario_id,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "scenario_count": len(scenarios),
        "scenario_kinds": sorted({str(scenario.get("kind")) for scenario in scenarios}),
        "findings": findings,
        "policy": [
            "This validator checks saved forward-test plans without executing agents.",
            "Agent prompts must not leak expected behavior or review context.",
            "Expected behavior is allowed only as judge-side metadata.",
        ],
    }
