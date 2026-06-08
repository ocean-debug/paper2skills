from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, field_value, finish_result, flatten_strings, normalize_token, text_blob


def compare_bio_contract(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("bio_contract")
    contract = (generated.get("bio_contract") or {}).get("bio_contract") or generated.get("bio_contract") or {}
    modality_accuracy = compare_modality(gold, contract)
    matrix_state_accuracy = compare_matrix_state(gold, contract)
    not_confirmed_accuracy = compare_not_confirmed(gold, contract)
    return finish_result(
        result,
        {
            "modality_accuracy": modality_accuracy,
            "matrix_state_accuracy": matrix_state_accuracy,
            "not_confirmed_correctness": not_confirmed_accuracy,
        },
    )


def compare_modality(gold: dict[str, Any], contract: dict[str, Any]) -> float:
    expected = {canonical_bio_token(item) for item in flatten_strings(gold.get("modality")) if item}
    if not expected:
        return 1.0
    observed = canonical_bio_token(field_value(((contract.get("modality") or {}).get("primary") or contract.get("modality"))))
    return 1.0 if observed in expected else 0.0


def compare_matrix_state(gold: dict[str, Any], contract: dict[str, Any]) -> float:
    expected = expected_matrix_states(gold)
    if not expected:
        return 1.0
    observed = " ".join(canonical_bio_token(item) for item in flatten_strings(contract.get("input_matrix_state") or contract))
    matched = sum(1 for item in expected if canonical_bio_token(item) in observed)
    return matched / len(expected)


def expected_matrix_states(gold: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in flatten_strings(gold.get("matrix_state")):
        token = normalize_token(item)
        if token and token not in {"true", "false"}:
            result.add(token)
    primary = gold.get("input_state") or {}
    for item in flatten_strings(primary):
        token = normalize_token(item)
        if token in {"preprocessed", "raw_counts", "normalized", "log1p", "raw_counts_required"}:
            result.add(token)
    return result


def compare_not_confirmed(gold: dict[str, Any], contract: dict[str, Any]) -> float:
    expected_paths = count_not_confirmed(gold)
    if not expected_paths:
        return 1.0
    observed_text = text_blob(contract)
    return 1.0 if "not_confirmed" in observed_text else 0.0


def count_not_confirmed(value: Any) -> int:
    if isinstance(value, dict):
        return sum(count_not_confirmed(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_not_confirmed(item) for item in value)
    return 1 if value == "not_confirmed" else 0


def canonical_bio_token(value: Any) -> str:
    token = normalize_token(value)
    aliases = {
        "ribo_seq": "ribo_rna_seq",
        "rna_seq": "ribo_rna_seq",
        "ribo_seq_rna_seq": "ribo_rna_seq",
        "ribo_seq_and_rna_seq": "ribo_rna_seq",
        "ribo_seq_rna_seq_translational_efficiency": "ribo_rna_seq",
        "raw_counts_required": "raw_counts",
        "raw_counts_loaded": "raw_counts",
        "raw_count_matrix": "raw_counts",
        "count_matrix": "raw_counts",
        "counts_matrix": "raw_counts",
        "genes_by_samples": "raw_counts",
        "features_by_cells": "raw_counts",
        "features_by_cells_matrix": "raw_counts",
        "scrna_seq": "scrna_seq",
        "single_cell_rna_seq": "scrna_seq",
        "single_cell_embedding": "scrna_seq",
        "sc_rna_seq": "scrna_seq",
        "perturb_seq": "perturb_seq",
        "perturbation_prediction": "perturb_seq",
        "bulk_rna_seq": "bulk_rna_seq",
        "deseq2": "bulk_rna_seq",
        "seurat": "scrna_seq",
        "singlecellexperiment": "scrna_seq",
    }
    return aliases.get(token, token)
