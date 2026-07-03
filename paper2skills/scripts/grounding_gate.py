"""Pre-publish grounding gate for task APIs and interfaces."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


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


def task_grounding_record(
    task: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    source_parse_report: dict[str, Any],
) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    api_refs = api_grounding.get("by_task_type", {}).get(task_type, {}).get("api_candidates", [])
    interface_refs = interface_grounding.get("by_task_type", {}).get(task_type, {}).get("interfaces", [])
    tutorial_refs = [
        tutorial.get("tutorial_id")
        for tutorial in tutorial_catalog.get("tutorials", [])
        if any(
            call for step in tutorial.get("steps", []) for call in step.get("api_calls", [])
        )
    ]
    parsed_counts = source_parse_report.get("counts", {})
    parseable_api_surface = (
        int(parsed_counts.get("python_file_count") or 0)
        + int(parsed_counts.get("notebook_file_count") or 0)
        + int(parsed_counts.get("api_candidate_count") or 0)
        + int(parsed_counts.get("interface_count") or 0)
    )
    status = "pass"
    reasons = []
    if not api_refs and not interface_refs:
        if parseable_api_surface > 0:
            status = "warning"
            reasons.append("parseable_source_without_task_api_or_interface")
        else:
            status = "warning"
            reasons.append("no_parseable_api_surface")
    if task.get("verification_status") == "execution_verified" and not (api_refs or interface_refs):
        status = "fail"
        reasons.append("verified_task_without_grounded_api_or_interface")
    return {
        "task_type": task_type,
        "status": status,
        "api_candidate_count": len(api_refs),
        "interface_count": len(interface_refs),
        "tutorial_with_api_hint_count": len(tutorial_refs),
        "evidence_ref_count": len(task.get("evidence_refs", [])),
        "verification_status": task.get("verification_status"),
        "reasons": reasons,
    }


def build_grounding_gate(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    source_parse_report: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    task_grounding = [
        task_grounding_record(task, api_grounding, interface_grounding, tutorial_catalog, source_parse_report)
        for task in task_catalog.get("tasks", [])
    ]
    for record in task_grounding:
        task_type = str(record.get("task_type"))
        if record.get("status") == "fail":
            add_finding(
                findings,
                "error",
                "verified_task_without_grounded_api_or_interface",
                "An execution_verified task_type must still point to grounded API or interface evidence.",
                task_type,
            )
        elif record.get("status") == "warning":
            add_finding(
                findings,
                "warning",
                "task_without_api_or_interface_grounding",
                "No API or interface candidate is linked to this task_type; keep generated guidance conservative.",
                task_type,
            )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    has_warnings = any(finding["severity"] == "warning" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "warning" if has_warnings else "pass",
        "task_grounding": task_grounding,
        "findings": findings,
        "policy": [
            "API and interface grounding are evidence hints, not execution proof.",
            "Generated child skills must not present ungrounded symbols as recommended APIs.",
            "Execution verification still requires successful execution evidence for the same task_type.",
        ],
    }
