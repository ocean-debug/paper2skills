from __future__ import annotations

from typing import Any


def infer_workflow(tutorial_trace: dict[str, Any]) -> dict[str, Any]:
    steps = tutorial_trace.get("workflow_steps", [])
    return {"steps": steps, "evidence_priority": ["tutorial", "docs", "api", "dependency_files", "paper", "readme"]}
