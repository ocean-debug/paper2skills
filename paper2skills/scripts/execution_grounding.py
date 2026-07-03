"""Execution trace ingestion and verification status helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import append_jsonl, as_list, now_utc, slugify, write_text
from constants import EXECUTION_SUCCESS_STATUSES


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
        if slugify(str(evidence.get("task_type")), "task") == slugify(task_type, "task")
    ]
    successful = [
        evidence
        for evidence in matches
        if str(evidence.get("status", "")).lower() in EXECUTION_SUCCESS_STATUSES
    ]
    if successful:
        trace = successful[0]
        return {
            "status": "execution_verified",
            "execution_grounded": True,
            "trace_ref": trace.get("trace_ref") or trace.get("evidence_ref"),
            "summary": trace.get("summary"),
        }
    if matches:
        trace = matches[0]
        return {
            "status": "execution_failed",
            "execution_grounded": True,
            "trace_ref": trace.get("trace_ref") or trace.get("evidence_ref"),
            "summary": trace.get("summary") or trace.get("failure_reason") or trace.get("error"),
        }
    return {
        "status": "source_grounded",
        "execution_grounded": False,
        "trace_ref": None,
        "summary": "No successful execution trace or replay result was supplied for this task_type.",
    }


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
