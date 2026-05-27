from __future__ import annotations

from typing import Any


def validate_tutorial_trace(trace: dict[str, Any]) -> list[str]:
    errors = []
    for index, step in enumerate(trace.get("workflow_steps", [])):
        for key in ["id", "name", "source", "source_type", "evidence_id", "confidence"]:
            if key not in step:
                errors.append(f"workflow_steps[{index}] missing {key}")
    return errors
