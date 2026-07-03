"""Build a compact timeline from phase, review, and gate artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def phase_events(phase_state: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for index, phase in enumerate(phase_state.get("phases", []), start=1):
        events.append(
            {
                "event_id": f"phase:{index:03d}",
                "kind": "phase",
                "name": phase.get("name"),
                "status": phase.get("status"),
                "created_at": phase.get("created_at"),
                "inputs": phase.get("inputs", []),
                "outputs": phase.get("outputs", []),
                "gates": phase.get("gates", []),
            }
        )
    return events


def review_events(review_result: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for iteration in review_result.get("iterations", []):
        events.append(
            {
                "event_id": f"review:{int(iteration.get('iteration', 0)):03d}",
                "kind": "review_iteration",
                "name": "self_review",
                "status": "passed" if iteration.get("passed") else "patched" if iteration.get("patch", {}).get("changed") else "stopped",
                "created_at": iteration.get("created_at"),
                "score": iteration.get("score"),
                "total": iteration.get("total"),
                "score_ratio": iteration.get("score_ratio"),
                "blocking": iteration.get("blocking"),
                "patch_summary": iteration.get("patch", {}).get("patch_summary"),
            }
        )
    return events


def gate_events(publish_gate: dict[str, Any], quality_report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": "gate:publish",
            "kind": "gate",
            "name": "publish_gate",
            "status": publish_gate.get("status"),
            "created_at": publish_gate.get("created_at"),
            "finding_count": len(publish_gate.get("findings", [])),
        },
        {
            "event_id": "gate:quality",
            "kind": "gate",
            "name": "quality_report",
            "status": quality_report.get("status"),
            "created_at": quality_report.get("created_at"),
            "task_blocker_count": len(quality_report.get("task_blockers", [])),
        },
    ]


def build_timeline(
    request: dict[str, Any],
    phase_state: dict[str, Any],
    review_result: dict[str, Any],
    publish_gate: dict[str, Any],
    quality_report: dict[str, Any],
) -> dict[str, Any]:
    events = phase_events(phase_state) + review_events(review_result) + gate_events(publish_gate, quality_report)
    events.sort(key=lambda event: str(event.get("created_at") or ""))
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "event_count": len(events),
        "events": events,
        "final_status": {
            "review": review_result.get("status"),
            "publish_gate": publish_gate.get("status"),
            "quality": quality_report.get("status"),
        },
    }
