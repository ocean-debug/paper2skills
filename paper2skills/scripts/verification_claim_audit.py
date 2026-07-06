"""Audit task_type verification claims against supplied trace validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import canonical_task_type, now_utc, read_text
from constants import SCHEMA_VERSION


ALLOWED_VERIFICATION_STATUSES = {"source_grounded", "execution_verified", "execution_failed"}


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


def valid_success_records(execution_trace_validation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for record in execution_trace_validation.get("records", []):
        if not record.get("success"):
            continue
        if record.get("missing_fields"):
            continue
        if not record.get("known_task_type"):
            continue
        task_type = canonical_task_type(str(record.get("task_type") or ""), "task")
        records.setdefault(task_type, []).append(record)
    return records


def failed_records(execution_trace_validation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for record in execution_trace_validation.get("records", []):
        if record.get("success"):
            continue
        task_type = canonical_task_type(str(record.get("task_type") or ""), "task")
        records.setdefault(task_type, []).append(record)
    return records


def rendered_text(child_skill_dir: Path) -> str:
    pieces = []
    for path in sorted(child_skill_dir.rglob("*.md")):
        if path.is_file():
            pieces.append(read_text(path))
    return "\n".join(pieces)


def build_verification_claim_audit(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    execution_trace_validation: dict[str, Any],
    execution_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    child_skill_dir: Path,
) -> dict[str, Any]:
    """Return a static audit for source_grounded and execution_verified claims."""
    findings: list[dict[str, Any]] = []
    valid_success_by_task = valid_success_records(execution_trace_validation)
    failed_by_task = failed_records(execution_trace_validation)
    text = rendered_text(child_skill_dir)
    task_rows: list[dict[str, Any]] = []

    for task in task_catalog.get("tasks", []):
        task_type = canonical_task_type(str(task.get("task_type") or ""), "task")
        status = str(task.get("verification_status") or "")
        trace_ref = task.get("trace_ref")
        valid_records = valid_success_by_task.get(task_type, [])
        failures = failed_by_task.get(task_type, [])
        valid_trace_count = sum(1 for record in valid_records if record.get("evidence_source") == "execution_trace")
        valid_replay_result_count = sum(1 for record in valid_records if record.get("evidence_source") == "execution_replay_result")
        row = {
            "task_type": task_type,
            "verification_status": status,
            "trace_ref": trace_ref,
            "valid_success_evidence_count": len(valid_records),
            "valid_success_trace_count": valid_trace_count,
            "valid_success_replay_result_count": valid_replay_result_count,
            "failed_trace_count": len(failures),
            "rendered_status_present": bool(status) and status in text,
        }
        task_rows.append(row)

        if status not in ALLOWED_VERIFICATION_STATUSES:
            add_finding(findings, "error", "unsupported_verification_status", "Task_type has an unsupported verification status.", task_type)
        if not request.get("execution_grounded") and status != "source_grounded":
            add_finding(findings, "error", "execution_claim_without_execution_grounding", "Execution claims are not allowed when execution_grounded is false.", task_type)
        if status == "execution_verified":
            if not trace_ref:
                add_finding(findings, "error", "verified_without_trace_ref", "execution_verified task_type requires trace_ref.", task_type)
            if not valid_records:
                add_finding(findings, "error", "verified_without_valid_success_trace", "execution_verified task_type requires a validated successful trace.", task_type)
            elif trace_ref and str(trace_ref) not in {str(record.get("trace_ref")) for record in valid_records}:
                add_finding(findings, "error", "verified_trace_ref_not_validated", "execution_verified trace_ref must match a validated successful trace.", task_type)
        if status == "execution_failed" and not failures:
            add_finding(findings, "error", "execution_failed_without_failed_trace", "execution_failed task_type requires a failed trace record.", task_type)
        if request.get("execution_grounded") and status == "source_grounded" and valid_records:
            add_finding(findings, "error", "valid_trace_not_promoted", "A validated successful trace exists but task_type remains source_grounded.", task_type)
        if not status or status not in text:
            add_finding(findings, "error", "verification_status_not_rendered", "Task verification status is not rendered in the child skill.", task_type)

    task_types = {canonical_task_type(str(task.get("task_type") or ""), "task") for task in task_catalog.get("tasks", [])}
    for task_type in sorted(set(valid_success_by_task) - task_types):
        add_finding(findings, "error", "valid_trace_without_task", "Validated trace task_type is missing from task_catalog.", task_type)

    if request.get("execution_grounded") and execution_trace_validation.get("valid_success_count", 0) == 0:
        add_finding(findings, "error", "execution_grounding_without_valid_success_trace", "execution_grounded requires at least one valid successful trace.")
    if execution_plan.get("plan_only") is not True:
        add_finding(findings, "error", "execution_plan_not_plan_only", "Execution plan must remain plan-only.")
    if tutorial_reproduction_plan.get("plan_only") is not True:
        add_finding(findings, "error", "tutorial_reproduction_plan_not_plan_only", "Tutorial reproduction plan must remain plan-only.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "task_count": len(task_rows),
        "trace_count": execution_trace_validation.get("trace_count", 0),
        "valid_success_count": execution_trace_validation.get("valid_success_count", 0),
        "execution_plan_status": execution_plan.get("status"),
        "tutorial_reproduction_plan_status": tutorial_reproduction_plan.get("status"),
        "tasks": task_rows,
        "findings": findings,
        "policy": [
            "source_grounded means evidence-backed but not execution verified.",
            "execution_verified requires a validated successful trace for the same task_type and trace_ref.",
            "Execution plans and tutorial reproduction plans are plan-only and must not themselves create verified claims.",
        ],
    }
