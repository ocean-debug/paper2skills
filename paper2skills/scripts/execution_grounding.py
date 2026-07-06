"""Execution trace ingestion and verification status helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from common import append_jsonl, as_list, canonical_task_type, now_utc, write_text


def execution_evidence_records(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Return supplied trace-like execution evidence without validating it."""
    records: list[dict[str, Any]] = []
    for trace in as_list(request.get("execution_traces")):
        if isinstance(trace, dict):
            records.append({**trace, "evidence_source": "execution_trace"})
    for result in as_list(request.get("execution_replay_results")):
        if isinstance(result, dict):
            records.append({**result, "evidence_source": "execution_replay_result"})
    return records


def execution_status_for(task_type: str, request: dict[str, Any]) -> dict[str, Any]:
    if not request.get("execution_grounded"):
        return {
            "status": "source_grounded",
            "execution_grounded": False,
            "trace_ref": None,
            "summary": "Execution grounding was not requested for this build.",
        }
    matches = [
        evidence
        for evidence in execution_evidence_records(request)
        if canonical_task_type(str(evidence.get("task_type")), "task") == canonical_task_type(task_type, "task")
    ]
    if matches:
        trace = matches[0]
        return {
            "status": "source_grounded",
            "execution_grounded": True,
            "trace_ref": trace.get("trace_ref") or trace.get("evidence_ref"),
            "summary": "Execution evidence was supplied, but verification status is assigned only after trace validation.",
        }
    return {
        "status": "source_grounded",
        "execution_grounded": False,
        "trace_ref": None,
        "summary": "No successful execution trace or replay result was supplied for this task_type.",
    }


def apply_validated_execution_status(
    task_catalog: dict[str, Any],
    execution_trace_validation: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    catalog = deepcopy(task_catalog)
    records_by_task: dict[str, list[dict[str, Any]]] = {}
    valid_success_by_task: dict[str, list[dict[str, Any]]] = {}
    for record in execution_trace_validation.get("records", []):
        task_key = canonical_task_type(str(record.get("task_type") or ""), "task")
        records_by_task.setdefault(task_key, []).append(record)
        if record.get("success") and not record.get("missing_fields") and record.get("known_task_type"):
            valid_success_by_task.setdefault(task_key, []).append(record)
    for task in catalog.get("tasks", []):
        task_key = canonical_task_type(str(task.get("task_type") or ""), "task")
        valid_records = valid_success_by_task.get(task_key, [])
        task_records = records_by_task.get(task_key, [])
        if not request.get("execution_grounded"):
            task["verification_status"] = "source_grounded"
            task["execution_grounded"] = False
            task["trace_ref"] = None
            continue
        if valid_records:
            trace = valid_records[0]
            task["verification_status"] = "execution_verified"
            task["execution_grounded"] = True
            task["trace_ref"] = trace.get("trace_ref")
        elif any(not record.get("success") for record in task_records):
            trace = next((record for record in task_records if not record.get("success")), task_records[0])
            task["verification_status"] = "execution_failed"
            task["execution_grounded"] = True
            task["trace_ref"] = trace.get("trace_ref")
        else:
            task["verification_status"] = "source_grounded"
            task["execution_grounded"] = bool(task_records)
            task["trace_ref"] = None
    return catalog


def write_execution_trace_if_requested(request: dict[str, Any], out: Path) -> None:
    if not request.get("execution_grounded"):
        return
    trace_path = out / "execution_trace.jsonl"
    write_text(trace_path, "")
    supplied_records = execution_evidence_records(request)
    if supplied_records:
        for trace in supplied_records:
            append_jsonl(
                trace_path,
                {
                    "event": "supplied_execution_evidence",
                    "created_at": now_utc(),
                    **trace,
                },
            )
        return
    append_jsonl(
        trace_path,
        {
            "event": "execution_grounding_requested_without_trace",
            "status": "not_verified",
            "created_at": now_utc(),
        },
    )
