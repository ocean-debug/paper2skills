from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def infer_io_contract(tutorial_trace: dict[str, Any], bio_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = []
    outputs = []
    format_evidence = []
    text_items = []
    for step in tutorial_trace.get("workflow_steps", []):
        inputs.extend(step.get("inputs", []))
        inputs.extend(step.get("read_files", []))
        outputs.extend(step.get("outputs", []))
        outputs.extend(step.get("write_files", []))
        format_evidence.extend(step_format_evidence(step))
        text_items.extend(step_format_evidence(step))
    bio = (bio_contract or {}).get("bio_contract", {})
    modality = (((bio.get("modality") or {}).get("primary") or {}).get("value"))
    return {
        "input_contract": {
            "required": {
                "input_manifest": {"type": "yaml", "state": "required"},
                "primary_data": {
                    "type": "file",
                    "state": "not_confirmed" if not inputs else "tutorial_confirmed",
                    "format": file_format_field(format_evidence, modality),
                    "matrix_state": matrix_state_field(bio),
                    "matrix_orientation": field_value("unknown", "low", []),
                    "metadata_keys": metadata_keys(bio, text_items),
                    "organism": organism_fields(bio),
                    "external_resources": external_resources(bio),
                    "evidence": sorted({str(value) for value in inputs if value}),
                },
            }
        },
        "output_contract": {
            "required": ["qc/environment_report.json", "qc/input_validation.json", "workflow/plan.json", "result.json", "results/"],
            "tutorial_outputs": sorted(dict.fromkeys(outputs)),
        },
    }


def step_format_evidence(step: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(string_values(step.get("inputs", [])))
    values.extend(string_values(step.get("read_files", [])))
    for call in step.get("function_calls", []) or []:
        if isinstance(call, dict):
            name = call.get("name")
            if name:
                values.append(str(name))
            values.extend(string_values(call.get("args", [])))
        elif call:
            values.append(str(call))
    for key in ["code_preview", "command_or_code"]:
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    return values


def string_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        values = [values]
    return [str(value) for value in values if value]


def field_value(value: Any, confidence: str = "low", evidence: list[str] | None = None) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "evidence": evidence or []}


def file_format_field(paths: list[Any], modality: str | None = None) -> dict[str, Any]:
    detected_values: dict[str, list[str]] = {}
    for value in paths:
        detected = detect_file_format(str(value), modality)
        if detected != "unknown":
            detected_values.setdefault(detected, []).append(str(value))
    primary_values = {key: value for key, value in detected_values.items() if key not in {"csv", "tsv"}}
    if primary_values:
        detected_values = primary_values
    if len(detected_values) == 1:
        detected, evidence = next(iter(detected_values.items()))
        return field_value(detected, "high", evidence)
    if len(detected_values) > 1:
        evidence = [item for values in detected_values.values() for item in values]
        result = field_value("not_confirmed", "low", evidence)
        result["conflicts"] = sorted(detected_values)
        return result
    return field_value("unknown", "low", [])


def detect_file_format(value: str, modality: str | None = None) -> str:
    lower = value.lower()
    name = PurePosixPath(lower.replace("\\", "/")).name
    if modality == "bulk RNA-seq" and ("deseqdatasetfrommatrix" in lower or "countdata" in lower or "counts" in name):
        return "count_matrix"
    if lower.endswith(".h5ad"):
        return "h5ad"
    if lower.endswith((".rds", ".rda")):
        return "rds"
    if name == "matrix.mtx" or "read_10x" in lower or "filtered_feature_bc_matrix" in lower:
        return "10x_mtx"
    if lower.endswith(".mtx"):
        return "mtx"
    if modality == "bulk RNA-seq" and lower.endswith((".csv", ".tsv", ".txt")):
        return "count_matrix"
    if lower.endswith((".csv", ".tsv")):
        return "csv" if lower.endswith(".csv") else "tsv"
    if lower.endswith(".loom"):
        return "loom"
    if lower.endswith((".h5", ".hdf5")):
        return "hdf5"
    return "unknown"


def matrix_state_field(bio: dict[str, Any]) -> dict[str, Any]:
    matrix = bio.get("input_matrix_state", {})
    transformations = matrix.get("matrix_transformations", []) or []
    if "log1p_transformed" in transformations:
        return field_value("log1p", "high", matrix.get("log_transformed_allowed", {}).get("evidence", []))
    if "normalized" in transformations:
        return field_value("normalized", "high", matrix.get("normalized_allowed", {}).get("evidence", []))
    if "raw_counts_loaded" in transformations or matrix.get("raw_counts_required", {}).get("value") is True:
        return field_value("raw_counts", "high", matrix.get("raw_counts_required", {}).get("evidence", []))
    return field_value("unknown", "low", [])


def metadata_keys(bio: dict[str, Any], text_items: list[str] | None = None) -> dict[str, Any]:
    metadata = bio.get("metadata_requirements", {})
    values = {key: metadata.get(key, field_value("not_confirmed")) for key in ["sample_key", "batch_key", "condition_key", "celltype_key", "perturbation_key"]}
    text = "\n".join(text_items or [])
    if values["condition_key"]["value"] == "not_confirmed" and "condition" in text.lower():
        values["condition_key"] = field_value("condition", "medium", ["tutorial_metadata_key"])
    if values["sample_key"]["value"] == "not_confirmed" and "sample" in text.lower():
        values["sample_key"] = field_value("sample", "medium", ["tutorial_metadata_key"])
    return values


def organism_fields(bio: dict[str, Any]) -> dict[str, Any]:
    organism = bio.get("organism", {})
    return {
        "species": organism.get("species_supported", field_value("not_confirmed")),
        "genome_build": organism.get("genome_build", field_value("not_confirmed")),
        "gene_id_type": organism.get("gene_id_type", field_value("not_confirmed")),
    }


def external_resources(bio: dict[str, Any]) -> dict[str, Any]:
    resources = bio.get("reference_resources", {})
    return {
        "genome": resources.get("genome", field_value("not_confirmed")),
        "annotation": resources.get("annotation", field_value("not_confirmed")),
        "grn": resources.get("grn", field_value("not_confirmed")),
        "ligand_receptor_database": resources.get("ligand_receptor_database", field_value("not_confirmed")),
        "pathway_database": resources.get("pathway_database", resources.get("database", field_value("not_confirmed"))),
    }
