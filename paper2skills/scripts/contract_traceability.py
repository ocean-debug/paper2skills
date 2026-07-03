"""Trace task contracts back to evidence references."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def observed_refs(items: list[dict[str, Any]]) -> list[str]:
    refs = []
    for item in items:
        ref = item.get("evidence_ref")
        if ref and ref not in refs:
            refs.append(str(ref))
        for ref in item.get("evidence_refs", []):
            if ref and ref not in refs:
                refs.append(str(ref))
    return refs


def record(
    task_type: str,
    kind: str,
    text: str,
    task_refs: list[str],
    direct_refs: list[str] | None = None,
    reason_key: str | None = None,
) -> dict[str, Any]:
    refs = list(direct_refs or []) or list(task_refs)
    return {
        "trace_id": f"contract:{slugify(task_type)}:{slugify(kind)}:{slugify(reason_key or text)[:80]}",
        "task_type": task_type,
        "kind": kind,
        "text": text,
        "reason_key": reason_key,
        "evidence_refs": refs,
        "grounding": "direct_observed" if direct_refs else "task_level_evidence",
    }


def task_records(task: dict[str, Any]) -> list[dict[str, Any]]:
    task_type = str(task.get("task_type"))
    task_refs = [str(ref) for ref in task.get("evidence_refs", [])]
    input_contract = task.get("input_contract") or {}
    output_contract = task.get("output_contract") or {}
    direct_input_refs = observed_refs(input_contract.get("evidence_observed", []))
    direct_output_refs = observed_refs(output_contract.get("evidence_observed", []))
    direct_validation_refs = observed_refs(output_contract.get("validation_observed", []))
    records = []
    for item in input_contract.get("required_from_user", []):
        records.append(record(task_type, "required_input", str(item), task_refs, direct_input_refs))
    for item in input_contract.get("must_confirm", []):
        records.append(record(task_type, "must_confirm", str(item), task_refs, direct_input_refs))
    for item in output_contract.get("expected_outputs", []):
        records.append(record(task_type, "expected_output", str(item), task_refs, direct_output_refs))
    for item in output_contract.get("minimum_validation", []):
        records.append(record(task_type, "validation_check", str(item), task_refs, direct_validation_refs or direct_output_refs))
    for boundary in task.get("refusal_boundaries", []):
        records.append(
            record(
                task_type,
                "refusal_boundary",
                str(boundary.get("when") or ""),
                task_refs,
                reason_key=str(boundary.get("reason_key") or ""),
            )
        )
    return records


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        finding["task_type"] = task_type
    findings.append(finding)


def build_contract_traceability(request: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    records = []
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        task_records_for_type = task_records(task)
        records.extend(task_records_for_type)
        if not task.get("evidence_refs"):
            add_finding(findings, "error", "task_missing_evidence_refs", "Task has no evidence references.", task_type)
        if not task_records_for_type:
            add_finding(findings, "error", "task_missing_contract_records", "Task has no traceable contract records.", task_type)
        if task_records_for_type and all(item.get("grounding") == "task_level_evidence" for item in task_records_for_type):
            add_finding(
                findings,
                "warning",
                "task_contracts_task_level_only",
                "Task contracts use task-level evidence refs but no direct parsed contract evidence.",
                task_type,
            )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "record_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Every generated input, output, validation, and refusal contract should point to evidence refs.",
            "task_level_evidence is acceptable for source-grounded drafts, but direct_observed evidence is stronger.",
        ],
    }
