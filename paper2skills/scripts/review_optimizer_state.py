"""Optimizer-state summary for the paper2skills review loop."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gate_state(iteration: dict[str, Any]) -> dict[str, Any]:
    return next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})


def patch_actions(iteration: dict[str, Any]) -> list[dict[str, Any]]:
    return list((iteration.get("patch") or {}).get("actions", []))


def iteration_record(iteration: dict[str, Any]) -> dict[str, Any]:
    actions = patch_actions(iteration)
    gate = gate_state(iteration)
    state_roles = [str(state.get("role")) for state in iteration.get("states", []) if state.get("role")]
    state_hash = stable_hash(
        {
            "iteration": iteration.get("iteration"),
            "score": iteration.get("score"),
            "total": iteration.get("total"),
            "score_ratio": iteration.get("score_ratio"),
            "blocking": iteration.get("blocking"),
            "passed": iteration.get("passed"),
            "state_roles": state_roles,
            "patch_actions": actions,
            "gate": gate,
        }
    )
    return {
        "iteration": iteration.get("iteration"),
        "created_at": iteration.get("created_at"),
        "score": iteration.get("score"),
        "total": iteration.get("total"),
        "score_ratio": iteration.get("score_ratio"),
        "blocking": bool(iteration.get("blocking")),
        "passed": bool(iteration.get("passed")),
        "patch_changed": bool((iteration.get("patch") or {}).get("changed")),
        "patch_action_count": len(actions),
        "gate_passed": bool(gate.get("passed")),
        "gate_reason": gate.get("reason"),
        "state_roles": state_roles,
        "state_hash": state_hash,
    }


def rejected_edit_record(iteration: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "iteration": iteration.get("iteration"),
        "reason": reason,
        "score_ratio": iteration.get("score_ratio"),
        "patch_changed": bool((iteration.get("patch") or {}).get("changed")),
        "gate_reason": gate_state(iteration).get("reason"),
    }


def build_review_optimizer_state(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    """Record optimizer state without executing or mutating artifacts."""
    iterations = [iteration_record(item) for item in review_result.get("iterations", [])]
    final_score = review_result.get("final_score") or {}
    configured_budget = int(request.get("review_iterations") or 3)
    min_score_ratio = float(request.get("review_min_score_ratio") or 0.875)

    rejected_edits: list[dict[str, Any]] = []
    pending_patch_ratio: float | None = None
    pending_patch_iteration: int | None = None
    for raw_iteration, record in zip(review_result.get("iterations", []), iterations):
        ratio = record.get("score_ratio")
        if record["patch_changed"] and not record["patch_action_count"]:
            rejected_edits.append(rejected_edit_record(raw_iteration, "changed_patch_without_actions"))
        if pending_patch_ratio is not None and isinstance(ratio, (int, float)) and ratio <= pending_patch_ratio:
            rejected_edits.append(
                {
                    "iteration": record.get("iteration"),
                    "reason": "patch_did_not_strictly_improve_score",
                    "score_ratio": ratio,
                    "previous_patched_iteration": pending_patch_iteration,
                    "previous_score_ratio": pending_patch_ratio,
                    "patch_changed": record["patch_changed"],
                    "gate_reason": record.get("gate_reason"),
                }
            )
        pending_patch_ratio = float(ratio) if record["patch_changed"] and isinstance(ratio, (int, float)) else None
        pending_patch_iteration = int(record.get("iteration") or 0) if record["patch_changed"] else None

    cache_key = stable_hash(
        {
            "package_name": request.get("package_name"),
            "method_name": request.get("method_name") or request.get("package_name"),
            "target_agent": request.get("target_agent"),
            "review_iterations": configured_budget,
            "review_min_score_ratio": min_score_ratio,
            "iteration_hashes": [item["state_hash"] for item in iterations],
            "final_score": final_score,
            "score_cache_keys": sorted((review_result.get("score_cache") or {}).keys()),
            "rejected_buffer": review_result.get("rejected_buffer", []),
        }
    )
    final_ratio = final_score.get("score_ratio")
    findings = [
        {
            "severity": "error",
            "code": str(item.get("reason") or "rejected_review_edit"),
            "message": "A review patch was rejected by optimizer-state policy.",
            "iteration": item.get("iteration"),
        }
        for item in rejected_edits
    ]
    has_errors = bool(rejected_edits)
    if review_result.get("status") == "passed" and not isinstance(final_ratio, (int, float)):
        has_errors = True
        rejected = (
            {
                "iteration": None,
                "reason": "missing_final_score_ratio",
                "score_ratio": final_ratio,
                "patch_changed": False,
                "gate_reason": None,
            }
        )
        rejected_edits.append(rejected)
        findings.append(
            {
                "severity": "error",
                "code": "missing_final_score_ratio",
                "message": "Passed review result is missing a numeric final score ratio.",
                "iteration": None,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "configured_iteration_budget": configured_budget,
        "min_score_ratio": min_score_ratio,
        "strict_improvement_gate": True,
        "cache_key": cache_key,
        "score_cache_count": len(review_result.get("score_cache") or {}),
        "rejected_buffer_count": len(review_result.get("rejected_buffer") or []),
        "rejected_buffer": review_result.get("rejected_buffer", []),
        "iteration_count": len(iterations),
        "iterations": iterations,
        "rejected_edit_count": len(rejected_edits),
        "rejected_edits": rejected_edits,
        "final_score": final_score,
        "findings": findings,
        "policy": [
            "Optimizer state is append-only audit metadata; it does not execute package code.",
            "Each iteration receives a stable hash so repeated review states can be detected by downstream tooling.",
            "Patch actions are accepted only when the immediate strict-improvement gate confirms the candidate score increased.",
        ],
    }
