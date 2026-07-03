"""Audit eval and rollout artifacts for holdout and prompt leakage boundaries."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


FORBIDDEN_PROMPT_TOKENS = [
    "expected_behavior",
    "expected_decision",
    "expected_task_type",
    "expected_reason_key",
    "judge_metadata",
    "judge_checks",
    "final_score",
    "review finding",
]


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


def prompt_leak_tokens(prompt: str) -> list[str]:
    lowered = prompt.lower()
    return sorted(token for token in FORBIDDEN_PROMPT_TOKENS if token in lowered)


def expected_values(expected_behavior: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("decision", "task_type", "reason_key"):
        value = expected_behavior.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if len(text) >= 6:
            values.append(text)
    return values


def prompt_leaks_expected_values(prompt: str, expected_behavior: dict[str, Any]) -> list[str]:
    lowered = prompt.lower()
    return sorted(value for value in expected_values(expected_behavior) if value.lower() in lowered)


def duplicate_values(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def case_identity(case: dict[str, Any]) -> str:
    source_artifact = str(case.get("source_artifact") or "unknown")
    source_case_id = str(case.get("source_case_id") or case.get("case_id") or "unknown")
    return f"{source_artifact}:{source_case_id}"


def audit_eval_splits(eval_splits: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = eval_splits.get("cases", [])
    records: list[dict[str, Any]] = []
    if eval_splits.get("status") != "pass":
        add_finding(findings, "error", "eval_splits_not_passed", "Eval leakage audit requires passing eval splits.")

    case_ids = [str(case.get("case_id")) for case in cases if case.get("case_id")]
    for case_id in duplicate_values(case_ids):
        add_finding(findings, "error", "duplicate_eval_case_id", "Eval split case ids must be unique.", case_id)

    identities_by_split: dict[str, set[str]] = {}
    for case in cases:
        split = str(case.get("split") or "missing")
        identity = case_identity(case)
        identities_by_split.setdefault(split, set()).add(identity)
        records.append(
            {
                "record_type": "eval_case",
                "case_id": case.get("case_id"),
                "source_case_id": case.get("source_case_id"),
                "source_artifact": case.get("source_artifact"),
                "split": split,
                "kind": case.get("kind"),
                "task_type": case.get("task_type"),
            }
        )

    for left, right in (("train", "selection"), ("train", "test"), ("selection", "test")):
        overlap = sorted(identities_by_split.get(left, set()).intersection(identities_by_split.get(right, set())))
        for identity in overlap:
            add_finding(
                findings,
                "error",
                "eval_case_identity_crosses_splits",
                "The same source case identity appears in more than one eval split.",
                identity,
            )
    return records


def audit_forward_scenarios(forward_test_plan: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios = forward_test_plan.get("scenarios", [])
    records: list[dict[str, Any]] = []
    if forward_test_plan.get("status") != "pass":
        add_finding(findings, "error", "forward_test_plan_not_passed", "Eval leakage audit requires a passing forward-test plan.")
    if not forward_test_plan.get("plan_only"):
        add_finding(findings, "error", "forward_test_plan_not_plan_only", "Forward-test plan must remain plan-only.")

    scenario_ids = [str(scenario.get("scenario_id")) for scenario in scenarios if scenario.get("scenario_id")]
    for scenario_id in duplicate_values(scenario_ids):
        add_finding(findings, "error", "duplicate_forward_scenario_id", "Forward-test scenario ids must be unique.", scenario_id)

    holdout_count = 0
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id") or "unknown")
        split = str(scenario.get("split") or "missing")
        if split in {"selection", "test"}:
            holdout_count += 1
        prompt = str(scenario.get("agent_prompt") or "")
        token_leaks = prompt_leak_tokens(prompt)
        value_leaks = prompt_leaks_expected_values(prompt, scenario.get("expected_behavior") or {})
        if token_leaks:
            add_finding(findings, "error", "forward_prompt_leaks_judge_token", "Forward-test prompt contains judge-only metadata tokens.", scenario_id)
        if value_leaks:
            add_finding(findings, "error", "forward_prompt_leaks_expected_value", "Forward-test prompt contains judge-only expected values.", scenario_id)
        records.append(
            {
                "record_type": "forward_scenario",
                "scenario_id": scenario_id,
                "source_case_id": scenario.get("source_case_id"),
                "split": split,
                "kind": scenario.get("kind"),
                "task_type": scenario.get("task_type"),
                "prompt_token_leaks": token_leaks,
                "prompt_expected_value_leaks": value_leaks,
                "has_expected_behavior": bool(scenario.get("expected_behavior")),
                "has_leakage_controls": bool(scenario.get("leakage_controls")),
            }
        )
    if scenarios and holdout_count == 0:
        add_finding(findings, "error", "no_holdout_forward_scenarios", "Forward-test plan must include selection or test split scenarios.")
    return records


def audit_rollout_cases(agent_rollout_harness: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = agent_rollout_harness.get("cases", [])
    records: list[dict[str, Any]] = []
    if agent_rollout_harness.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_harness_not_passed", "Eval leakage audit requires a passing rollout harness.")
    if not agent_rollout_harness.get("plan_only"):
        add_finding(findings, "error", "agent_rollout_harness_not_plan_only", "Agent rollout harness must remain plan-only.")

    rollout_ids = [str(case.get("rollout_id")) for case in cases if case.get("rollout_id")]
    for rollout_id in duplicate_values(rollout_ids):
        add_finding(findings, "error", "duplicate_rollout_id", "Rollout ids must be unique.", rollout_id)

    for case in cases:
        scenario_id = str(case.get("scenario_id") or case.get("rollout_id") or "unknown")
        judge_metadata = case.get("judge_metadata") or {}
        expected_behavior = judge_metadata.get("expected_behavior") or {}
        prompt = str(case.get("agent_prompt") or "")
        token_leaks = prompt_leak_tokens(prompt)
        value_leaks = prompt_leaks_expected_values(prompt, expected_behavior)
        if token_leaks:
            add_finding(findings, "error", "rollout_prompt_leaks_judge_token", "Rollout prompt contains judge-only metadata tokens.", scenario_id)
        if value_leaks:
            add_finding(findings, "error", "rollout_prompt_leaks_expected_value", "Rollout prompt contains judge-only expected values.", scenario_id)
        if not judge_metadata.get("judge_checks"):
            add_finding(findings, "error", "rollout_missing_judge_checks", "Rollout case must keep judge checks in judge metadata.", scenario_id)
        records.append(
            {
                "record_type": "rollout_case",
                "rollout_id": case.get("rollout_id"),
                "scenario_id": scenario_id,
                "source_case_id": case.get("source_case_id"),
                "split": case.get("split"),
                "kind": case.get("kind"),
                "task_type": case.get("task_type"),
                "prompt_token_leaks": token_leaks,
                "prompt_expected_value_leaks": value_leaks,
                "has_judge_metadata": bool(judge_metadata),
                "has_leakage_controls": bool(case.get("leakage_controls")),
            }
        )
    return records


def build_eval_leakage_audit(
    request: dict[str, Any],
    eval_splits: dict[str, Any],
    forward_test_plan: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    eval_result_judge: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit of eval split isolation and agent prompt leakage."""
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    records.extend(audit_eval_splits(eval_splits, findings))
    records.extend(audit_forward_scenarios(forward_test_plan, findings))
    records.extend(audit_rollout_cases(agent_rollout_harness, findings))

    if eval_result_judge.get("status") == "fail":
        add_finding(findings, "error", "eval_result_judge_failed", "Supplied eval results failed static judging.")

    split_counts = eval_splits.get("split_counts") or {}
    missing_splits = sorted(split for split in ("train", "selection", "test") if split_counts.get(split, 0) == 0)
    for split in missing_splits:
        add_finding(findings, "error", "missing_eval_split", "Eval leakage audit requires non-empty train, selection, and test splits.", split)

    prompt_records = [record for record in records if record["record_type"] in {"forward_scenario", "rollout_case"}]
    leaked_prompt_count = sum(
        1
        for record in prompt_records
        if record.get("prompt_token_leaks") or record.get("prompt_expected_value_leaks")
    )
    holdout_forward_scenario_count = sum(
        1
        for record in records
        if record["record_type"] == "forward_scenario" and record.get("split") in {"selection", "test"}
    )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "eval_splits_status": eval_splits.get("status"),
        "forward_test_plan_status": forward_test_plan.get("status"),
        "agent_rollout_harness_status": agent_rollout_harness.get("status"),
        "eval_result_judge_status": eval_result_judge.get("status"),
        "split_counts": split_counts,
        "eval_case_count": len(eval_splits.get("cases", [])),
        "forward_scenario_count": len(forward_test_plan.get("scenarios", [])),
        "rollout_case_count": len(agent_rollout_harness.get("cases", [])),
        "prompt_record_count": len(prompt_records),
        "leaked_prompt_count": leaked_prompt_count,
        "holdout_forward_scenario_count": holdout_forward_scenario_count,
        "records": records,
        "findings": findings,
        "policy": [
            "Eval leakage audit is static and plan-only; it never launches agents or package code.",
            "Train, selection, and test split identities must remain disjoint.",
            "Agent-visible prompts must not contain judge-only metadata, expected behavior keys, expected values, or review context.",
            "Judge checks and expected behavior may exist only in judge-side metadata.",
        ],
    }
