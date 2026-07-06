"""Plan tutorial replay jobs and audit supplied replay results."""

from __future__ import annotations

from typing import Any

from common import as_list, canonical_task_type, now_utc, slugify
from constants import EXECUTION_SUCCESS_STATUSES, SCHEMA_VERSION


REQUIRED_SUCCESS_RESULT_FIELDS = [
    "replay_id",
    "task_type",
    "status",
    "trace_ref",
    "environment",
    "inputs",
    "outputs",
    "validation_checks",
    "package_versions",
]
REQUIRED_FAILURE_RESULT_FIELDS = [
    "replay_id",
    "task_type",
    "status",
    "failure_reason",
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
    value: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        item["task_type"] = task_type
    if value:
        item["value"] = value
    findings.append(item)


def task_boundary(execution_plan: dict[str, Any], task_type: str) -> dict[str, Any]:
    for task in execution_plan.get("tasks", []):
        if task.get("task_type") == task_type:
            return task
    return {}


def replay_job(
    replay: dict[str, Any],
    execution_plan: dict[str, Any],
    environment_install_plan: dict[str, Any],
) -> dict[str, Any]:
    task_type = str(replay.get("task_type") or "")
    boundary = task_boundary(execution_plan, task_type)
    replay_sources = replay.get("tutorial_replay_sources", [])
    blocked_reasons = []
    if replay.get("status") != "planned":
        blocked_reasons.append("no_replay_source")
    if execution_plan.get("missing_environment_fields"):
        blocked_reasons.append("missing_execution_environment")
    if environment_install_plan.get("status") == "fail":
        blocked_reasons.append("environment_install_plan_failed")
    return {
        "job_id": f"replay-job:{slugify(task_type)}",
        "replay_id": replay.get("replay_id"),
        "task_type": task_type,
        "status": "blocked" if blocked_reasons else "ready",
        "blocked_reasons": blocked_reasons,
        "plan_only": True,
        "requires_user_approval": True,
        "environment": execution_plan.get("environment", {}),
        "install_strategy": environment_install_plan.get("install_strategy"),
        "tutorial_sources": [
            {
                "tutorial_id": item.get("tutorial_id"),
                "source_evidence_id": item.get("source_evidence_id"),
                "source_path": item.get("source_path"),
                "step_count": item.get("step_count", 0),
            }
            for item in replay_sources
        ],
        "preflight_checks": boundary.get("preflight_checks", replay.get("preflight_checks", [])),
        "success_criteria": boundary.get("success_criteria", replay.get("success_criteria", [])),
        "trace_capture_contract": {
            "required_success_fields": REQUIRED_SUCCESS_RESULT_FIELDS,
            "required_failure_fields": REQUIRED_FAILURE_RESULT_FIELDS,
            "accepted_success_statuses": sorted(EXECUTION_SUCCESS_STATUSES),
            "must_record_command_or_notebook": True,
            "must_use_script_or_notebook_for_remote_multiline": True,
            "must_record_stdout_or_log_summary": True,
            "must_record_failure_reason_for_failed_replay": True,
            "remote_command_transport": {
                "preferred": "upload a standalone script or notebook and record its path/hash",
                "avoid": "inline multi-line shell or Python payloads in the command field",
                "result_fields": ["script", "script_path", "script_sha256", "notebook", "command"],
            },
        },
    }


def result_status(result: dict[str, Any]) -> str:
    return str(result.get("status") or "").lower()


def result_is_success(result: dict[str, Any]) -> bool:
    return result_status(result) in EXECUTION_SUCCESS_STATUSES


def command_or_notebook_present(result: dict[str, Any]) -> bool:
    return bool(result.get("command") or result.get("notebook") or result.get("script") or result.get("script_path"))


def has_remote_script_carrier(result: dict[str, Any]) -> bool:
    return bool(result.get("script") or result.get("script_path") or result.get("notebook"))


def command_looks_inline_multiline(result: dict[str, Any]) -> bool:
    command = str(result.get("command") or "")
    return "\n" in command or "python -" in command or "bash -" in command or "cat <<" in command


def missing_result_fields(result: dict[str, Any], remote_execution: bool = False) -> list[str]:
    fields = REQUIRED_SUCCESS_RESULT_FIELDS if result_is_success(result) else REQUIRED_FAILURE_RESULT_FIELDS
    missing = [field for field in fields if not result.get(field)]
    if result_is_success(result) and not command_or_notebook_present(result):
        missing.append("command_or_notebook")
    if result_is_success(result) and remote_execution and not has_remote_script_carrier(result):
        missing.append("script_or_notebook_for_remote_execution")
    return missing


def result_record(index: int, result: Any, jobs_by_replay: dict[str, dict[str, Any]], remote_execution: bool) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "result_index": index,
            "status": "invalid",
            "replay_id": None,
            "task_type": None,
            "success": False,
            "missing_fields": ["result_object"],
            "known_replay": False,
            "known_task_type": False,
            "trace_ref": None,
        }
    replay_id = str(result.get("replay_id") or "")
    task_type = canonical_task_type(str(result.get("task_type") or ""), "task")
    job = jobs_by_replay.get(replay_id, {})
    return {
        "result_index": index,
        "status": result_status(result) or "missing",
        "replay_id": replay_id,
        "task_type": task_type,
        "success": result_is_success(result),
        "missing_fields": missing_result_fields(result, remote_execution),
        "known_replay": bool(job),
        "known_task_type": task_type == canonical_task_type(str(job.get("task_type") or ""), "task") if job else False,
        "trace_ref": result.get("trace_ref"),
        "remote_execution": remote_execution,
        "has_script_carrier": has_remote_script_carrier(result),
        "command_looks_inline_multiline": command_looks_inline_multiline(result),
        "has_failure_reason": bool(result.get("failure_reason") or result.get("stderr") or result.get("error")),
        "has_troubleshooting_notes": bool(result.get("troubleshooting_notes") or result.get("remediation_suggestions")),
    }


def revision_actions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = []
    for record in records:
        task_type = record.get("task_type")
        if not task_type:
            continue
        if record.get("success") and not record.get("missing_fields") and record.get("known_replay") and record.get("known_task_type"):
            actions.append(
                {
                    "task_type": task_type,
                    "action": "allow_execution_verified_if_trace_validation_passes",
                    "trace_ref": record.get("trace_ref"),
                    "target_files": ["SKILL.md", "references/validation.md", "references/evidence.md"],
                }
            )
        elif not record.get("success"):
            actions.append(
                {
                    "task_type": task_type,
                    "action": "keep_source_grounded_and_update_troubleshooting",
                    "target_files": ["references/troubleshooting.md", "references/limitations-and-refusal.md"],
                }
            )
    return actions


def build_execution_replay_orchestrator(
    request: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    execution_plan: dict[str, Any],
    environment_install_plan: dict[str, Any],
) -> dict[str, Any]:
    """Return replay jobs and result-audit records without executing code."""
    environment = request.get("execution_environment") if isinstance(request.get("execution_environment"), dict) else {}
    remote_execution = environment.get("mode") == "remote" or bool(environment.get("remote_only"))
    jobs = [
        replay_job(replay, execution_plan, environment_install_plan)
        for replay in tutorial_reproduction_plan.get("replays", [])
    ]
    jobs_by_replay = {
        str(job.get("replay_id")): job
        for job in jobs
        if job.get("replay_id")
    }
    results = as_list(request.get("execution_replay_results"))
    records = [result_record(index, result, jobs_by_replay, remote_execution) for index, result in enumerate(results, start=1)]
    findings: list[dict[str, Any]] = []

    if tutorial_reproduction_plan.get("status") == "fail":
        add_finding(findings, "error", "tutorial_reproduction_plan_failed", "Replay orchestration requires a passing tutorial reproduction plan.")
    if execution_plan.get("plan_only") is not True:
        add_finding(findings, "error", "execution_plan_not_plan_only", "Replay orchestration must depend on a plan-only execution plan.")
    if environment_install_plan.get("plan_only") is not True:
        add_finding(findings, "error", "environment_install_plan_not_plan_only", "Replay orchestration must depend on a plan-only environment install plan.")

    ready_jobs = [job for job in jobs if job.get("status") == "ready"]
    blocked_jobs = [job for job in jobs if job.get("status") == "blocked"]
    if request.get("execution_grounded") and not ready_jobs:
        add_finding(findings, "error", "execution_grounded_without_ready_replay_jobs", "Execution grounding requires at least one ready replay job.")
    for job in blocked_jobs:
        severity = "error" if request.get("execution_grounded") else "warning"
        add_finding(
            findings,
            severity,
            "replay_job_blocked",
            "Replay job is blocked by missing sources or environment constraints.",
            task_type=str(job.get("task_type") or ""),
            value=", ".join(job.get("blocked_reasons", [])),
        )

    for record in records:
        index = int(record.get("result_index") or 0)
        task_type = str(record.get("task_type") or "")
        if record.get("status") == "invalid":
            add_finding(findings, "error", "invalid_replay_result_object", "Execution replay result must be a mapping.", value=str(index))
            continue
        if not record.get("known_replay"):
            add_finding(findings, "error", "replay_result_unknown_replay", "Execution replay result replay_id does not match a planned replay job.", task_type, str(index))
        if not record.get("known_task_type"):
            add_finding(findings, "error", "replay_result_task_mismatch", "Execution replay result task_type does not match its replay job.", task_type, str(index))
        if record.get("missing_fields"):
            severity = "error" if record.get("success") else "warning"
            add_finding(findings, severity, "replay_result_missing_fields", "Execution replay result is missing required fields.", task_type, ", ".join(record.get("missing_fields", [])))
        if record.get("success") and not record.get("trace_ref"):
            add_finding(findings, "error", "successful_replay_without_trace_ref", "Successful replay result requires trace_ref.", task_type)
        if record.get("success") and remote_execution and not record.get("has_script_carrier"):
            add_finding(findings, "error", "remote_replay_without_script_carrier", "Remote replay results must record a script_path, script, or notebook carrier.", task_type)
        if remote_execution and record.get("command_looks_inline_multiline"):
            add_finding(findings, "warning", "remote_replay_inline_multiline_command", "Remote replay command looks like an inline multi-line payload; prefer a standalone script or notebook.", task_type)
        if not record.get("success") and not record.get("has_failure_reason"):
            add_finding(findings, "warning", "failed_replay_without_failure_reason", "Failed replay result should include failure_reason, stderr, or error.", task_type)

    if request.get("execution_grounded") and results and not any(record.get("success") and not record.get("missing_fields") for record in records):
        add_finding(findings, "error", "execution_grounded_without_successful_replay_result", "Execution grounding supplied replay results but none are successful and complete.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "remote_execution": remote_execution,
        "plan_only": True,
        "job_count": len(jobs),
        "ready_job_count": len(ready_jobs),
        "blocked_job_count": len(blocked_jobs),
        "result_count": len(records),
        "successful_result_count": sum(1 for record in records if record.get("success") and not record.get("missing_fields")),
        "failed_result_count": sum(1 for record in records if not record.get("success") and record.get("status") != "invalid"),
        "jobs": jobs,
        "result_records": records,
        "skill_revision_actions": revision_actions(records),
        "findings": findings,
        "policy": [
            "Replay orchestration is plan-only; it never installs packages or runs tutorials.",
            "Remote replay evidence should use uploaded scripts or notebooks rather than inline multi-line command payloads.",
            "Successful replay results can support execution_verified only after execution_trace_validation also passes.",
            "Failed replay results update troubleshooting and refusal guidance but must not be marked verified.",
        ],
    }
