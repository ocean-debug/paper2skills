"""Judge supplied eval results against static eval splits."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PASS_STATUSES = {"pass", "passed", "ok", "success"}
FAIL_STATUSES = {"fail", "failed", "error"}


def case_index(eval_splits: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case in eval_splits.get("cases", []):
        case_id = str(case.get("case_id"))
        source_case_id = str(case.get("source_case_id"))
        cases[case_id] = case
        cases[source_case_id] = case
    return cases


def expected_fields_match(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    mismatches = []
    for field in ("expected_decision", "expected_task_type", "expected_reason_key"):
        expected = case.get(field)
        observed_field = field.replace("expected_", "observed_")
        observed = result.get(observed_field)
        if expected is not None and observed is not None and str(expected) != str(observed):
            mismatches.append(field)
    return mismatches


def judge_one(result: dict[str, Any], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    case_id = str(result.get("case_id") or result.get("source_case_id") or "")
    case = cases.get(case_id)
    if not case:
        return {
            "case_id": case_id,
            "status": "fail",
            "reason": "unknown_case_id",
            "message": "Eval result references a case_id not present in eval_splits.",
        }

    raw_status = str(result.get("status") or "").lower()
    if raw_status in PASS_STATUSES:
        mismatches = expected_fields_match(case, result)
        if mismatches:
            return {
                "case_id": case.get("case_id"),
                "source_case_id": case.get("source_case_id"),
                "split": case.get("split"),
                "kind": case.get("kind"),
                "task_type": case.get("task_type"),
                "status": "fail",
                "reason": "expected_field_mismatch",
                "mismatched_fields": mismatches,
            }
        return {
            "case_id": case.get("case_id"),
            "source_case_id": case.get("source_case_id"),
            "split": case.get("split"),
            "kind": case.get("kind"),
            "task_type": case.get("task_type"),
            "status": "pass",
            "reason": "reported_pass",
        }

    if raw_status in FAIL_STATUSES:
        return {
            "case_id": case.get("case_id"),
            "source_case_id": case.get("source_case_id"),
            "split": case.get("split"),
            "kind": case.get("kind"),
            "task_type": case.get("task_type"),
            "status": "fail",
            "reason": "reported_fail",
            "message": result.get("message") or result.get("error"),
        }

    mismatches = expected_fields_match(case, result)
    if mismatches:
        return {
            "case_id": case.get("case_id"),
            "source_case_id": case.get("source_case_id"),
            "split": case.get("split"),
            "kind": case.get("kind"),
            "task_type": case.get("task_type"),
            "status": "fail",
            "reason": "expected_field_mismatch",
            "mismatched_fields": mismatches,
        }

    observed_decision = result.get("observed_decision")
    if observed_decision is not None and case.get("expected_decision") is not None:
        return {
            "case_id": case.get("case_id"),
            "source_case_id": case.get("source_case_id"),
            "split": case.get("split"),
            "kind": case.get("kind"),
            "task_type": case.get("task_type"),
            "status": "pass",
            "reason": "observed_fields_match",
        }

    return {
        "case_id": case.get("case_id"),
        "source_case_id": case.get("source_case_id"),
        "split": case.get("split"),
        "kind": case.get("kind"),
        "task_type": case.get("task_type"),
        "status": "unknown",
        "reason": "insufficient_result_fields",
        "message": "Result must include status or observed expectation fields.",
    }


def build_eval_result_judge(request: dict[str, Any], eval_splits: dict[str, Any]) -> dict[str, Any]:
    results = list(request.get("eval_results", []))
    cases = case_index(eval_splits)
    records = [judge_one(result, cases) for result in results]
    findings = []
    for record in records:
        if record.get("status") == "fail":
            findings.append(
                {
                    "severity": "error",
                    "code": "eval_result_failed",
                    "case_id": record.get("case_id"),
                    "message": "Supplied eval result failed against the static eval split expectation.",
                }
            )
        if record.get("status") == "unknown":
            findings.append(
                {
                    "severity": "warning",
                    "code": "eval_result_unknown",
                    "case_id": record.get("case_id"),
                    "message": "Supplied eval result lacked enough fields to judge.",
                }
            )

    pass_count = sum(1 for record in records if record.get("status") == "pass")
    fail_count = sum(1 for record in records if record.get("status") == "fail")
    unknown_count = sum(1 for record in records if record.get("status") == "unknown")
    status = "not_run"
    if results:
        status = "fail" if fail_count else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": status,
        "result_count": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "records": records,
        "findings": findings,
        "policy": [
            "No eval result is assumed unless explicitly supplied in the build request.",
            "A static eval pass does not prove runtime package execution.",
            "Runtime verification still requires execution traces.",
        ],
    }
