"""Run-level score report for review, quality, publish, and candidate gates."""

from __future__ import annotations

from typing import Any

from action_policy import expected_install_statuses, is_publish_status_acceptable
from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    artifact: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if artifact:
        item["artifact"] = artifact
    findings.append(item)


def blocking_scorecards(quality_report: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for card in quality_report.get("scorecards", []):
        if card.get("blocking_count", 0) > 0:
            cards.append(
                {
                    "name": card.get("name"),
                    "status": card.get("status"),
                    "blocking_count": card.get("blocking_count", 0),
                    "severity_counts": card.get("severity_counts", {}),
                }
            )
    return cards


def publish_blockers(publish_gate: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    blockers = [
        {
            "code": finding.get("code"),
            "message": finding.get("message"),
            "task_type": finding.get("task_type"),
        }
        for finding in publish_gate.get("findings", [])
        if finding.get("severity") == "error"
    ]
    return blockers[:limit]


def review_trajectory(review_evolution: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "iteration": item.get("iteration"),
            "score": item.get("score"),
            "total": item.get("total"),
            "score_ratio": item.get("score_ratio"),
            "blocking": item.get("blocking"),
            "passed": item.get("passed"),
            "patch_changed": item.get("patch_changed"),
            "gate_reason": item.get("gate_reason"),
        }
        for item in review_evolution.get("iterations", [])
    ]


def build_score_report(
    request: dict[str, Any],
    review_evolution: dict[str, Any],
    rubric_grounding_audit: dict[str, Any],
    quality_report: dict[str, Any],
    publish_gate: dict[str, Any],
    candidate_selection_audit: dict[str, Any],
    candidate_promotion_audit: dict[str, Any],
    final_candidate_audit: dict[str, Any],
    candidate_evolution_audit: dict[str, Any],
    codex_publish_adapter: dict[str, Any],
    install_readiness: dict[str, Any],
    publish_manifest_audit: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    final_score = review_evolution.get("final_score") or {}
    blockers = blocking_scorecards(quality_report)
    publish_errors = publish_blockers(publish_gate)
    action = publish_gate.get("recommended_action")

    if review_evolution.get("status") != "passed":
        add_finding(findings, "error", "review_not_passed", "Review evolution did not end in passed status.", "review_evolution")
    if rubric_grounding_audit.get("status") != "pass":
        add_finding(findings, "error", "rubric_grounding_not_passed", "Rubric grounding audit did not pass.", "rubric_grounding_audit")
    if quality_report.get("status") != "pass":
        add_finding(findings, "error", "quality_not_passed", "Quality report did not pass.", "quality_report")
    if not is_publish_status_acceptable(action, publish_gate.get("status")):
        add_finding(findings, "error", "publish_gate_status_invalid", "Publish gate does not match the release action.", "publish_gate")
    if candidate_selection_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_selection_not_passed", "Candidate selection audit did not pass.", "candidate_selection_audit")
    if candidate_promotion_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_promotion_not_passed", "Candidate promotion audit did not pass.", "candidate_promotion_audit")
    if final_candidate_audit.get("status") != "pass":
        add_finding(findings, "error", "final_candidate_not_passed", "Final candidate audit did not pass.", "final_candidate_audit")
    if candidate_evolution_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_evolution_not_passed", "Candidate evolution audit did not pass.", "candidate_evolution_audit")
    if codex_publish_adapter.get("status") != "pass":
        add_finding(findings, "error", "codex_publish_adapter_not_passed", "Codex publish adapter did not pass.", "codex_publish_adapter")
    if str(install_readiness.get("status")) not in expected_install_statuses(action):
        add_finding(findings, "error", "install_readiness_status_invalid", "Install readiness status does not match the release action.", "install_readiness")
    if publish_manifest_audit.get("status") != "pass":
        add_finding(findings, "error", "publish_manifest_audit_not_passed", "Publish manifest audit did not pass.", "publish_manifest_audit")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "final_score": final_score,
        "review_status": review_evolution.get("status"),
        "review_stop_reason": review_evolution.get("stop_reason"),
        "review_iteration_count": review_evolution.get("iteration_count", 0),
        "review_trajectory": review_trajectory(review_evolution),
        "rubric_grounding_status": rubric_grounding_audit.get("status"),
        "quality_status": quality_report.get("status"),
        "quality_blocking_scorecards": blockers,
        "task_blockers": quality_report.get("task_blockers", []),
        "publish_gate_status": publish_gate.get("status"),
        "recommended_action": action,
        "publish_blockers": publish_errors,
        "candidate_selection_status": candidate_selection_audit.get("status"),
        "candidate_promotion_status": candidate_promotion_audit.get("status"),
        "final_candidate_status": final_candidate_audit.get("status"),
        "candidate_evolution_status": candidate_evolution_audit.get("status"),
        "codex_publish_adapter_status": codex_publish_adapter.get("status"),
        "install_readiness_status": install_readiness.get("status"),
        "publish_manifest_audit_status": publish_manifest_audit.get("status"),
        "promoted_to_release": candidate_promotion_audit.get("promoted_to_release"),
        "finalized_for_release": final_candidate_audit.get("finalized_for_release"),
        "findings": findings,
        "policy": [
            "Score report is a run artifact only; it is not copied into the public child skill.",
            "A passing score report requires review, rubric grounding, quality, publish, candidate, adapter, install-readiness, and manifest gates to agree under the selected release action.",
            "This report summarizes blockers without replacing the detailed source artifacts.",
        ],
    }
