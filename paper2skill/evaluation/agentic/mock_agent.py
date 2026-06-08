from __future__ import annotations

from typing import Any

from paper2skill.evaluation.schemas import EXECUTABLE_ADAPTER_STATUSES


def decide_action(task: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    command = str(task.get("user_command") or "").lower()
    expected_action = str((task.get("expected_behavior") or {}).get("action") or "")
    adapter_status = adapter_status_value(generated)
    if any(token in command for token in ["install all", "execute notebook", "unknown notebook"]):
        action = "refuse"
        reason = "unsafe command refused according to adapter_status and notebook policy"
    elif adapter_status not in EXECUTABLE_ADAPTER_STATUSES and expected_action in {"run", "explain_candidate_status"}:
        action = "explain_candidate_status"
        reason = "adapter_status is candidate, so execution requires review"
    elif expected_action:
        action = expected_action
        reason = refusal_reason(command)
    else:
        action = "refuse"
        reason = "insufficient structured task expectation"
    return {
        "action": action,
        "reason": reason,
        "references": ["io_contract", "bio_contract", "adapter_status"],
        "attempted_actions": [],
    }


def refusal_reason(command: str) -> str:
    parts = ["decision follows io_contract, bio_contract, and adapter_status"]
    if any(token in command for token in ["normalized", "tpm", "cpm"]):
        parts.append("raw counts required")
    if "without condition" in command or "missing condition" in command:
        parts.append("condition_key missing")
    if "without label" in command or "missing label" in command:
        parts.append("label metadata missing")
    if "without cell" in command or "missing cell" in command:
        parts.append("cell_type metadata missing")
    return "; ".join(parts)


def adapter_status_value(generated: dict[str, Any]) -> str:
    for key in ["adapter_review", "adapter_spec"]:
        source = generated.get(key) or {}
        if isinstance(source, dict):
            for field in ["status", "adapter_status", "initial_status"]:
                if source.get(field):
                    return str(source[field])
    return "candidate"
