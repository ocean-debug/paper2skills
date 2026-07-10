"""Audit build timeline integrity against phase, review, and gate artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_GATE_EVENTS = {"gate:publish", "gate:quality"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    event_id: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if event_id:
        finding["event_id"] = event_id
    findings.append(finding)


def event_ids(events: list[dict[str, Any]]) -> list[str]:
    return [str(event.get("event_id") or "") for event in events]


def build_timeline_audit(
    request: dict[str, Any],
    build_timeline: dict[str, Any],
    phase_state: dict[str, Any],
    review_result: dict[str, Any],
    publish_gate: dict[str, Any],
    quality_report: dict[str, Any],
) -> dict[str, Any]:
    """Return a static integrity audit for build_timeline.yaml."""
    findings: list[dict[str, Any]] = []
    events = build_timeline.get("events", [])
    ids = event_ids(events)
    nonempty_ids = [event_id for event_id in ids if event_id]
    duplicate_ids = sorted({event_id for event_id in nonempty_ids if nonempty_ids.count(event_id) > 1})
    event_kinds = sorted({str(event.get("kind") or "unknown") for event in events})
    phase_events = [event for event in events if event.get("kind") == "phase"]
    review_events = [event for event in events if event.get("kind") == "review_iteration"]
    gate_ids = {str(event.get("event_id") or "") for event in events if event.get("kind") == "gate"}

    if build_timeline.get("event_count") != len(events):
        add_finding(findings, "error", "timeline_event_count_mismatch", "event_count must equal the number of timeline events.")
    for event in events:
        if not event.get("event_id"):
            add_finding(findings, "error", "timeline_event_missing_id", "Timeline event is missing event_id.")
        if not event.get("kind"):
            add_finding(findings, "error", "timeline_event_missing_kind", "Timeline event is missing kind.", str(event.get("event_id") or ""))
        if not event.get("name"):
            add_finding(findings, "warning", "timeline_event_missing_name", "Timeline event is missing name.", str(event.get("event_id") or ""))
        if event.get("kind") == "phase" and not event.get("gates"):
            add_finding(findings, "error", "phase_event_missing_gates", "Phase timeline events must include gates.", str(event.get("event_id") or ""))
    for event_id in duplicate_ids:
        add_finding(findings, "error", "timeline_duplicate_event_id", "Timeline event_id must be unique.", event_id)

    expected_phase_count = len(phase_state.get("phases", []))
    if len(phase_events) != expected_phase_count:
        add_finding(findings, "error", "timeline_phase_count_mismatch", "Timeline phase event count must match phase_state phase count.")
    expected_review_count = len(review_result.get("iterations", []))
    if len(review_events) != expected_review_count:
        add_finding(findings, "error", "timeline_review_count_mismatch", "Timeline review event count must match review iteration count.")
    missing_gate_events = sorted(REQUIRED_GATE_EVENTS.difference(gate_ids))
    for event_id in missing_gate_events:
        add_finding(findings, "error", "timeline_missing_gate_event", "Timeline is missing a required gate event.", event_id)

    final_status = build_timeline.get("final_status") or {}
    if final_status.get("publish_gate") != publish_gate.get("status"):
        add_finding(findings, "error", "timeline_publish_status_mismatch", "Timeline final publish status must match publish_gate.")
    if final_status.get("quality") != quality_report.get("status"):
        add_finding(findings, "error", "timeline_quality_status_mismatch", "Timeline final quality status must match quality_report.")
    if final_status.get("review") != review_result.get("status"):
        add_finding(findings, "error", "timeline_review_status_mismatch", "Timeline final review status must match review summary.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "event_count": len(events),
        "declared_event_count": build_timeline.get("event_count"),
        "phase_event_count": len(phase_events),
        "expected_phase_event_count": expected_phase_count,
        "phase_scope": "full_phase_state",
        "review_event_count": len(review_events),
        "expected_review_event_count": expected_review_count,
        "gate_event_ids": sorted(gate_ids),
        "event_kinds": event_kinds,
        "duplicate_event_ids": duplicate_ids,
        "findings": findings,
        "policy": [
            "Build timeline audit is static and never executes package code.",
            "The timeline must preserve phase, review, and final gate events with stable event ids.",
            "The timeline is a run artifact for auditability and must not be copied into the public child skill.",
        ],
    }
