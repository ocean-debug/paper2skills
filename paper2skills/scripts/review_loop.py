"""SkillOpt-style deterministic review and patch loop."""

from __future__ import annotations

from typing import Any

from common import now_utc
from patch_planner import apply_review_patches
from review_rubric import score_artifacts
from self_review import self_review


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def focus_area(check: str) -> str:
    if check in {"source_grounding", "sources", "evidence", "evidence_refs", "api_grounding", "interface_grounding"}:
        return "evidence"
    if check in {"task_partition", "task_split", "task_routing", "routing"}:
        return "task_split_and_routing"
    if check in {"input_contracts", "output_contracts", "input_contract", "output_contract", "parameter_constraints"}:
        return "contracts"
    if check in {"refusal_boundaries", "refusal", "backend"}:
        return "refusal_boundaries"
    if check in {"validation_rules", "validation", "verification", "verification_labels"}:
        return "validation_and_verification"
    if check in {"environment_contract", "tutorial_catalog"}:
        return "supporting_context"
    return "other"


def critic_state(findings: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    focus_counts: dict[str, int] = {}
    for finding in findings:
        area = focus_area(str(finding.get("check") or finding.get("code") or "other"))
        focus_counts[area] = focus_counts.get(area, 0) + 1
    return {
        "role": "critic",
        "score": rubric["score"],
        "total": rubric["total"],
        "score_ratio": rubric["score_ratio"],
        "severity_counts": severity_counts(findings),
        "focus_counts": dict(sorted(focus_counts.items())),
        "item_results": rubric.get("item_results", []),
        "blocking_findings": [
            finding for finding in findings if finding.get("severity") == "error"
        ],
    }


def draft_snapshot(task_catalog: dict[str, Any], router: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "draft_snapshot",
        "task_types": [task.get("task_type") for task in task_catalog.get("tasks", [])],
        "route_count": len(router.get("routes", [])),
    }


def revision_state(patch: dict[str, Any]) -> dict[str, Any]:
    changed_artifacts = sorted({action.get("artifact") for action in patch.get("actions", []) if action.get("artifact")})
    return {
        "role": "revision",
        "changed": patch["changed"],
        "changed_artifacts": changed_artifacts,
        "summary": patch["patch_summary"],
    }


def has_blocking_findings(findings: list[dict[str, Any]]) -> bool:
    return any(finding.get("severity") == "error" for finding in findings)


def review_loop(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    source_grounding: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    evidence_cards: dict[str, Any],
    api_grounding: dict[str, Any] | None = None,
    interface_grounding: dict[str, Any] | None = None,
    environment_spec: dict[str, Any] | None = None,
    tutorial_catalog: dict[str, Any] | None = None,
    parameter_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    max_iterations = int(request.get("review_iterations") or 3)
    min_score_ratio = float(request.get("review_min_score_ratio") or 0.875)
    iterations = []
    current_catalog = task_catalog
    current_router = router
    stop_reason = "iteration_budget_exhausted"

    for iteration in range(1, max_iterations + 1):
        checklist = self_review(request, discovery_report, source_grounding, current_catalog, current_router)
        rubric = score_artifacts(
            source_grounding,
            current_catalog,
            current_router,
            evidence_cards,
            api_grounding,
            interface_grounding,
            environment_spec,
            tutorial_catalog,
            parameter_catalog,
        )
        findings = checklist + rubric["findings"]
        blocking = has_blocking_findings(findings)
        passed = not blocking and rubric["score_ratio"] >= min_score_ratio
        event = {
            "event": "review_iteration",
            "created_at": now_utc(),
            "iteration": iteration,
            "score": rubric["score"],
            "total": rubric["total"],
            "score_ratio": rubric["score_ratio"],
            "blocking": blocking,
            "passed": passed,
            "findings": findings,
            "states": [
                draft_snapshot(current_catalog, current_router),
                critic_state(findings, rubric),
            ],
        }
        if passed:
            event["patch"] = {"changed": False, "patch_summary": "Rubric gate passed."}
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch needed because the rubric gate passed.",
            }
            event["states"].append(event["patch_plan"])
            event["states"].append({"role": "gate", "passed": True, "reason": "rubric_gate_passed"})
            iterations.append(event)
            stop_reason = "rubric_gate_passed"
            break
        patch = apply_review_patches(current_catalog, current_router, findings)
        event["patch"] = {
            "changed": patch["changed"],
            "patch_summary": patch["patch_summary"],
            "finding_count": patch["finding_count"],
            "actions": patch.get("actions", []),
        }
        event["patch_plan"] = {
            "role": "patch_plan",
            "changed": patch["changed"],
            "actions": patch.get("actions", []),
            "summary": patch["patch_summary"],
        }
        event["states"].append(event["patch_plan"])
        event["states"].append(revision_state(patch))
        iterations.append(event)
        current_catalog = patch["task_catalog"]
        current_router = patch["router"]
        if not patch["changed"]:
            event["states"].append(
                {
                    "role": "gate",
                    "passed": False,
                    "reason": "no_deterministic_patch_available",
                }
            )
            stop_reason = "no_deterministic_patch_available"
            break
        event["states"].append({"role": "gate", "passed": False, "reason": "patched_for_next_iteration"})

    final_checklist = self_review(request, discovery_report, source_grounding, current_catalog, current_router)
    final_rubric = score_artifacts(
        source_grounding,
        current_catalog,
        current_router,
        evidence_cards,
        api_grounding,
        interface_grounding,
        environment_spec,
        tutorial_catalog,
        parameter_catalog,
    )
    final_findings = final_checklist + final_rubric["findings"]
    return {
        "task_catalog": current_catalog,
        "router": current_router,
        "iterations": iterations,
        "final_score": final_rubric,
        "final_findings": final_findings,
        "stop_reason": stop_reason,
        "status": "passed" if final_rubric["score_ratio"] >= min_score_ratio and not has_blocking_findings(final_findings) else "needs_review",
    }
