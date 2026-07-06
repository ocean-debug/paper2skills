"""Human-readable run scorecard renderer."""

from __future__ import annotations

from typing import Any

from common import md_table, now_utc
from constants import SCHEMA_VERSION


def _score_text(score: dict[str, Any]) -> str:
    passed = score.get("passed")
    total = score.get("total")
    ratio = score.get("score_ratio")
    if passed is None or total is None:
        return "unknown"
    if ratio is None:
        return f"{passed}/{total}"
    return f"{passed}/{total} ({ratio})"


def _status(value: Any) -> str:
    return str(value or "unknown")


def _finding_rows(findings: list[dict[str, Any]], limit: int = 12) -> list[list[str]]:
    rows: list[list[str]] = []
    for finding in findings[:limit]:
        rows.append(
            [
                _status(finding.get("severity")),
                _status(finding.get("artifact")),
                _status(finding.get("code")),
                _status(finding.get("message")),
            ]
        )
    return rows


def build_run_scorecard(
    request: dict[str, Any],
    score_report: dict[str, Any],
    quality_report: dict[str, Any],
    completion_audit: dict[str, Any],
    release_action_audit: dict[str, Any],
    publish_manifest: dict[str, Any],
    build_timeline: dict[str, Any],
    build_timeline_audit: dict[str, Any],
) -> dict[str, Any]:
    """Build metadata for the Markdown run scorecard."""
    blocking_scorecards = score_report.get("quality_blocking_scorecards", [])
    completion_findings = completion_audit.get("findings") or []
    release_findings = release_action_audit.get("findings") or []
    publish_findings = publish_manifest.get("findings") or []
    findings: list[dict[str, Any]] = []
    if not score_report:
        findings.append({"severity": "error", "code": "missing_score_report", "message": "score_report is missing."})
    if not completion_audit:
        findings.append({"severity": "error", "code": "missing_completion_audit", "message": "completion_audit is missing."})
    if not build_timeline:
        findings.append({"severity": "error", "code": "missing_build_timeline", "message": "build_timeline is missing."})
    if not build_timeline_audit:
        findings.append({"severity": "error", "code": "missing_build_timeline_audit", "message": "build_timeline_audit is missing."})

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if any(item.get("severity") == "error" for item in findings) else "pass",
        "markdown_path": "run_scorecard.md",
        "verdict_status": completion_audit.get("status"),
        "recommended_action": completion_audit.get("recommended_action") or score_report.get("recommended_action"),
        "discovery_decision": completion_audit.get("discovery_decision"),
        "publish_gate_status": completion_audit.get("publish_gate_status"),
        "quality_status": completion_audit.get("quality_status"),
        "protocol_compliance_audit_status": completion_audit.get("protocol_compliance_audit_status"),
        "score_report_status": completion_audit.get("score_report_status"),
        "release_action_audit_status": completion_audit.get("release_action_audit_status"),
        "install_readiness_status": completion_audit.get("install_readiness_status"),
        "publish_manifest_audit_status": completion_audit.get("publish_manifest_audit_status"),
        "build_timeline_audit_status": build_timeline_audit.get("status"),
        "final_score": score_report.get("final_score", {}),
        "review_iteration_count": score_report.get("review_iteration_count", 0),
        "review_stop_reason": score_report.get("review_stop_reason"),
        "promoted_to_release": score_report.get("promoted_to_release"),
        "blocking_summary": {
            "quality_blocking_scorecard_count": len(blocking_scorecards),
            "task_blocker_count": len(score_report.get("task_blockers") or []),
            "publish_blocker_count": len(score_report.get("publish_blockers") or []),
            "completion_finding_count": len(completion_findings),
            "release_action_finding_count": len(release_findings),
            "publish_manifest_finding_count": len(publish_findings),
        },
        "timeline_event_count": build_timeline.get("event_count", 0),
        "report_sections": [
            "verdict",
            "release_action",
            "review_and_quality",
            "blocking_findings",
            "timeline",
        ],
        "findings": findings,
        "policy": [
            "Run scorecard is a run artifact only; it is not copied into the public child skill.",
            "Run scorecard summarizes existing gates and does not override publish, release, or completion decisions.",
            "Detailed evidence remains in the source YAML, JSONL, SVG, and child-skill artifacts.",
        ],
    }


def render_run_scorecard_markdown(
    scorecard: dict[str, Any],
    score_report: dict[str, Any],
    quality_report: dict[str, Any],
    completion_audit: dict[str, Any],
    release_action_audit: dict[str, Any],
    build_timeline: dict[str, Any],
    build_timeline_audit: dict[str, Any],
) -> str:
    """Render a concise Markdown scorecard for human review."""
    title = scorecard.get("method_name") or scorecard.get("package_name") or "paper2skills Run"
    summary_rows = [
        ["Completion", _status(scorecard.get("verdict_status"))],
        ["Recommended action", _status(scorecard.get("recommended_action"))],
        ["Discovery decision", _status(scorecard.get("discovery_decision"))],
        ["Publish gate", _status(scorecard.get("publish_gate_status"))],
        ["Quality report", _status(scorecard.get("quality_status"))],
        ["Protocol compliance", _status(scorecard.get("protocol_compliance_audit_status"))],
        ["Release action audit", _status(scorecard.get("release_action_audit_status"))],
        ["Install readiness", _status(scorecard.get("install_readiness_status"))],
        ["Timeline audit", _status(scorecard.get("build_timeline_audit_status"))],
    ]
    review_rows = [
        ["Final review score", _score_text(scorecard.get("final_score", {}))],
        ["Review iterations", _status(scorecard.get("review_iteration_count"))],
        ["Review stop reason", _status(scorecard.get("review_stop_reason"))],
        ["Promoted to release", _status(scorecard.get("promoted_to_release"))],
    ]
    blocking_summary = scorecard.get("blocking_summary", {})
    blocker_rows = [
        ["Quality scorecards with blockers", _status(blocking_summary.get("quality_blocking_scorecard_count"))],
        ["Task blockers", _status(blocking_summary.get("task_blocker_count"))],
        ["Publish blockers", _status(blocking_summary.get("publish_blocker_count"))],
        ["Completion findings", _status(blocking_summary.get("completion_finding_count"))],
        ["Release action findings", _status(blocking_summary.get("release_action_finding_count"))],
        ["Timeline audit findings", _status(len(build_timeline_audit.get("findings") or []))],
    ]
    findings = (
        (completion_audit.get("findings") or [])
        + (release_action_audit.get("findings") or [])
        + (score_report.get("findings") or [])
        + (quality_report.get("task_blockers") or [])
    )
    normalized_findings: list[dict[str, Any]] = []
    for item in findings:
        if isinstance(item, dict):
            normalized_findings.append(item)
        else:
            normalized_findings.append(
                {
                    "severity": "error",
                    "artifact": "quality_report",
                    "code": "task_blocker",
                    "message": f"Task_type has incomplete quality contract: {item}",
                }
            )
    finding_rows = _finding_rows(normalized_findings)
    if not finding_rows:
        finding_rows = [["info", "all", "no_blockers", "No blocking findings were reported by the summarized gates."]]

    timeline_rows = []
    for event in build_timeline.get("events", [])[-10:]:
        timeline_rows.append(
            [
                _status(event.get("kind")),
                _status(event.get("name") or event.get("phase")),
                _status(event.get("status")),
                _status(event.get("message") or event.get("summary")),
            ]
        )
    if not timeline_rows:
        timeline_rows = [["unknown", "none", "unknown", "No timeline events were recorded."]]

    return "\n\n".join(
        [
            f"# {title} Run Scorecard",
            "This run artifact summarizes final gates for human review. It does not replace the detailed YAML, JSONL, SVG, or child-skill files.",
            "## Verdict",
            md_table(["Gate", "Status"], summary_rows),
            "## Review And Quality",
            md_table(["Metric", "Value"], review_rows),
            "## Blocking Summary",
            md_table(["Blocker", "Count"], blocker_rows),
            "## Blocking Findings",
            md_table(["Severity", "Artifact", "Code", "Message"], finding_rows),
            "## Recent Timeline",
            md_table(["Kind", "Name", "Status", "Message"], timeline_rows),
            "",
        ]
    )
