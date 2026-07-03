"""Judge explicitly supplied agent rollout results against rollout expectations."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PASS_STATUSES = {"pass", "passed", "ok", "success"}
FAIL_STATUSES = {"fail", "failed", "error"}


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


def rollout_case_index(agent_rollout_harness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case in agent_rollout_harness.get("cases", []):
        for field in ("rollout_id", "scenario_id", "source_case_id"):
            value = case.get(field)
            if value:
                cases[str(value)] = case
    return cases


def expected_behavior(case: dict[str, Any]) -> dict[str, Any]:
    return (case.get("judge_metadata") or {}).get("expected_behavior") or {}


def observed_value(result: dict[str, Any], field: str) -> Any:
    return result.get(f"observed_{field}") if f"observed_{field}" in result else result.get(field)


def expected_fields_match(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    expected = expected_behavior(case)
    mismatches: list[str] = []
    for field in ("decision", "task_type", "reason_key"):
        expected_value = expected.get(field)
        observed = observed_value(result, field)
        if expected_value is not None and observed is not None and str(expected_value) != str(observed):
            mismatches.append(field)
    return mismatches


def required_checks_present(case: dict[str, Any], result: dict[str, Any]) -> bool:
    required = (case.get("judge_metadata") or {}).get("judge_checks") or []
    if not required:
        return True

    failed_checks = result.get("failed_judge_checks") or result.get("failed_checks") or []
    if failed_checks:
        return False

    satisfied_checks = (
        result.get("satisfied_judge_checks")
        or result.get("passed_judge_checks")
        or result.get("passed_checks")
        or result.get("observed_checks")
        or []
    )
    if not isinstance(satisfied_checks, list):
        return False

    satisfied_set = {str(item).strip().lower() for item in satisfied_checks}
    if "all" in satisfied_set:
        return True

    required_keys = [
        {str(index), f"check:{index}", f"judge_check:{index}"}
        for index, _ in enumerate(required, start=1)
    ]
    if required_keys and all(keys.intersection(satisfied_set) for keys in required_keys):
        return True

    observed_text = "\n".join(str(item).lower() for item in satisfied_checks)
    return all(str(check).lower() in observed_text for check in required)


def judge_one(result: dict[str, Any], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result_id = str(result.get("rollout_id") or result.get("scenario_id") or result.get("source_case_id") or "")
    case = cases.get(result_id)
    if not case:
        return {
            "result_id": result_id,
            "status": "fail",
            "reason": "unknown_rollout_case",
            "message": "Rollout result references no rollout, scenario, or source case id in the rollout harness.",
        }

    raw_status = str(result.get("status") or "").lower()
    mismatches = expected_fields_match(case, result)
    checks_ok = required_checks_present(case, result)
    base = {
        "rollout_id": case.get("rollout_id"),
        "scenario_id": case.get("scenario_id"),
        "source_case_id": case.get("source_case_id"),
        "split": case.get("split"),
        "kind": case.get("kind"),
        "task_type": case.get("task_type"),
    }

    if raw_status in FAIL_STATUSES:
        return {
            **base,
            "status": "fail",
            "reason": "reported_fail",
            "message": result.get("message") or result.get("error"),
        }
    if mismatches:
        return {
            **base,
            "status": "fail",
            "reason": "expected_field_mismatch",
            "mismatched_fields": mismatches,
        }
    if not checks_ok:
        return {
            **base,
            "status": "fail",
            "reason": "required_checks_not_observed",
            "message": "Result did not report all required judge checks.",
        }
    if raw_status in PASS_STATUSES:
        return {**base, "status": "pass", "reason": "reported_pass"}
    if any(observed_value(result, field) is not None for field in ("decision", "task_type", "reason_key")):
        return {**base, "status": "pass", "reason": "observed_fields_match"}
    return {
        **base,
        "status": "unknown",
        "reason": "insufficient_result_fields",
        "message": "Result must include status or observed expectation fields.",
    }


def build_agent_rollout_result_judge(
    request: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    eval_leakage_audit: dict[str, Any],
) -> dict[str, Any]:
    """Judge supplied rollout results without launching agents or package code."""
    results = list(request.get("agent_rollout_results", []))
    cases = rollout_case_index(agent_rollout_harness)
    records = [judge_one(result, cases) for result in results]
    findings: list[dict[str, Any]] = []

    if agent_rollout_harness.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_harness_failed", "Rollout result judging requires a passing rollout harness.")
    if eval_leakage_audit.get("status") != "pass":
        add_finding(findings, "error", "eval_leakage_audit_failed", "Rollout result judging requires passing eval leakage audit.")

    for record in records:
        if record.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "agent_rollout_result_failed",
                "Supplied rollout result failed against judge-side expectations.",
                str(record.get("rollout_id") or record.get("scenario_id") or record.get("result_id") or ""),
            )
        if record.get("status") == "unknown":
            add_finding(
                findings,
                "warning",
                "agent_rollout_result_unknown",
                "Supplied rollout result lacked enough fields to judge.",
                str(record.get("rollout_id") or record.get("scenario_id") or ""),
            )

    pass_count = sum(1 for record in records if record.get("status") == "pass")
    fail_count = sum(1 for record in records if record.get("status") == "fail")
    unknown_count = sum(1 for record in records if record.get("status") == "unknown")
    has_errors = any(finding["severity"] == "error" for finding in findings)
    status = "fail" if has_errors else "not_run"
    if results:
        status = "fail" if fail_count or unknown_count or has_errors else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": status,
        "agent_rollout_harness_status": agent_rollout_harness.get("status"),
        "eval_leakage_audit_status": eval_leakage_audit.get("status"),
        "result_count": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "records": records,
        "findings": findings,
        "policy": [
            "No agent rollout result is assumed unless explicitly supplied in the build request.",
            "Rollout result judging is static and never launches agents or package code.",
            "A passing rollout result does not imply package execution verification.",
            "Agent-visible prompt leakage must pass before supplied rollout results are accepted.",
            "Incomplete supplied rollout results fail closed instead of being treated as validation evidence.",
        ],
    }
