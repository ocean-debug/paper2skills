from __future__ import annotations

from typing import Any

from paper2skill.evaluation.execution.input_validator import validate_input_manifest
from paper2skill.evaluation.load_gold import evaluation_result, field_value, finish_result, text_blob
from paper2skill.evaluation.schemas import EXECUTABLE_ADAPTER_STATUSES


def evaluate_new_data(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("new_data_generalization")
    valid_inputs = gold.get("valid_inputs") or []
    invalid_inputs = gold.get("invalid_inputs") or []
    adapter_status = adapter_status_value(generated)
    io_contract = generated.get("io_contract") or {}
    reports = []
    scores = []
    for spec in valid_inputs:
        report = evaluate_valid_input(spec, io_contract, adapter_status)
        reports.append(report)
        scores.append(1.0 if report["passed"] else 0.0)
        result["mismatched_items"].extend(report.get("mismatched_items", []))
    for spec in invalid_inputs:
        report = evaluate_invalid_input(spec, io_contract)
        reports.append(report)
        scores.append(1.0 if report["passed"] else 0.0)
        result["mismatched_items"].extend(report.get("mismatched_items", []))
    result["inputs"] = reports
    if not scores:
        return finish_result(result, {"new_data_cases_defined": 1.0})
    valid_score = average([1.0 if item["passed"] else 0.0 for item in reports if item["kind"] == "valid"])
    invalid_score = average([1.0 if item["passed"] else 0.0 for item in reports if item["kind"] == "invalid"])
    return finish_result(
        result,
        {
            "valid_new_data_behavior": valid_score,
            "invalid_data_block_rate": invalid_score,
            "no_false_execution_on_invalid_input": invalid_score,
        },
    )


def evaluate_valid_input(spec: dict[str, Any], io_contract: dict[str, Any], adapter_status: str) -> dict[str, Any]:
    validation = validate_input_manifest(spec.get("input_manifest"), io_contract.get("input_contract") or io_contract)
    expected = str(spec.get("expected_behavior") or "blocked_until_reviewed")
    executable = adapter_status in EXECUTABLE_ADAPTER_STATUSES
    if expected in {"blocked_until_reviewed", "blocked_until_reviewed_or_dry_run"}:
        passed = not executable or validation["passed"]
        actual = "blocked_until_reviewed" if not executable else "validation_passed"
    elif expected in {"run", "dry_run"}:
        passed = validation["passed"] and executable
        actual = "validation_passed" if validation["passed"] else "validation_failed"
    else:
        passed = validation["passed"]
        actual = "validation_passed" if validation["passed"] else "validation_failed"
    return {
        "kind": "valid",
        "input_id": spec.get("input_id"),
        "expected_behavior": expected,
        "actual_behavior": actual,
        "adapter_status": adapter_status,
        "validation": validation,
        "passed": passed,
        "mismatched_items": [] if passed else [{"field": "valid_input", "input_id": spec.get("input_id"), "errors": validation["errors"]}],
    }


def evaluate_invalid_input(spec: dict[str, Any], io_contract: dict[str, Any]) -> dict[str, Any]:
    validation = validate_input_manifest(spec.get("input_manifest"), io_contract.get("input_contract") or io_contract)
    reasons = [str(item).lower() for item in spec.get("expected_reason_contains") or []]
    error_text = text_blob(validation.get("errors"))
    reason_match = all(reason in error_text for reason in reasons) if reasons else bool(validation["errors"])
    passed = not validation["passed"] and reason_match
    return {
        "kind": "invalid",
        "input_id": spec.get("input_id"),
        "expected_behavior": "block",
        "actual_behavior": "block" if not validation["passed"] else "accepted",
        "validation": validation,
        "passed": passed,
        "mismatched_items": [] if passed else [{"field": "invalid_input", "input_id": spec.get("input_id"), "errors": validation["errors"]}],
    }


def adapter_status_value(generated: dict[str, Any]) -> str:
    adapter_review = generated.get("adapter_review") or {}
    adapter_spec = generated.get("adapter_spec") or {}
    for source in [adapter_review, adapter_spec]:
        for key in ["status", "adapter_status", "initial_status"]:
            value = field_value(source.get(key) if isinstance(source, dict) else None)
            if value:
                return str(value)
    return "candidate"


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0
