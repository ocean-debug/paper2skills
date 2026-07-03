"""Audit cross-artifact integrity of the review-loop trajectory."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    artifact: str | None = None,
    iteration: int | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if artifact:
        item["artifact"] = artifact
    if iteration is not None:
        item["iteration"] = iteration
    findings.append(item)


def iteration_ids(items: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for item in items:
        value = item.get("iteration")
        if isinstance(value, int):
            ids.add(value)
    return ids


def final_iteration(review_evolution: dict[str, Any]) -> dict[str, Any]:
    iterations = review_evolution.get("iterations", [])
    if not iterations:
        return {}
    return sorted(iterations, key=lambda item: int(item.get("iteration", 0)))[-1]


def score_tuple(score: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (score.get("score"), score.get("total"), score.get("score_ratio"))


def build_review_trajectory_audit(
    request: dict[str, Any],
    review_evolution: dict[str, Any],
    review_cursor: dict[str, Any],
    patch_application: dict[str, Any],
    review_optimizer_state: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
    rubric_grounding_audit: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    evolution_iterations = review_evolution.get("iterations", [])
    patch_records = patch_application.get("records", [])
    optimizer_iterations = review_optimizer_state.get("iterations", [])

    evolution_ids = iteration_ids(evolution_iterations)
    patch_ids = iteration_ids(patch_records)
    optimizer_ids = iteration_ids(optimizer_iterations)
    iteration_count = review_evolution.get("iteration_count", 0)

    if review_evolution.get("status") != "passed":
        add_finding(findings, "error", "review_evolution_not_passed", "Review evolution status must be passed.", "review_evolution")
    if review_cursor.get("status") != "pass":
        add_finding(findings, "error", "review_cursor_not_passed", "Review cursor status must pass.", "review_cursor")
    if patch_application.get("status") != "pass":
        add_finding(findings, "error", "patch_application_not_passed", "Patch application audit must pass.", "patch_application")
    if review_optimizer_state.get("status") != "pass":
        add_finding(findings, "error", "optimizer_state_not_passed", "Review optimizer state must pass.", "review_optimizer_state")
    if review_prompt_contracts.get("status") != "pass":
        add_finding(findings, "error", "prompt_contracts_not_passed", "Review prompt contracts must pass.", "review_prompt_contracts")
    if rubric_grounding_audit.get("status") != "pass":
        add_finding(findings, "error", "rubric_grounding_not_passed", "Rubric grounding audit must pass.", "rubric_grounding_audit")

    if iteration_count != len(evolution_iterations):
        add_finding(findings, "error", "evolution_iteration_count_mismatch", "review_evolution iteration_count must equal iterations length.", "review_evolution")
    if review_cursor.get("iteration_count") != iteration_count:
        add_finding(findings, "error", "cursor_iteration_count_mismatch", "review_cursor iteration_count must match review_evolution.", "review_cursor")
    if patch_application.get("iteration_count") != iteration_count:
        add_finding(findings, "error", "patch_iteration_count_mismatch", "patch_application iteration_count must match review_evolution.", "patch_application")
    if review_optimizer_state.get("iteration_count") != iteration_count:
        add_finding(findings, "error", "optimizer_iteration_count_mismatch", "review_optimizer_state iteration_count must match review_evolution.", "review_optimizer_state")
    if review_prompt_contracts.get("iteration_count") != iteration_count:
        add_finding(findings, "error", "prompt_contract_iteration_count_mismatch", "review_prompt_contracts iteration_count must match review_evolution.", "review_prompt_contracts")

    if evolution_ids != patch_ids:
        for missing in sorted(evolution_ids.difference(patch_ids)):
            add_finding(findings, "error", "patch_record_missing_iteration", "Patch application is missing an iteration record.", "patch_application", missing)
        for extra in sorted(patch_ids.difference(evolution_ids)):
            add_finding(findings, "error", "patch_record_extra_iteration", "Patch application contains an unknown iteration record.", "patch_application", extra)
    if evolution_ids != optimizer_ids:
        for missing in sorted(evolution_ids.difference(optimizer_ids)):
            add_finding(findings, "error", "optimizer_missing_iteration", "Review optimizer state is missing an iteration record.", "review_optimizer_state", missing)
        for extra in sorted(optimizer_ids.difference(evolution_ids)):
            add_finding(findings, "error", "optimizer_extra_iteration", "Review optimizer state contains an unknown iteration record.", "review_optimizer_state", extra)

    final = final_iteration(review_evolution)
    final_score = review_evolution.get("final_score", {})
    if final and score_tuple(final_score) != (final.get("score"), final.get("total"), final.get("score_ratio")):
        add_finding(findings, "error", "final_score_mismatch", "review_evolution final_score must match the final iteration score.", "review_evolution")
    optimizer_final = review_optimizer_state.get("final_score", {})
    if final_score and score_tuple(optimizer_final) != score_tuple(final_score):
        add_finding(findings, "error", "optimizer_final_score_mismatch", "review_optimizer_state final_score must match review_evolution.", "review_optimizer_state")

    cursor_current = review_cursor.get("current") or {}
    if cursor_current and cursor_current.get("iteration") not in evolution_ids:
        add_finding(findings, "error", "cursor_current_iteration_unknown", "Review cursor current iteration must exist in review_evolution.", "review_cursor")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "iteration_count": iteration_count,
        "evolution_iteration_ids": sorted(evolution_ids),
        "patch_iteration_ids": sorted(patch_ids),
        "optimizer_iteration_ids": sorted(optimizer_ids),
        "review_status": review_evolution.get("status"),
        "review_stop_reason": review_evolution.get("stop_reason"),
        "final_score": final_score,
        "findings": findings,
        "policy": [
            "Review trajectory artifacts must agree before publish.",
            "This audit checks trajectory integrity; it does not run review steps or apply patches.",
            "Detailed findings remain in the underlying review, prompt contract, patch, optimizer, and rubric artifacts.",
        ],
    }
