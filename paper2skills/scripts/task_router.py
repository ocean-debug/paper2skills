"""Task-type router artifact construction."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def build_router(task_catalog: dict[str, Any]) -> dict[str, Any]:
    routes = []
    for index, task in enumerate(task_catalog["tasks"], start=1):
        routes.append(
            {
                "task_type": task["task_type"],
                "priority": index,
                "choose_when": task["routing_cues"],
                "ask_when": [
                    "The user goal matches more than one task_type.",
                    "Required modality, metadata role, or contrast is missing.",
                ],
                "refuse_when": [item["reason_key"] for item in task["refusal_boundaries"]],
                "verification_status": task["verification_status"],
                "evidence_refs": task["evidence_refs"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "routing_scope": "inside_single_child_skill",
        "selection_order": [
            "match user intent",
            "check modality and format",
            "check required metadata",
            "prefer execution_verified over source_grounded when both match",
            "ask on ambiguity",
            "refuse unsupported requests",
        ],
        "routes": routes,
    }
