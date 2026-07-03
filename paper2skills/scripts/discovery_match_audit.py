"""Audit existing-skill match quality for Discovery decisions."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


STRONG_MATCH_LEVELS = {"exact_repo", "paper_reference", "package_task_overlap"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    match_path: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if match_path:
        item["match_path"] = match_path
    findings.append(item)


def task_types(task_catalog: dict[str, Any]) -> list[str]:
    return sorted(
        str(task.get("task_type"))
        for task in task_catalog.get("tasks", [])
        if task.get("task_type")
    )


def audited_match(match: dict[str, Any], requested_task_types: list[str]) -> dict[str, Any]:
    covered = set(match.get("covered_task_types", []))
    requested = set(requested_task_types)
    missing_standard_refs = [
        item.get("reference")
        for item in match.get("shape_findings", [])
        if item.get("code") == "missing_child_reference" and item.get("reference")
    ]
    return {
        "path": match.get("path"),
        "score": match.get("score", 0),
        "match_level": match.get("match_level", "unknown"),
        "confidence": match.get("confidence", 0.0),
        "task_coverage_ratio": match.get("task_coverage_ratio", 0.0),
        "covered_task_types": sorted(covered),
        "missing_task_types": sorted(requested.difference(covered)),
        "field_matches": match.get("field_matches", {}),
        "shape_status": match.get("shape_status", "unknown"),
        "missing_standard_references": missing_standard_refs,
        "files_scanned": match.get("files_scanned", []),
        "known_backend_count": len(match.get("known_backends", [])),
        "known_api_symbol_count": len(match.get("known_api_symbols", [])),
    }


def build_discovery_match_audit(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
    task_catalog: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic audit of match strength, ambiguity, and skill shape."""
    findings: list[dict[str, Any]] = []
    requested = task_types(task_catalog)
    decision = str(discovery_report.get("decision") or "")
    matches = list(discovery_report.get("matches", []))
    audited_matches = [audited_match(match, requested) for match in matches]
    best = audited_matches[0] if audited_matches else {}

    if decision not in {"reuse", "update", "create"}:
        add_finding(findings, "error", "invalid_discovery_decision", "Discovery decision must be reuse, update, or create.")

    if decision in {"reuse", "update"} and not matches:
        add_finding(findings, "error", "decision_requires_match", "Reuse or update requires at least one existing-skill match.")

    if best:
        if best.get("match_level") not in STRONG_MATCH_LEVELS and decision in {"reuse", "update"}:
            add_finding(
                findings,
                "error",
                "weak_match_for_reuse_or_update",
                "Reuse or update requires a repository, paper, or package plus task_type match.",
                str(best.get("path")),
            )
        if decision == "reuse" and best.get("task_coverage_ratio") != 1.0:
            add_finding(
                findings,
                "error",
                "reuse_without_full_task_coverage",
                "Reuse requires full requested task_type coverage.",
                str(best.get("path")),
            )
        if decision == "reuse" and best.get("shape_status") != "pass":
            add_finding(
                findings,
                "error",
                "reuse_with_invalid_child_shape",
                "Reuse requires the existing skill to satisfy the lightweight child-skill structure.",
                str(best.get("path")),
            )
        if decision == "update" and best.get("confidence", 0.0) < 0.35:
            add_finding(
                findings,
                "error",
                "update_match_below_confidence_floor",
                "Update requires enough identifier overlap to avoid modifying an unrelated skill.",
                str(best.get("path")),
            )
        if not best.get("files_scanned"):
            add_finding(
                findings,
                "error",
                "match_without_scanned_files",
                "Matched skill must report scanned standard files.",
                str(best.get("path")),
            )
    elif decision == "create":
        pass

    if decision == "create":
        strong_matches = [
            match for match in audited_matches
            if match.get("match_level") in STRONG_MATCH_LEVELS and match.get("confidence", 0.0) >= 0.35
        ]
        if strong_matches:
            add_finding(
                findings,
                "warning",
                "create_with_strong_related_match",
                "Create decision has a strong related existing-skill match; review whether update is more appropriate.",
                str(strong_matches[0].get("path")),
            )

    if len(audited_matches) > 1:
        top = audited_matches[0]
        runner_up = audited_matches[1]
        if (
            top.get("confidence", 0.0) >= 0.55
            and runner_up.get("confidence", 0.0) >= 0.55
            and abs(float(top.get("confidence", 0.0)) - float(runner_up.get("confidence", 0.0))) <= 0.1
        ):
            add_finding(
                findings,
                "warning",
                "ambiguous_high_confidence_matches",
                "Two existing skills have similar high-confidence matches; manual review is recommended before reuse or update.",
                str(top.get("path")),
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "decision": decision,
        "match_count": len(matches),
        "requested_or_inferred_task_types": requested,
        "required_standard_references": REQUIRED_CHILD_REFERENCES,
        "best_match": best,
        "matches": audited_matches,
        "findings": findings,
        "policy": [
            "Match audit verifies field-level identifiers instead of trusting a raw score.",
            "Reuse requires full task_type coverage and valid lightweight child-skill shape.",
            "Update requires a strong enough match to avoid touching unrelated skills.",
            "Create remains valid when no strong reusable or updatable child skill is found.",
        ],
    }
