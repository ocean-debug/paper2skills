from __future__ import annotations

from typing import Any


def evaluate_trace(task: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    expected = task.get("expected_behavior") or {}
    expected_action = str(expected.get("action") or "")
    reason_contains = [str(item).lower() for item in expected.get("reason_contains") or []]
    must_reference = [str(item).lower() for item in expected.get("must_reference") or []]
    must_not = [str(item).lower() for item in expected.get("must_not") or []]
    action = str(trace.get("action") or "")
    reason = str(trace.get("reason") or "").lower()
    references = " ".join(str(item).lower() for item in trace.get("references") or [])
    attempted = " ".join(str(item).lower() for item in trace.get("attempted_actions") or [])
    mismatches = []
    if expected_action and action != expected_action:
        mismatches.append({"field": "action", "expected": expected_action, "actual": action})
    missing_reasons = [item for item in reason_contains if item not in reason]
    if missing_reasons:
        mismatches.append({"field": "reason_contains", "missing": missing_reasons})
    missing_refs = [item for item in must_reference if item not in references and item not in reason]
    if missing_refs:
        mismatches.append({"field": "must_reference", "missing": missing_refs})
    forbidden = [item for item in must_not if item in attempted or item in reason]
    if forbidden:
        mismatches.append({"field": "must_not", "violations": forbidden})
    return {"passed": not mismatches, "mismatched_items": mismatches}

