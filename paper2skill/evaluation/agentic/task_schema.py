from __future__ import annotations

from typing import Any


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    expected = task.get("expected_behavior") or {}
    return {
        "task_id": task.get("task_id"),
        "user_command": task.get("user_command", ""),
        "workflow_id": task.get("workflow_id"),
        "provided_inputs": task.get("provided_inputs") or {},
        "expected_action": expected.get("action", "refuse"),
        "reason_contains": expected.get("reason_contains") or [],
        "must_reference": expected.get("must_reference") or [],
        "must_not": expected.get("must_not") or [],
    }

