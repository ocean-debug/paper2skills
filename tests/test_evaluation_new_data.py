from __future__ import annotations

from paper2skill.evaluation.execution.run_new_data_validation import evaluate_new_data


def test_l3_valid_input_blocked_by_candidate_is_success():
    gold = {"valid_inputs": [{"input_id": "valid", "input_manifest": {"metadata": {"condition": "condition"}}, "expected_behavior": "blocked_until_reviewed"}]}
    generated = {"adapter_review": {"status": "candidate"}, "io_contract": {"input_contract": {}}}

    result = evaluate_new_data(gold, generated)

    assert result["passed"] is True
    assert result["inputs"][0]["actual_behavior"] == "blocked_until_reviewed"


def test_l3_invalid_missing_metadata_is_blocked():
    gold = {
        "invalid_inputs": [
            {
                "input_id": "missing_condition",
                "input_manifest": {"validation_errors": ["missing condition_key"]},
                "expected_reason_contains": ["condition_key"],
            }
        ]
    }

    result = evaluate_new_data(gold, {"io_contract": {}})

    assert result["passed"] is True
    assert result["inputs"][0]["actual_behavior"] == "block"


def test_l3_normalized_input_rejected_when_raw_counts_required():
    gold = {
        "invalid_inputs": [
            {
                "input_id": "normalized",
                "input_manifest": {"matrix_state": "normalized_tpm"},
                "expected_reason_contains": ["raw counts"],
            }
        ]
    }
    generated = {"io_contract": {"input_contract": {"required": {"primary_data": {"matrix_state": {"value": "raw_counts"}}}}}}

    result = evaluate_new_data(gold, generated)

    assert result["passed"] is True
