"""Audit why the active child-skill candidate was selected."""

from __future__ import annotations

from typing import Any

from action_policy import REUSE_EXISTING, expected_publish_statuses, is_publish_status_acceptable
from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def active_version(candidate_registry: dict[str, Any]) -> dict[str, Any]:
    active_id = candidate_registry.get("active_version_id")
    for version in candidate_registry.get("versions", []):
        if version.get("version_id") == active_id:
            return version
    return {}


def candidate_by_id(draft_candidates: dict[str, Any], candidate_id: str | None) -> dict[str, Any]:
    for candidate in draft_candidates.get("candidates", []):
        if candidate.get("candidate_id") == candidate_id:
            return candidate
    return {}


def quality_signal(name: str, status: Any, expected: set[str]) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "expected": sorted(expected),
        "passed": str(status) in expected,
    }


def build_candidate_selection_audit(
    request: dict[str, Any],
    draft_candidates: dict[str, Any],
    candidate_registry: dict[str, Any],
    publish_gate: dict[str, Any],
    skill_update_plan: dict[str, Any],
    review_result: dict[str, Any],
    lint_report: dict[str, Any],
    draft_readiness: dict[str, Any],
    requirement_coverage: dict[str, Any],
) -> dict[str, Any]:
    """Record the active candidate selection rationale before promotion."""
    findings: list[dict[str, Any]] = []
    active = active_version(candidate_registry)
    selected_candidate = candidate_by_id(draft_candidates, active.get("candidate_id"))
    recommended_action = skill_update_plan.get("recommended_action")
    expected_publish = expected_publish_statuses(recommended_action)
    quality_signals = [
        quality_signal("publish_gate", publish_gate.get("status"), expected_publish),
        quality_signal("review", review_result.get("status"), {"passed"}),
        quality_signal("lint", lint_report.get("status"), {"pass"}),
        quality_signal("draft_readiness", draft_readiness.get("status"), {"pass"}),
        quality_signal("requirement_coverage", requirement_coverage.get("status"), {"pass"}),
        quality_signal("skill_update_plan", skill_update_plan.get("status"), {"pass"}),
    ]

    if draft_candidates.get("candidate_count", 0) != 1:
        add_finding(findings, "error", "unexpected_candidate_count", "Exactly one child-skill candidate is allowed per package.")
    if not candidate_registry.get("active_version_id"):
        add_finding(findings, "error", "missing_active_version_id", "Candidate registry must name the selected version.")
    if not active:
        add_finding(findings, "error", "active_version_not_found", "Selected version is not present in candidate registry.")
    if active and not selected_candidate:
        add_finding(findings, "error", "selected_candidate_not_found", "Selected version does not point to a draft candidate.")
    if selected_candidate and selected_candidate.get("one_package_one_skill") is not True:
        add_finding(findings, "error", "candidate_not_single_skill", "Selected candidate must preserve one package to one child skill.")
    if active.get("status") != publish_gate.get("status"):
        add_finding(findings, "error", "selected_status_mismatch", "Selected candidate status must mirror publish_gate status.")
    for signal in quality_signals:
        if not signal["passed"]:
            add_finding(
                findings,
                "error",
                "selection_quality_signal_failed",
                f"{signal['name']} status is {signal['status']}; expected one of {', '.join(signal['expected'])}.",
            )
    if recommended_action == REUSE_EXISTING and publish_gate.get("status") == "publishable":
        add_finding(findings, "error", "reuse_selection_publishable", "Reuse recommendations must not select a duplicate candidate for release.")
    if not is_publish_status_acceptable(recommended_action, publish_gate.get("status")):
        add_finding(findings, "error", "selected_publish_status_invalid", "Selected candidate status must match the action-specific publish status.")
    if active.get("blocking_findings"):
        add_finding(findings, "error", "selected_candidate_has_blockers", "Selected candidate retains blocking publish findings.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "selection_mode": "single_child_skill_candidate",
        "candidate_count": draft_candidates.get("candidate_count", 0),
        "selected_version_id": candidate_registry.get("active_version_id"),
        "selected_candidate_id": active.get("candidate_id"),
        "publish_gate_status": publish_gate.get("status"),
        "recommended_action": recommended_action,
        "quality_signals": quality_signals,
        "rationale": [
            "Select the active registry version only after source-grounded review, lint, draft readiness, requirement coverage, and action-specific publish gates pass.",
            "Keep capabilities inside the selected child skill as task_type entries rather than selecting separate skills.",
            "Treat reuse recommendations as evidence for maintaining an existing skill, not as permission to publish a duplicate candidate.",
        ],
        "findings": findings,
        "policy": [
            "Candidate selection is an audit record only; it does not copy, install, or mutate files.",
            "Selection must be explainable before candidate promotion and release packaging.",
            "Selection must preserve the one-package-one-child-skill invariant.",
        ],
    }
