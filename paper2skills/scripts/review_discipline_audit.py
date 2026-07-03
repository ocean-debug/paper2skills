"""Audit review-loop discipline and stop-condition consistency."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_STATE_ROLES = {"draft_snapshot", "critic", "patch_plan", "gate"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        item["iteration"] = iteration
    findings.append(item)


def state_roles(iteration: dict[str, Any]) -> set[str]:
    return {str(state.get("role")) for state in iteration.get("states", []) if state.get("role")}


def gate_state(iteration: dict[str, Any]) -> dict[str, Any]:
    return next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})


def patch_changed(iteration: dict[str, Any]) -> bool:
    return bool((iteration.get("patch") or {}).get("changed"))


def patch_action_count(iteration: dict[str, Any]) -> int:
    return len((iteration.get("patch") or {}).get("actions", []))


def build_review_discipline_audit(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    iterations = review_result.get("iterations", [])
    max_iterations = int(request.get("review_iterations") or 3)
    stop_reason = str(review_result.get("stop_reason") or "")

    if not iterations:
        add_finding(
            findings,
            "error",
            "review_loop_has_no_iterations",
            "Review loop must record at least one iteration.",
        )

    previous_ratio: float | None = None
    previous_changed_iteration: int | None = None
    for expected_index, iteration in enumerate(iterations, start=1):
        iteration_index = int(iteration.get("iteration") or 0)
        if iteration_index != expected_index:
            add_finding(
                findings,
                "error",
                "non_consecutive_review_iteration",
                "Review iterations must be consecutive and start at one.",
                iteration_index,
            )

        missing_roles = REQUIRED_STATE_ROLES.difference(state_roles(iteration))
        if missing_roles:
            add_finding(
                findings,
                "error",
                "review_iteration_missing_state",
                "Review iteration is missing required draft, critic, patch-plan, or gate state.",
                iteration_index,
            )

        score = iteration.get("score")
        total = iteration.get("total")
        score_ratio = iteration.get("score_ratio")
        if not isinstance(score, (int, float)) or not isinstance(total, (int, float)) or total <= 0:
            add_finding(
                findings,
                "error",
                "invalid_review_score",
                "Review iteration must record numeric score and positive total.",
                iteration_index,
            )
        elif score < 0 or score > total:
            add_finding(
                findings,
                "error",
                "review_score_out_of_range",
                "Review score must be between zero and total.",
                iteration_index,
            )
        if not isinstance(score_ratio, (int, float)) or score_ratio < 0 or score_ratio > 1:
            add_finding(
                findings,
                "error",
                "review_score_ratio_out_of_range",
                "Review score_ratio must be between zero and one.",
                iteration_index,
            )

        gate = gate_state(iteration)
        passed = bool(iteration.get("passed"))
        changed = patch_changed(iteration)
        action_count = patch_action_count(iteration)
        gate_passed = bool(gate.get("passed"))
        gate_reason = str(gate.get("reason") or "")

        if passed and not gate_passed:
            add_finding(
                findings,
                "error",
                "passed_iteration_without_gate_pass",
                "A passed review iteration must have a passing gate state.",
                iteration_index,
            )
        if gate_passed and not passed:
            add_finding(
                findings,
                "error",
                "gate_pass_without_iteration_pass",
                "A passing gate state must match iteration passed=true.",
                iteration_index,
            )
        if passed and changed:
            add_finding(
                findings,
                "error",
                "passed_iteration_changed_patch",
                "A passed review iteration must not also apply patches.",
                iteration_index,
            )
        if changed and action_count == 0:
            add_finding(
                findings,
                "error",
                "changed_patch_without_actions",
                "A changed review patch must record at least one action.",
                iteration_index,
            )
        if changed and gate_reason != "patched_for_next_iteration":
            add_finding(
                findings,
                "error",
                "changed_patch_wrong_gate_reason",
                "A changed review patch must close the iteration with patched_for_next_iteration.",
                iteration_index,
            )
        if not changed and not passed and gate_reason != "no_deterministic_patch_available":
            add_finding(
                findings,
                "error",
                "stopped_iteration_wrong_gate_reason",
                "A failed iteration without a patch must record no_deterministic_patch_available.",
                iteration_index,
            )

        if previous_changed_iteration is not None and isinstance(score_ratio, (int, float)):
            if previous_ratio is not None and score_ratio < previous_ratio:
                add_finding(
                    findings,
                    "error",
                    "review_patch_score_regressed",
                    "Score ratio decreased after an applied review patch.",
                    iteration_index,
                )
            elif previous_ratio is not None and score_ratio == previous_ratio:
                add_finding(
                    findings,
                    "warning",
                    "review_patch_score_unchanged",
                    "Score ratio did not improve after an applied review patch.",
                    iteration_index,
                )
            previous_changed_iteration = None

        previous_ratio = float(score_ratio) if isinstance(score_ratio, (int, float)) else None
        if changed:
            previous_changed_iteration = iteration_index

    last = iterations[-1] if iterations else {}
    last_passed = bool(last.get("passed"))
    last_changed = patch_changed(last)
    iteration_count = len(iterations)
    if stop_reason == "rubric_gate_passed" and not last_passed:
        add_finding(
            findings,
            "error",
            "stop_reason_pass_without_passed_last_iteration",
            "rubric_gate_passed requires the last iteration to pass.",
        )
    if stop_reason == "no_deterministic_patch_available" and (last_passed or last_changed):
        add_finding(
            findings,
            "error",
            "stop_reason_no_patch_inconsistent",
            "no_deterministic_patch_available requires a failed last iteration with no patch.",
        )
    if stop_reason == "iteration_budget_exhausted" and iteration_count != max_iterations:
        add_finding(
            findings,
            "error",
            "iteration_budget_stop_count_mismatch",
            "iteration_budget_exhausted must use the configured iteration budget.",
        )
    if review_result.get("status") == "passed" and stop_reason == "iteration_budget_exhausted":
        add_finding(
            findings,
            "warning",
            "passed_after_final_patch_without_confirming_iteration",
            "Final artifacts pass, but the loop stopped by budget before recording a confirming pass iteration.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "configured_iteration_budget": max_iterations,
        "iteration_count": iteration_count,
        "findings": findings,
        "policy": [
            "Review discipline audits the self-review state machine; it does not execute package code.",
            "Each iteration must expose draft, critic, patch-plan, revision/gate semantics and consistent stop reasons.",
        ],
    }
