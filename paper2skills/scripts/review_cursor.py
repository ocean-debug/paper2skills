"""Review-loop cursor state for resumable paper2skills review loop iteration."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def gate_state(iteration: dict[str, Any]) -> dict[str, Any]:
    return next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})


def state_roles(iteration: dict[str, Any]) -> list[str]:
    return [str(state.get("role")) for state in iteration.get("states", []) if state.get("role")]


def iteration_cursor(iteration: dict[str, Any]) -> dict[str, Any]:
    gate = gate_state(iteration)
    patch = iteration.get("patch", {})
    return {
        "iteration": iteration.get("iteration"),
        "created_at": iteration.get("created_at"),
        "state_roles": state_roles(iteration),
        "score": iteration.get("score"),
        "total": iteration.get("total"),
        "score_ratio": iteration.get("score_ratio"),
        "blocking": bool(iteration.get("blocking")),
        "passed": bool(iteration.get("passed")),
        "patch_changed": bool(patch.get("changed")),
        "patch_action_count": len(patch.get("actions", [])),
        "gate_passed": bool(gate.get("passed")),
        "gate_reason": gate.get("reason"),
    }


def current_cursor(review_result: dict[str, Any]) -> dict[str, Any]:
    iterations = review_result.get("iterations", [])
    if not iterations:
        return {
            "phase": "not_started",
            "iteration": 0,
            "resumable": True,
            "reason": "review_loop_has_no_iterations",
        }
    last = iteration_cursor(iterations[-1])
    stop_reason = review_result.get("stop_reason")
    if review_result.get("status") == "passed":
        phase = "complete"
        resumable = False
    elif stop_reason == "awaiting_agent_proposal":
        phase = "awaiting_agent_review_loop"
        resumable = True
    elif stop_reason == "agent_proposal_rejected":
        phase = "agent_review_loop_rejected"
        resumable = True
    elif stop_reason == "awaiting_confirming_iteration":
        phase = "awaiting_confirming_iteration"
        resumable = True
    elif stop_reason == "iteration_budget_exhausted":
        phase = "iteration_budget_exhausted"
        resumable = True
    else:
        phase = "stopped"
        resumable = True
    return {
        "phase": phase,
        "iteration": last.get("iteration"),
        "resumable": resumable,
        "reason": stop_reason,
        "resume_action": "rerun_with_one_more_review_iteration_to_confirm_last_patch" if stop_reason == "awaiting_confirming_iteration" else None,
    }


def build_review_cursor(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    iterations = [iteration_cursor(item) for item in review_result.get("iterations", [])]
    cursor = current_cursor(review_result)
    required_roles = {"draft_snapshot", "record_score", "rollout_plan", "critic", "patch_plan", "gate"}
    incomplete_iterations = [
        item
        for item in iterations
        if not required_roles.issubset(set(item.get("state_roles", [])))
    ]
    status = "fail" if incomplete_iterations else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": status,
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "current": cursor,
        "iteration_count": len(iterations),
        "iterations": iterations,
        "required_state_roles": sorted(required_roles),
        "findings": [
            {
                "severity": "error",
                "code": "incomplete_review_iteration_state",
                "message": "A review iteration is missing one or more required cursor states.",
                "iteration": item.get("iteration"),
            }
            for item in incomplete_iterations
        ],
        "policy": [
            "Every review iteration must expose draft_snapshot, record_score, rollout_plan, critic, patch_plan, and gate states.",
            "The cursor records resumability and stop reason; it does not execute review or apply patches.",
            "awaiting_agent_review_loop means Codex must author a bounded proposal and rerun the build.",
        ],
    }
