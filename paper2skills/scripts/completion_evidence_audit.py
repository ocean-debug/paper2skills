"""Audit whether a build has enough evidence to claim full completion."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def full_e2e_verified(e2e_acceptance: dict[str, Any]) -> bool:
    required_count = int(e2e_acceptance.get("required_scenario_count") or 0)
    passed_count = int(e2e_acceptance.get("passed_required_scenario_count") or 0)
    return (
        e2e_acceptance.get("status") == "pass"
        and e2e_acceptance.get("e2e_verdict") == "passed"
        and required_count > 0
        and passed_count == required_count
        and int(e2e_acceptance.get("result_count") or 0) > 0
    )


def rollout_verified(agent_rollout_result_judge: dict[str, Any]) -> bool:
    return (
        agent_rollout_result_judge.get("status") == "pass"
        and int(agent_rollout_result_judge.get("result_count") or 0) > 0
        and int(agent_rollout_result_judge.get("pass_count") or 0) > 0
        and int(agent_rollout_result_judge.get("fail_count") or 0) == 0
        and int(agent_rollout_result_judge.get("unknown_count") or 0) == 0
    )


def execution_verified_if_requested(
    request: dict[str, Any],
    execution_trace_validation: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
) -> bool:
    if not request.get("execution_grounded"):
        return True
    return (
        int(execution_trace_validation.get("valid_success_count") or 0) > 0
        or (
            execution_replay_orchestrator.get("status") == "pass"
            and int(execution_replay_orchestrator.get("successful_result_count") or 0) > 0
        )
    )


def build_completion_evidence_audit(
    request: dict[str, Any],
    requirement_coverage: dict[str, Any],
    agent_rollout_result_judge: dict[str, Any],
    e2e_acceptance: dict[str, Any],
    execution_trace_validation: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
) -> dict[str, Any]:
    """Return a non-executing audit of what completion claims are justified."""
    findings: list[dict[str, Any]] = []
    static_build_complete = requirement_coverage.get("status") == "pass"
    e2e_complete = full_e2e_verified(e2e_acceptance)
    rollout_complete = rollout_verified(agent_rollout_result_judge)
    execution_complete = execution_verified_if_requested(request, execution_trace_validation, execution_replay_orchestrator)
    successful_execution_evidence_count = int(execution_trace_validation.get("valid_success_count") or 0)
    successful_execution_trace_count = int(execution_trace_validation.get("valid_success_trace_count") or 0)
    successful_execution_replay_result_count = int(
        execution_trace_validation.get("valid_success_replay_result_count")
        or execution_replay_orchestrator.get("successful_result_count")
        or 0
    )

    missing_evidence: list[str] = []
    if not static_build_complete:
        missing_evidence.append("requirement_coverage_pass")
        add_finding(findings, "error", "static_build_requirements_incomplete", "Requirement coverage must pass before any completion claim.")
    if e2e_acceptance.get("status") == "fail":
        add_finding(findings, "error", "e2e_acceptance_failed", "Failed E2E acceptance audit blocks completion evidence claims.")
    if agent_rollout_result_judge.get("status") == "fail":
        add_finding(findings, "error", "agent_rollout_result_judge_failed", "Failed agent rollout result judge blocks completion evidence claims.")
    if execution_replay_orchestrator.get("status") == "fail":
        add_finding(findings, "error", "execution_replay_orchestrator_failed", "Failed execution replay orchestration blocks completion evidence claims.")
    if not e2e_complete:
        missing_evidence.append("passing_required_e2e_acceptance_results")
    if not rollout_complete:
        missing_evidence.append("passing_agent_rollout_results")
    if request.get("execution_grounded") and not execution_complete:
        missing_evidence.append("successful_execution_evidence")

    can_claim_full_goal_complete = static_build_complete and e2e_complete and rollout_complete and execution_complete
    if can_claim_full_goal_complete:
        claim_verdict = "full_goal_complete"
    elif static_build_complete:
        claim_verdict = "static_build_complete_unverified"
    else:
        claim_verdict = "incomplete"

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if any(finding["severity"] == "error" for finding in findings) else "pass",
        "claim_verdict": claim_verdict,
        "can_claim_static_build_complete": static_build_complete,
        "can_claim_full_goal_complete": can_claim_full_goal_complete,
        "requirement_coverage_status": requirement_coverage.get("status"),
        "agent_rollout_result_judge_status": agent_rollout_result_judge.get("status"),
        "agent_rollout_result_count": int(agent_rollout_result_judge.get("result_count") or 0),
        "e2e_acceptance_status": e2e_acceptance.get("status"),
        "e2e_verdict": e2e_acceptance.get("e2e_verdict"),
        "e2e_result_count": int(e2e_acceptance.get("result_count") or 0),
        "required_e2e_scenario_count": int(e2e_acceptance.get("required_scenario_count") or 0),
        "passed_required_e2e_scenario_count": int(e2e_acceptance.get("passed_required_scenario_count") or 0),
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "execution_trace_validation_status": execution_trace_validation.get("status"),
        "successful_execution_evidence_count": successful_execution_evidence_count,
        "successful_execution_trace_count": successful_execution_trace_count,
        "execution_replay_orchestrator_status": execution_replay_orchestrator.get("status"),
        "successful_execution_replay_result_count": successful_execution_replay_result_count,
        "missing_evidence": missing_evidence,
        "findings": findings,
        "policy": [
            "This audit never runs package code, launches agents, installs environments, or changes publish status.",
            "Static build completion is not the same as full real-package completion.",
            "Full completion requires passing required E2E results and passing independent agent rollout results.",
            "When execution grounding is requested, full completion also requires at least one successful execution evidence record.",
        ],
    }
