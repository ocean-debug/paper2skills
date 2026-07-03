"""Review-loop evolution summary for auditability."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def iteration_record(iteration: dict[str, Any]) -> dict[str, Any]:
    critic = next((state for state in iteration.get("states", []) if state.get("role") == "critic"), {})
    gate = next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})
    patch = iteration.get("patch", {})
    return {
        "iteration": iteration.get("iteration"),
        "score": iteration.get("score"),
        "total": iteration.get("total"),
        "score_ratio": iteration.get("score_ratio"),
        "blocking": iteration.get("blocking"),
        "passed": iteration.get("passed"),
        "severity_counts": critic.get("severity_counts", {}),
        "focus_counts": critic.get("focus_counts", {}),
        "patch_changed": patch.get("changed", False),
        "patch_summary": patch.get("patch_summary"),
        "patch_action_count": len(patch.get("actions", [])),
        "gate_reason": gate.get("reason"),
    }


def build_review_evolution(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    iterations = [iteration_record(item) for item in review_result.get("iterations", [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "iteration_count": len(iterations),
        "iterations": iterations,
        "final_score": review_result.get("final_score", {}),
        "final_finding_count": len(review_result.get("final_findings", [])),
        "policy": [
            "Review evolution summarizes the deterministic self-review loop.",
            "It does not replace review_iterations.jsonl, which keeps full per-iteration findings and patch actions.",
        ],
    }
