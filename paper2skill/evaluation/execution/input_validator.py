from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import flatten_strings, normalize_token, text_blob


def validate_input_manifest(input_manifest: dict[str, Any] | str | None, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = input_manifest if isinstance(input_manifest, dict) else {"path": input_manifest} if input_manifest else {}
    contract = contract or {}
    errors: list[str] = []
    warnings: list[str] = []
    manifest_text = text_blob(manifest)
    contract_text = text_blob(contract)

    for required in required_metadata_terms(contract):
        if required and normalize_token(required) not in normalize_token(manifest_text):
            errors.append(f"missing required metadata field: {required}")
    expected_state = expected_matrix_state(contract)
    if expected_state and "matrix_state" in manifest_text and normalize_token(expected_state) not in normalize_token(manifest_text):
        errors.append(f"matrix_state violates contract: expected {expected_state}")
    if "raw_counts" in normalize_token(contract_text) and any(token in normalize_token(manifest_text) for token in ["normalized", "tpm", "cpm"]):
        errors.append("raw counts required but normalized input was provided")
    for explicit in flatten_strings(manifest.get("validation_errors") if isinstance(manifest, dict) else []):
        errors.append(str(explicit))
    return {"passed": not errors, "errors": sorted(dict.fromkeys(errors)), "warnings": warnings}


def required_metadata_terms(contract: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ["metadata", "metadata_keys", "metadata_requirements"]:
        value = contract.get(key) if isinstance(contract, dict) else None
        if isinstance(value, dict):
            for field, spec in value.items():
                if isinstance(spec, dict) and spec.get("required") is True:
                    terms.append(str(field))
                    terms.extend(str(item) for item in spec.get("required_columns") or [])
                elif isinstance(spec, dict) and spec.get("value") not in {None, "not_confirmed"}:
                    terms.append(str(spec.get("value")))
    primary_inputs = contract.get("primary_inputs") if isinstance(contract, dict) else None
    if isinstance(primary_inputs, dict):
        for spec in primary_inputs.values():
            if isinstance(spec, dict):
                terms.extend(str(item) for item in spec.get("required_columns") or [])
    return terms


def expected_matrix_state(contract: dict[str, Any]) -> str | None:
    for item in flatten_strings(contract):
        token = normalize_token(item)
        if token in {"raw_counts", "preprocessed", "normalized", "log1p"}:
            return token
    return None

