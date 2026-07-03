"""Build stable eval splits from static routing and acceptance cases."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


TRAIN_KINDS = {
    "task_type_routing",
    "input_output_contract",
    "eval_contract_acceptance",
    "select_task_type",
}
SELECTION_KINDS = {
    "structured_refusal",
    "contract_traceability",
    "eval_structured_refusal",
    "unsupported_task",
    "ask_on_ambiguity",
}
TEST_KINDS = {
    "ambiguity_resolution",
    "execution_boundary",
    "eval_api_grounding_review",
}


def split_for_kind(kind: str) -> str:
    if kind in SELECTION_KINDS:
        return "selection"
    if kind in TEST_KINDS:
        return "test"
    return "train"


def normalize_case(source_artifact: str, case: dict[str, Any]) -> dict[str, Any]:
    raw_case_id = str(case.get("case_id") or case.get("scenario_id") or f"{source_artifact}:{case.get('kind')}")
    kind = str(case.get("kind") or "unknown")
    task_type = case.get("task_type") or case.get("expected_task_type")
    return {
        "case_id": f"{source_artifact}:{slugify(raw_case_id)}",
        "source_case_id": raw_case_id,
        "source_artifact": source_artifact,
        "split": split_for_kind(kind),
        "kind": kind,
        "task_type": task_type,
        "expected_decision": case.get("expected_decision"),
        "expected_task_type": case.get("expected_task_type"),
        "expected_reason_key": case.get("expected_reason_key"),
        "required_checks": case.get("required_checks") or case.get("must_check") or [],
        "validation_checks": case.get("validation_checks", []),
        "evidence_refs": case.get("evidence_refs", []),
        "execution_required": bool(case.get("execution_required", False)),
    }


def build_eval_splits(
    request: dict[str, Any],
    eval_plan: dict[str, Any],
    acceptance_suite: dict[str, Any],
    routing_fixture: dict[str, Any],
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in acceptance_suite.get("cases", []):
        cases.append(normalize_case("acceptance_suite", case))
    for case in routing_fixture.get("cases", []):
        cases.append(normalize_case("routing_fixture", case))
    for scenario in eval_plan.get("scenarios", []):
        cases.append(normalize_case("eval_plan", scenario))

    seen: set[str] = set()
    unique_cases = []
    for case in cases:
        case_id = str(case.get("case_id"))
        if case_id in seen:
            continue
        seen.add(case_id)
        unique_cases.append(case)

    split_counts = {"train": 0, "selection": 0, "test": 0}
    task_types_by_split: dict[str, set[str]] = {"train": set(), "selection": set(), "test": set()}
    for case in unique_cases:
        split = str(case.get("split"))
        split_counts[split] = split_counts.get(split, 0) + 1
        if case.get("task_type"):
            task_types_by_split.setdefault(split, set()).add(str(case["task_type"]))

    task_types = sorted({str(case["task_type"]) for case in unique_cases if case.get("task_type")})
    findings = []
    for split in ("train", "selection", "test"):
        if split_counts.get(split, 0) == 0:
            findings.append(
                {
                    "severity": "error",
                    "code": "empty_eval_split",
                    "split": split,
                    "message": "Eval split has no cases.",
                }
            )
    for task_type in task_types:
        covered_splits = sorted(
            split for split, split_task_types in task_types_by_split.items() if task_type in split_task_types
        )
        if "train" not in covered_splits:
            findings.append(
                {
                    "severity": "warning",
                    "code": "task_missing_train_case",
                    "task_type": task_type,
                    "message": "Task_type has no train split case.",
                }
            )
        if not {"selection", "test"}.intersection(covered_splits):
            findings.append(
                {
                    "severity": "warning",
                    "code": "task_missing_holdout_case",
                    "task_type": task_type,
                    "message": "Task_type has no selection or test split case.",
                }
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "case_count": len(unique_cases),
        "split_counts": split_counts,
        "task_type_count": len(task_types),
        "task_types": task_types,
        "cases": unique_cases,
        "findings": findings,
        "policy": [
            "Eval splits are static and do not execute package code.",
            "Train cases support draft/debug review; selection and test cases support later holdout validation.",
            "Case records avoid long source excerpts and keep only expectations needed for judging.",
        ],
    }
