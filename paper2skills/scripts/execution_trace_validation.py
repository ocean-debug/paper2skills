"""Validate supplied execution traces without running package code."""

from __future__ import annotations

from typing import Any

from common import as_list, now_utc, slugify
from constants import EXECUTION_SUCCESS_STATUSES, SCHEMA_VERSION
from execution_grounding import execution_evidence_records


REQUIRED_SUCCESS_FIELDS = [
    "task_type",
    "status",
    "trace_ref",
    "environment",
    "inputs",
    "outputs",
    "validation_checks",
]


def trace_ref(trace: dict[str, Any]) -> str | None:
    return trace.get("trace_ref") or trace.get("evidence_ref")


def trace_command_or_notebook(trace: dict[str, Any]) -> bool:
    return bool(trace.get("command") or trace.get("notebook") or trace.get("script"))


def is_success(trace: dict[str, Any]) -> bool:
    return str(trace.get("status", "")).lower() in EXECUTION_SUCCESS_STATUSES


def missing_success_fields(trace: dict[str, Any]) -> list[str]:
    missing = []
    for field in REQUIRED_SUCCESS_FIELDS:
        if field == "trace_ref":
            if not trace_ref(trace):
                missing.append(field)
        elif not trace.get(field):
            missing.append(field)
    if not trace_command_or_notebook(trace):
        missing.append("command_or_notebook")
    if trace.get("evidence_source") == "execution_replay_result":
        if not (trace.get("replay_id") or trace.get("job_id")):
            missing.append("replay_id")
        if not trace.get("package_versions"):
            missing.append("package_versions")
    return missing


def trace_record(index: int, trace: Any, known_task_types: set[str]) -> dict[str, Any]:
    if not isinstance(trace, dict):
        return {
            "trace_index": index,
            "status": "invalid",
            "task_type": None,
            "trace_ref": None,
            "evidence_source": "invalid",
            "replay_id": None,
            "success": False,
            "missing_fields": ["trace_object"],
            "known_task_type": False,
        }
    task_type = slugify(str(trace.get("task_type") or ""), "task")
    success = is_success(trace)
    missing = missing_success_fields(trace) if success else []
    return {
        "trace_index": index,
        "status": str(trace.get("status") or "missing"),
        "task_type": task_type,
        "trace_ref": trace_ref(trace),
        "evidence_source": trace.get("evidence_source") or "execution_trace",
        "replay_id": trace.get("replay_id"),
        "success": success,
        "missing_fields": missing,
        "known_task_type": task_type in known_task_types,
        "has_error_text": bool(trace.get("error") or trace.get("stderr") or trace.get("failure_reason")),
    }


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    trace_index: int | None = None,
    task_type: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if trace_index is not None:
        finding["trace_index"] = trace_index
    if task_type:
        finding["task_type"] = task_type
    findings.append(finding)


def successful_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("success") and not record.get("missing_fields") and record.get("known_task_type")
    ]


def build_execution_trace_validation(request: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    traces = execution_evidence_records(request)
    known_task_types = {slugify(str(task.get("task_type")), "task") for task in task_catalog.get("tasks", [])}
    records = [trace_record(index, trace, known_task_types) for index, trace in enumerate(traces, start=1)]
    valid_successes = successful_records(records)
    findings: list[dict[str, Any]] = []

    if request.get("execution_grounded") and not traces:
        add_finding(
            findings,
            "error",
            "execution_grounding_without_traces",
            "execution_grounded was requested but no execution_traces or execution_replay_results were supplied.",
        )

    for record in records:
        index = int(record.get("trace_index") or 0)
        task_type = str(record.get("task_type") or "")
        if record.get("status") == "invalid":
            add_finding(findings, "error", "invalid_trace_object", "Execution trace must be a mapping.", index)
            continue
        if not record.get("known_task_type"):
            add_finding(findings, "error", "trace_unknown_task_type", "Execution trace task_type is not in task_catalog.", index, task_type)
        if record.get("success") and record.get("missing_fields"):
            add_finding(
                findings,
                "error",
                "successful_execution_evidence_missing_required_fields",
                "Successful execution evidence must include required provenance and validation fields.",
                index,
                task_type,
            )
        if not record.get("success") and not record.get("has_error_text"):
            add_finding(
                findings,
                "warning",
                "failed_execution_evidence_without_error_text",
                "Failed execution evidence should include error, stderr, or failure_reason.",
                index,
                task_type,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "trace_count": len(records),
        "execution_trace_count": len(as_list(request.get("execution_traces"))),
        "execution_replay_result_count": len(as_list(request.get("execution_replay_results"))),
        "valid_success_count": len(valid_successes),
        "valid_success_trace_count": sum(1 for record in valid_successes if record.get("evidence_source") == "execution_trace"),
        "valid_success_replay_result_count": sum(1 for record in valid_successes if record.get("evidence_source") == "execution_replay_result"),
        "records": records,
        "status": "fail" if has_errors else "pass",
        "findings": findings,
        "policy": [
            "This artifact validates supplied trace and replay-result metadata only; it does not execute tutorials.",
            "A successful trace must include task_type, status, trace_ref, environment, inputs, outputs, validation_checks, and command/notebook/script provenance.",
        ],
    }
