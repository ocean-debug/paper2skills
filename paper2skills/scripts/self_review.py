"""SkillOpt-style self-review checks for generated drafts."""

from __future__ import annotations

from typing import Any

from common import as_list


ALLOWED_VERIFICATION_STATUS = {"source_grounded", "execution_verified", "execution_failed"}


def self_review(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    source_grounding: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if discovery_report.get("decision") == "reuse":
        findings.append(
            {
                "severity": "info",
                "check": "discovery",
                "message": "Existing skill may be reusable; avoid rebuilding unless user wants an update.",
            }
        )
    if not as_list(request.get("tutorial_links")) and not as_list(request.get("doc_links")):
        findings.append(
            {
                "severity": "warning",
                "check": "evidence",
                "message": "No tutorial or documentation link was provided; task boundaries may be weak.",
            }
        )
    if request.get("language_backend") != "python":
        findings.append(
            {
                "severity": "error",
                "check": "backend",
                "message": "The current backend is Python-first; non-Python backends must be represented as unsupported extension points.",
            }
        )
    tasks = task_catalog.get("tasks", [])
    task_types = [task.get("task_type") for task in tasks]
    duplicate_task_types = sorted({task_type for task_type in task_types if task_types.count(task_type) > 1 and task_type})
    if duplicate_task_types:
        findings.append(
            {
                "severity": "error",
                "check": "task_split",
                "message": "Duplicate task_type entries were produced.",
                "task_types": duplicate_task_types,
            }
        )
    route_task_types = {route.get("task_type") for route in router.get("routes", [])}
    for task in tasks:
        task_type = task.get("task_type")
        verification_status = task.get("verification_status")
        if verification_status == "source_grounded":
            findings.append(
                {
                    "severity": "info",
                    "check": "verification",
                    "task_type": task_type,
                    "message": "Task is source_grounded only; do not claim execution_verified.",
                }
            )
        if verification_status not in ALLOWED_VERIFICATION_STATUS:
            findings.append(
                {
                    "severity": "error",
                    "check": "verification",
                    "task_type": task_type,
                    "message": "Task has an unsupported verification_status.",
                }
            )
        if verification_status == "execution_verified" and not task.get("trace_ref"):
            findings.append(
                {
                    "severity": "error",
                    "check": "verification",
                    "task_type": task_type,
                    "message": "execution_verified task_type requires trace_ref.",
                }
            )
        if verification_status == "execution_failed":
            findings.append(
                {
                    "severity": "warning",
                    "check": "verification",
                    "task_type": task_type,
                    "message": "Execution trace failed; keep the task unverified and record troubleshooting guidance.",
                }
            )
        if not task.get("evidence_refs"):
            findings.append(
                {
                    "severity": "error",
                    "check": "evidence_refs",
                    "task_type": task_type,
                    "message": "Task is missing evidence references.",
                }
            )
        if task_type not in route_task_types:
            findings.append(
                {
                    "severity": "error",
                    "check": "routing",
                    "task_type": task_type,
                    "message": "Task has no route entry.",
                }
            )
        if not task.get("routing_cues"):
            findings.append(
                {
                    "severity": "warning",
                    "check": "routing",
                    "task_type": task_type,
                    "message": "Task has no routing cues.",
                }
            )
        input_contract = task.get("input_contract") or {}
        output_contract = task.get("output_contract") or {}
        if not input_contract.get("required_from_user"):
            findings.append(
                {
                    "severity": "error",
                    "check": "input_contract",
                    "task_type": task_type,
                    "message": "Task is missing required input contract fields.",
                }
            )
        if not output_contract.get("expected_outputs"):
            findings.append(
                {
                    "severity": "error",
                    "check": "output_contract",
                    "task_type": task_type,
                    "message": "Task is missing expected output contract fields.",
                }
            )
        if not output_contract.get("minimum_validation"):
            findings.append(
                {
                    "severity": "error",
                    "check": "validation",
                    "task_type": task_type,
                    "message": "Task is missing minimum validation rules.",
                }
            )
        if not task.get("refusal_boundaries"):
            findings.append(
                {
                    "severity": "error",
                    "check": "refusal",
                    "task_type": task_type,
                    "message": "Task is missing refusal boundaries.",
                }
            )
    if not router.get("routes"):
        findings.append(
            {
                "severity": "error",
                "check": "routing",
                "message": "No task_type routes were generated.",
            }
        )
    if not source_grounding.get("sources"):
        findings.append(
            {
                "severity": "error",
                "check": "sources",
                "message": "No sources were recorded.",
            }
        )
    return findings
