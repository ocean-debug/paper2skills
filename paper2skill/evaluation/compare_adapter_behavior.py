from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, finish_result, normalize_token, text_blob


EXECUTABLE_STATUSES = {"ready", "reviewed", "verified"}


def compare_adapter_behavior(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("adapter_behavior")
    adapter = generated.get("adapter_spec") or {}
    algorithm_contract = generated.get("algorithm_contract") or {}
    expected_type = normalize_token(gold.get("expected_adapter_type"))
    actual_type = normalize_token(adapter.get("adapter_type"))
    type_accuracy = adapter_type_matches(expected_type, actual_type)
    if not type_accuracy:
        result["mismatched_items"].append({"field": "adapter_type", "expected": expected_type, "actual": actual_type})

    expected_status = normalize_token(gold.get("expected_initial_status"))
    actual_status = normalize_token(adapter.get("status"))
    status_accuracy = 1.0 if not expected_status or expected_status == actual_status else 0.0
    if expected_status and expected_status != actual_status:
        result["mismatched_items"].append({"field": "adapter_status", "expected": expected_status, "actual": actual_status})

    expects_block = normalize_token(((gold.get("non_demo_run") or {}).get("expected_behavior"))) in {"blocked_until_reviewed", "blocked"}
    non_demo_block = 1.0 if not expects_block or actual_status not in EXECUTABLE_STATUSES else 0.0
    install_policy = 1.0 if install_policy_compliant(algorithm_contract, generated) else 0.0
    execution_safety = 1.0 if actual_status not in EXECUTABLE_STATUSES or expected_status in EXECUTABLE_STATUSES else 0.0
    return finish_result(
        result,
        {
            "adapter_type_accuracy": type_accuracy,
            "adapter_status_accuracy": status_accuracy,
            "non_demo_block_correctness": non_demo_block,
            "install_policy_compliance": install_policy,
            "execution_claim_safety": execution_safety,
        },
    )


def adapter_type_matches(expected: str, actual: str) -> float:
    if not expected:
        return 1.0
    if expected == actual:
        return 1.0
    aliases = {
        "r_script_or_r_package": {"r_script", "r_package"},
        "python_api_or_notebook": {"python_api", "notebook"},
    }
    return 1.0 if actual in aliases.get(expected, set()) else 0.0


def install_policy_compliant(algorithm_contract: dict[str, Any], generated: dict[str, Any]) -> bool:
    text = text_blob({"algorithm_contract": algorithm_contract, "environment_spec": generated.get("environment_spec") or {}})
    return "install_policy_default" in text and "ask" in text or "install_policy" in text and "ask" in text
