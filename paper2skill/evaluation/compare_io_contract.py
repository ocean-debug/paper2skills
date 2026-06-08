from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, field_value, finish_result, flatten_strings, normalize_token, text_blob


def compare_io_contract(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("io_contract")
    io_contract = generated.get("io_contract") or {}
    primary = (((io_contract.get("input_contract") or {}).get("required") or {}).get("primary_data") or {})
    generated_format = normalize_token(field_value(primary.get("format")))
    gold_formats = extract_gold_formats(gold)
    format_accuracy = 1.0 if not gold_formats or any(tokens_equivalent(generated_format, expected) for expected in gold_formats) else 0.0
    if gold_formats and not format_accuracy:
        result["mismatched_items"].append({"field": "primary_input.format", "expected": sorted(gold_formats), "actual": generated_format})

    metadata_expected = extract_metadata_keys(gold)
    metadata_accuracy = key_recall(metadata_expected, primary.get("metadata_keys") or io_contract)
    output_expected = extract_output_terms(gold)
    output_accuracy = key_recall(output_expected, io_contract.get("output_contract") or {})
    return finish_result(
        result,
        {
            "input_format_accuracy": format_accuracy,
            "metadata_key_accuracy": metadata_accuracy,
            "output_contract_accuracy": output_accuracy,
        },
    )


def extract_gold_formats(gold: dict[str, Any]) -> set[str]:
    formats: set[str] = set()
    primary = gold.get("primary_input") or {}
    for key in ["accepted_formats", "accepted_objects"]:
        for item in primary.get(key) or []:
            formats.add(normalize_token(item))
    if primary.get("object_type"):
        formats.add(normalize_token(primary["object_type"]))
    for spec in (gold.get("primary_inputs") or {}).values():
        if isinstance(spec, dict) and spec.get("format"):
            formats.add(normalize_token(spec["format"]))
    return formats


def extract_metadata_keys(gold: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    metadata = gold.get("metadata") or {}
    for key, value in metadata.items():
        if not normalize_token(key).endswith("_file"):
            result.add(normalize_token(key))
        if isinstance(value, dict):
            for nested_key in ["name", "default", "override_arg", "semantic"]:
                if value.get(nested_key):
                    result.add(normalize_token(value[nested_key]))
            for item in value.get("required_columns") or []:
                result.add(normalize_token(item))
    primary_inputs = gold.get("primary_inputs") or {}
    sample_info = primary_inputs.get("sample_info_file") or {}
    for item in sample_info.get("required_columns") or []:
        result.add(normalize_token(item))
    return {item for item in result if item}


def extract_output_terms(gold: dict[str, Any]) -> set[str]:
    output = gold.get("output") or {}
    terms = set()
    for item in flatten_strings(output):
        token = normalize_token(item)
        if token and token not in {"true", "false", "required", "optional"}:
            terms.add(token)
    return terms


def key_recall(expected: set[str], observed: Any) -> float:
    if not expected:
        return 1.0
    observed_tokens = {canonical_token(item) for item in flatten_strings(observed)}
    observed_text = " ".join(observed_tokens)
    matched = sum(1 for item in expected if canonical_token(item) in observed_tokens or canonical_token(item) in observed_text)
    return matched / len(expected)


def canonical_token(value: str) -> str:
    token = normalize_token(value)
    aliases = {
        "celltype_key": "cell_type_key",
        "celltype": "cell_type",
        "celltypes": "cell_type",
        "sampleid": "sample_key",
        "sample_id": "sample_key",
        "seqtype": "seqtype_key",
        "sequencing_type": "seqtype_key",
        "tabular_count_matrix": "count_matrix",
        "raw_count_matrix": "count_matrix",
        "counts_matrix": "count_matrix",
        "anndata_object": "anndata",
        "anndata": "anndata",
        "h5ad": "anndata",
        "anndata_or_gears_pertdata": "anndata",
        "preprocessed_gears_dataset": "anndata",
        "seurat_object": "r_single_cell_object",
        "singlecellexperiment_object": "r_single_cell_object",
        "monocle3_object": "r_single_cell_object",
        "rds": "r_single_cell_object",
        "features_by_cells_matrix": "count_matrix",
        "genes_by_samples": "count_matrix",
        "sample_information_file": "sample_key",
        "sample_information": "sample_key",
        "sample": "sample_key",
        "condition": "condition_key",
        "batch": "batch_key",
        "label": "label_key",
        "perturbation": "perturbation_key",
    }
    return aliases.get(token, token)


def tokens_equivalent(left: str, right: str) -> bool:
    return canonical_token(left) == canonical_token(right)
