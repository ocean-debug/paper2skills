"""Audit Discovery decisions for reuse, update, or create."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def best_match(report: dict[str, Any]) -> dict[str, Any]:
    matches = report.get("matches", [])
    return matches[0] if matches else {}


def coverage_ratio(match: dict[str, Any], task_types: list[str]) -> float:
    if not task_types:
        return 0.0
    covered = set(match.get("covered_task_types", []))
    return len(covered.intersection(task_types)) / len(set(task_types))


def audited_match(match: dict[str, Any], task_types: list[str]) -> dict[str, Any]:
    return {
        "path": match.get("path"),
        "score": match.get("score", 0),
        "match_level": match.get("match_level"),
        "confidence": match.get("confidence", 0.0),
        "score_components": match.get("score_components", []),
        "covered_task_types": match.get("covered_task_types", []),
        "missing_task_types": sorted(set(task_types).difference(set(match.get("covered_task_types", [])))),
        "known_task_type_count": len(match.get("known_task_types", [])),
        "matched_api_count": len(match.get("matched_api_names", [])),
        "matched_paper_ref_count": len(match.get("matched_paper_refs", [])),
        "coverage_ratio": coverage_ratio(match, task_types),
        "shape_status": match.get("shape_status"),
    }


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def build_discovery_audit(
    request: dict[str, Any],
    discovery_preflight: dict[str, Any],
    discovery_report: dict[str, Any],
    task_catalog: dict[str, Any],
) -> dict[str, Any]:
    task_types = [str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")]
    findings: list[dict[str, Any]] = []
    final_decision = discovery_report.get("decision")
    final_best = best_match(discovery_report)
    preflight_best = best_match(discovery_preflight)

    if final_decision not in {"reuse", "update", "create"}:
        add_finding(findings, "error", "invalid_discovery_decision", "Final Discovery decision is not reuse, update, or create.")
    if final_decision in {"reuse", "update"} and not discovery_report.get("matches"):
        add_finding(findings, "error", "decision_without_match", "Final Discovery decision requires at least one matching skill.")
    if final_decision == "reuse" and final_best.get("missing_task_types"):
        add_finding(findings, "error", "reuse_with_missing_task_types", "Reuse decision is invalid because the best match misses task_type entries.")
    if final_decision == "reuse" and final_best.get("shape_status") not in {None, "pass"}:
        add_finding(findings, "error", "reuse_with_invalid_child_shape", "Reuse decision is invalid because the best match does not satisfy the lightweight child-skill structure.")
    if final_decision == "create" and discovery_report.get("matches"):
        add_finding(findings, "warning", "create_with_related_matches", "Create decision has related matches; review whether update is more appropriate.")
    if not discovery_report.get("checked_existing_skill_dirs"):
        add_finding(findings, "warning", "no_existing_skill_dirs_checked", "No existing skill directories were provided for Discovery.")
    if discovery_preflight.get("decision") == "reuse" and final_decision == "create":
        add_finding(findings, "warning", "preflight_reuse_final_create", "Preflight suggested reuse but final Discovery suggests create.")

    recommendations = []
    if final_decision == "reuse":
        recommendations.append("Reuse the best matching existing child skill instead of publishing a duplicate.")
    elif final_decision == "update":
        recommendations.append("Update the best matching existing child skill to cover missing task_type entries.")
    else:
        recommendations.append("Create a new child skill because no covering existing skill was found.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "preflight_decision": discovery_preflight.get("decision"),
        "final_decision": final_decision,
        "checked_existing_skill_dirs": discovery_report.get("checked_existing_skill_dirs", []),
        "requested_or_inferred_task_types": task_types,
        "preflight_best_match": audited_match(preflight_best, discovery_preflight.get("requested_or_inferred_task_types", [])) if preflight_best else {},
        "final_best_match": audited_match(final_best, task_types) if final_best else {},
        "match_count": len(discovery_report.get("matches", [])),
        "findings": findings,
        "recommendations": recommendations,
        "policy": [
            "Discovery audit explains reuse, update, or create decisions before publishing.",
            "A reuse decision is valid only when the best match covers every inferred task_type.",
        ],
    }
