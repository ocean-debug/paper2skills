"""Audit schemas and leakage boundaries for supplied external result evidence."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PASS_STATUSES = {"pass", "passed", "ok", "success"}
FAIL_STATUSES = {"fail", "failed", "error"}
KNOWN_STATUSES = PASS_STATUSES | FAIL_STATUSES | {"unknown", "not_run"}
FORBIDDEN_RESULT_FIELDS = {
    "expected_behavior",
    "expected_decision",
    "expected_task_type",
    "expected_reason_key",
    "judge_metadata",
    "judge_checks",
    "agent_prompt",
    "prompt",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    field: str | None = None,
    index: int | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if field:
        item["field"] = field
    if index is not None:
        item["index"] = index
    findings.append(item)


def as_result_list(request: dict[str, Any], field: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    value = request.get(field, [])
    if not isinstance(value, list):
        add_finding(findings, "error", "external_result_field_not_list", "External result field must be a list.", field)
        return []
    records: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            add_finding(findings, "error", "external_result_not_mapping", "Each external result must be a mapping.", field, index)
            continue
        records.append(item)
    return records


def raw_status(result: dict[str, Any]) -> str:
    return str(result.get("status") or "").strip().lower()


def has_any(result: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(result.get(field) not in {None, ""} for field in fields)


def audit_common_result(
    findings: list[dict[str, Any]],
    result: dict[str, Any],
    field: str,
    index: int,
) -> None:
    forbidden = sorted(FORBIDDEN_RESULT_FIELDS.intersection(result))
    if forbidden:
        add_finding(
            findings,
            "error",
            "external_result_contains_judge_or_prompt_fields",
            "External result evidence must not include expected values, judge metadata, or agent-visible prompts.",
            field,
            index,
        )

    status = raw_status(result)
    if status and status not in KNOWN_STATUSES:
        add_finding(
            findings,
            "error",
            "external_result_unknown_status",
            "External result status must be pass, fail, unknown, not_run, or a known synonym.",
            field,
            index,
        )

    failed_checks = result.get("failed_judge_checks") or result.get("failed_checks") or []
    if status in PASS_STATUSES and failed_checks:
        add_finding(
            findings,
            "error",
            "external_result_pass_with_failed_checks",
            "External result cannot report pass while also reporting failed checks.",
            field,
            index,
        )
    if status in FAIL_STATUSES and not has_any(result, ("message", "error", "reason")):
        add_finding(
            findings,
            "warning",
            "external_result_fail_without_reason",
            "Failed external results should include message, error, or reason.",
            field,
            index,
        )


def audit_eval_result(findings: list[dict[str, Any]], result: dict[str, Any], index: int) -> None:
    field = "eval_results"
    audit_common_result(findings, result, field, index)
    if not has_any(result, ("case_id", "source_case_id")):
        add_finding(
            findings,
            "error",
            "eval_result_missing_case_identity",
            "Eval result must reference case_id or source_case_id.",
            field,
            index,
        )
    if not raw_status(result) and not has_any(result, ("observed_decision", "observed_task_type", "observed_reason_key")):
        add_finding(
            findings,
            "error",
            "eval_result_missing_judgable_fields",
            "Eval result must include status or observed decision/task/reason fields.",
            field,
            index,
        )


def audit_rollout_result(findings: list[dict[str, Any]], result: dict[str, Any], index: int) -> None:
    field = "agent_rollout_results"
    audit_common_result(findings, result, field, index)
    if not has_any(result, ("rollout_id", "scenario_id", "source_case_id")):
        add_finding(
            findings,
            "error",
            "rollout_result_missing_case_identity",
            "Agent rollout result must reference rollout_id, scenario_id, or source_case_id.",
            field,
            index,
        )
    if not raw_status(result) and not has_any(result, ("observed_decision", "observed_task_type", "observed_reason_key")):
        add_finding(
            findings,
            "error",
            "rollout_result_missing_judgable_fields",
            "Agent rollout result must include status or observed decision/task/reason fields.",
            field,
            index,
        )
    for check_field in ("satisfied_judge_checks", "passed_judge_checks", "failed_judge_checks", "failed_checks"):
        if check_field in result and not isinstance(result.get(check_field), list):
            add_finding(
                findings,
                "error",
                "rollout_result_check_field_not_list",
                "Rollout judge-check fields must be lists.",
                field,
                index,
            )


def remote_environment_requested(request: dict[str, Any]) -> bool:
    environment = request.get("execution_environment") if isinstance(request.get("execution_environment"), dict) else {}
    return environment.get("mode") == "remote" or bool(environment.get("remote_only"))


def replay_has_script_carrier(result: dict[str, Any]) -> bool:
    return has_any(result, ("script", "script_path", "notebook"))


def replay_command_looks_inline_multiline(result: dict[str, Any]) -> bool:
    command = str(result.get("command") or "")
    return "\n" in command or "python -" in command or "bash -" in command or "cat <<" in command


def audit_replay_result(findings: list[dict[str, Any]], result: dict[str, Any], index: int, remote_execution: bool) -> None:
    field = "execution_replay_results"
    audit_common_result(findings, result, field, index)
    if not has_any(result, ("replay_id", "job_id")):
        add_finding(
            findings,
            "error",
            "replay_result_missing_replay_identity",
            "Execution replay result must reference replay_id or job_id.",
            field,
            index,
        )
    if not has_any(result, ("task_type",)):
        add_finding(
            findings,
            "error",
            "replay_result_missing_task_type",
            "Execution replay result must include task_type.",
            field,
            index,
        )
    if raw_status(result) in PASS_STATUSES and not has_any(result, ("trace_ref", "evidence_ref")):
        add_finding(
            findings,
            "error",
            "successful_replay_result_missing_trace_ref",
            "Successful execution replay result must include trace_ref or evidence_ref.",
            field,
            index,
        )
    if raw_status(result) in PASS_STATUSES and remote_execution and not replay_has_script_carrier(result):
        add_finding(
            findings,
            "error",
            "remote_replay_result_missing_script_carrier",
            "Successful remote replay result must include script, script_path, or notebook.",
            field,
            index,
        )
    if remote_execution and replay_command_looks_inline_multiline(result):
        add_finding(
            findings,
            "warning",
            "remote_replay_result_inline_multiline_command",
            "Remote replay command looks like an inline multi-line payload; record a standalone script or notebook instead.",
            field,
            index,
        )


def audit_e2e_result(findings: list[dict[str, Any]], result: dict[str, Any], index: int) -> None:
    field = "e2e_acceptance_results"
    audit_common_result(findings, result, field, index)
    if not has_any(result, ("scenario_id",)):
        add_finding(
            findings,
            "error",
            "e2e_result_missing_scenario_identity",
            "E2E acceptance result must reference scenario_id.",
            field,
            index,
        )
    if raw_status(result) in PASS_STATUSES:
        if not isinstance(result.get("artifact_refs"), list) or not result.get("artifact_refs"):
            add_finding(
                findings,
                "error",
                "successful_e2e_result_missing_artifact_refs",
                "Successful E2E acceptance result must include non-empty artifact_refs.",
                field,
                index,
            )
        if not isinstance(result.get("completed_checks"), list) or not result.get("completed_checks"):
            add_finding(
                findings,
                "error",
                "successful_e2e_result_missing_completed_checks",
                "Successful E2E acceptance result must include non-empty completed_checks.",
                field,
                index,
            )


def audit_smoke_result(findings: list[dict[str, Any]], result: dict[str, Any], index: int) -> None:
    field = "smoke_test_results"
    audit_common_result(findings, result, field, index)
    if not has_any(result, ("scenario_id",)):
        add_finding(
            findings,
            "error",
            "smoke_result_missing_scenario_identity",
            "Smoke test result must reference scenario_id.",
            field,
            index,
        )
    if raw_status(result) in PASS_STATUSES:
        if not isinstance(result.get("artifact_refs"), list) or not result.get("artifact_refs"):
            add_finding(
                findings,
                "error",
                "successful_smoke_result_missing_artifact_refs",
                "Successful smoke test result must include non-empty artifact_refs.",
                field,
                index,
            )
        if not isinstance(result.get("completed_checks"), list) or not result.get("completed_checks"):
            add_finding(
                findings,
                "error",
                "successful_smoke_result_missing_completed_checks",
                "Successful smoke test result must include non-empty completed_checks.",
                field,
                index,
            )


def build_external_result_contracts(request: dict[str, Any]) -> dict[str, Any]:
    """Return a static contract audit for external eval, rollout, replay, and E2E results."""
    findings: list[dict[str, Any]] = []
    eval_results = as_result_list(request, "eval_results", findings)
    rollout_results = as_result_list(request, "agent_rollout_results", findings)
    smoke_results = as_result_list(request, "smoke_test_results", findings)
    replay_results = as_result_list(request, "execution_replay_results", findings)
    e2e_results = as_result_list(request, "e2e_acceptance_results", findings)
    remote_execution = remote_environment_requested(request)

    for index, result in enumerate(eval_results):
        audit_eval_result(findings, result, index)
    for index, result in enumerate(rollout_results):
        audit_rollout_result(findings, result, index)
    for index, result in enumerate(smoke_results):
        audit_smoke_result(findings, result, index)
    for index, result in enumerate(replay_results):
        audit_replay_result(findings, result, index, remote_execution)
    for index, result in enumerate(e2e_results):
        audit_e2e_result(findings, result, index)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "eval_result_count": len(eval_results),
        "agent_rollout_result_count": len(rollout_results),
        "smoke_test_result_count": len(smoke_results),
        "execution_replay_result_count": len(replay_results),
        "e2e_acceptance_result_count": len(e2e_results),
        "supplied_result_count": len(eval_results) + len(rollout_results) + len(smoke_results) + len(replay_results) + len(e2e_results),
        "remote_execution": remote_execution,
        "forbidden_result_fields": sorted(FORBIDDEN_RESULT_FIELDS),
        "findings": findings,
        "policy": [
            "External results are optional supplied evidence; the builder never fabricates them.",
            "External result evidence must contain observed outcomes, not judge-only expected values or prompts.",
            "External result contract auditing is static and does not launch agents or execute package code.",
        ],
    }
