from __future__ import annotations

from typing import Any


def infer_parameters(tutorial_trace: dict[str, Any]) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for step in tutorial_trace.get("workflow_steps", []):
        parameters.update(step.get("parameters", {}) or {})
    return parameters
