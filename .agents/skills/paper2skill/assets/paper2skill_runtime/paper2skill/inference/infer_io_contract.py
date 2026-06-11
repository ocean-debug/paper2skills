from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any


def infer_io_contract(tutorial_trace: dict[str, Any], bio_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = []
    outputs = []
    format_evidence = []
    text_items = []
    for step in iter_steps(tutorial_trace):
        inputs.extend(step.get("inputs", []))
        inputs.extend(step.get("read_files", []))
        outputs.extend(step.get("outputs", []))
        outputs.extend(step.get("write_files", []))
        format_evidence.extend(step_format_evidence(step))
        text_items.extend(step_format_evidence(step))
    bio = (bio_contract or {}).get("bio_contract", {})
    modality = (((bio.get("modality") or {}).get("primary") or {}).get("value"))
    semantic_outputs = semantic_output_terms(outputs, text_items)
    return {
        "input_contract": {
            "required": {
                "input_manifest": {"type": "yaml", "state": "required"},
                "primary_data": {
                    "type": "file",
                    "state": "not_confirmed" if not inputs else "tutorial_confirmed",
                    "format": file_format_field(format_evidence, modality),
                    "matrix_state": matrix_state_field(bio),
                    "matrix_orientation": matrix_orientation_field(text_items),
                    "metadata_keys": metadata_keys(bio, text_items),
                    "organism": organism_fields(bio),
                    "external_resources": external_resources(bio),
                    "evidence": sorted({str(value) for value in inputs if value}),
                },
            }
        },
        "output_contract": {
            "required": ["qc/environment_report.json", "qc/input_validation.json", "workflow/plan.json", "result.json", "results/"],
            "tutorial_outputs": sorted(dict.fromkeys([*outputs, *flatten_semantic_outputs(semantic_outputs)])),
            "semantic_outputs": semantic_outputs,
        },
    }


def iter_steps(tutorial_trace: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tutorial in tutorial_trace.get("tutorials", []) or []:
        for step in [*(tutorial.get("steps") or []), *(tutorial.get("workflow_steps") or [])]:
            step_id = str(step.get("step_id") or step.get("id") or id(step))
            if step_id in seen:
                continue
            seen.add(step_id)
            steps.append(step)
    for step in tutorial_trace.get("workflow_steps", []) or []:
        step_id = str(step.get("step_id") or step.get("id") or id(step))
        if step_id in seen:
            continue
        seen.add(step_id)
        steps.append(step)
    return steps


def step_format_evidence(step: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(string_values(step.get("inputs", [])))
    values.extend(string_values(step.get("read_files", [])))
    values.extend(string_values(step.get("outputs", [])))
    values.extend(string_values(step.get("write_files", [])))
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
    primary_values = {key: value for key, value in detected_values.items() if key not in {"csv", "tsv", "AnnData_object"}}
    if primary_values:
        detected_values = primary_values
    if len(detected_values) == 1:
        detected, evidence = next(iter(detected_values.items()))
        return field_value(detected, "high", evidence)
    if len(detected_values) > 1:
        selected = select_primary_format(detected_values)
        if selected:
            evidence = [item for values in detected_values.values() for item in values]
            result = field_value(selected, "medium", detected_values[selected])
            result["alternatives"] = sorted(detected_values)
            result["evidence"] = evidence
            return result
        evidence = [item for values in detected_values.values() for item in values]
        result = field_value("not_confirmed", "low", evidence)
        result["conflicts"] = sorted(detected_values)
        return result
    return field_value("unknown", "low", [])


def select_primary_format(detected_values: dict[str, list[str]]) -> str | None:
    priority = ["h5ad", "10x_mtx", "AnnData_object", "rds", "count_matrix", "mtx", "loom", "hdf5", "csv", "tsv"]
    keys = set(detected_values)
    compatible_groups = [
        {"h5ad", "AnnData_object"},
        {"rds", "count_matrix"},
        {"count_matrix", "csv", "tsv"},
    ]
    if any(keys <= group for group in compatible_groups):
        for item in priority:
            if item in keys:
                return item
    if "h5ad" in keys and not {"10x_mtx", "rds"} & keys:
        return "h5ad"
    if "rds" in keys and "count_matrix" in keys and "10x_mtx" not in keys:
        return "rds"
    return None


def detect_file_format(value: str, modality: str | None = None) -> str:
    lower = value.lower()
    name = PurePosixPath(lower.replace("\\", "/")).name
    if modality == "bulk RNA-seq" and ("deseqdatasetfrommatrix" in lower or "countdata" in lower or "counts" in name):
        return "count_matrix"
    if lower.endswith(".h5ad") or ".h5ad" in lower or "read_h5ad" in lower:
        return "h5ad"
    if name == "matrix.mtx" or "read_10x" in lower or "filtered_feature_bc_matrix" in lower:
        return "10x_mtx"
    if lower.endswith(".mtx"):
        return "mtx"
    if lower.endswith((".rds", ".rda")) or ".rds" in lower or ".rda" in lower or "readrds" in lower:
        return "rds"
    if any(signal in lower for signal in ["anndata", "adata", "scanpy.read"]):
        return "AnnData_object"
    if any(signal in lower for signal in ["seurat", "singlecellexperiment", "singlecellexperiment_object", "monocle3"]) or re.search(r"\bsce\b", lower):
        return "rds"
    if any(signal in lower for signal in ["ribo-seq count matrix", "rna-seq count matrix", "genes-by-samples", "genes by samples", "features-by-cells", "features by cells", "sample information file", "raw count matrix"]):
        return "count_matrix"
    if modality == "bulk RNA-seq" and lower.endswith((".csv", ".tsv", ".txt")):
        return "count_matrix"
    if modality == "Ribo-seq/RNA-seq" and lower.endswith((".csv", ".tsv", ".txt")):
        return "count_matrix"
    if lower.endswith((".csv", ".tsv")):
        return "csv" if lower.endswith(".csv") else "tsv"
    if lower.endswith(".loom"):
        return "loom"
    if lower.endswith((".h5", ".hdf5")):
        return "hdf5"
    return "unknown"


def matrix_orientation_field(text_items: list[str] | None = None) -> dict[str, Any]:
    text = "\n".join(text_items or []).lower()
    if "genes-by-samples" in text or "genes by samples" in text:
        return field_value("genes_by_samples", "medium", ["tutorial_matrix_orientation"])
    if "genes-by-cells" in text or "genes by cells" in text:
        return field_value("genes_by_cells", "medium", ["tutorial_matrix_orientation"])
    if "features-by-cells" in text or "features by cells" in text:
        return field_value("features_by_cells", "medium", ["tutorial_matrix_orientation"])
    return field_value("unknown", "low", [])


def matrix_state_field(bio: dict[str, Any]) -> dict[str, Any]:
    matrix = bio.get("input_matrix_state", {})
    transformations = matrix.get("matrix_transformations", []) or []
    if "log1p_transformed" in transformations:
        return field_value("log1p", "high", matrix.get("log_transformed_allowed", {}).get("evidence", []))
    if "normalized" in transformations:
        return field_value("normalized", "high", matrix.get("normalized_allowed", {}).get("evidence", []))
    if "preprocessed" in transformations or matrix.get("preprocessed_required", {}).get("value") is True:
        return field_value("preprocessed", "high", matrix.get("preprocessed_required", {}).get("evidence", []))
    if "raw_counts_loaded" in transformations or matrix.get("raw_counts_required", {}).get("value") is True:
        return field_value("raw_counts", "high", matrix.get("raw_counts_required", {}).get("evidence", []))
    return field_value("unknown", "low", [])


def metadata_keys(bio: dict[str, Any], text_items: list[str] | None = None) -> dict[str, Any]:
    metadata = bio.get("metadata_requirements", {})
    values = {key: metadata.get(key, field_value("not_confirmed")) for key in ["sample_key", "batch_key", "condition_key", "celltype_key", "cell_type_key", "label_key", "seqtype_key", "perturbation_key"]}
    if values["cell_type_key"]["value"] == "not_confirmed" and values["celltype_key"]["value"] != "not_confirmed":
        values["cell_type_key"] = values["celltype_key"]
    text = "\n".join(text_items or [])
    lower = text.lower()
    if values["condition_key"]["value"] == "not_confirmed" and "condition" in lower:
        values["condition_key"] = field_value("condition", "medium", ["tutorial_metadata_key"])
    if values["sample_key"]["value"] == "not_confirmed" and ("sample" in lower or "sampleid" in lower or "sample information" in lower):
        values["sample_key"] = field_value("sample", "medium", ["tutorial_metadata_key"])
    if values["celltype_key"]["value"] == "not_confirmed" and ("cell_type" in lower or "celltype" in lower or "cell type" in lower):
        values["celltype_key"] = field_value("cell_type", "medium", ["tutorial_metadata_key"])
        values["cell_type_key"] = values["celltype_key"]
    if values["label_key"]["value"] == "not_confirmed" and ("label_col" in lower or "label" in lower):
        values["label_key"] = field_value("label", "medium", ["tutorial_metadata_key"])
    if values["seqtype_key"]["value"] == "not_confirmed" and ("seqtype" in lower or "sequencing type" in lower):
        values["seqtype_key"] = field_value("SeqType", "medium", ["tutorial_metadata_key"])
    if values["batch_key"]["value"] == "not_confirmed" and "batch" in lower:
        values["batch_key"] = field_value("Batch", "medium", ["tutorial_metadata_key"])
    if values["perturbation_key"]["value"] == "not_confirmed" and ("perturbation" in lower or "perturbed" in lower):
        values["perturbation_key"] = field_value("perturbation", "medium", ["tutorial_metadata_key"])
    return values


def semantic_output_terms(outputs: list[Any], text_items: list[str] | None = None) -> list[dict[str, Any]]:
    text = "\n".join([*string_values(outputs), *(text_items or [])])
    lower = text.lower()
    semantic: list[dict[str, Any]] = []
    if re.search(r"\baugur\$auc\b", lower) or "auc data frame" in lower or "auc item" in lower:
        semantic.append(
            {
                "name": "auc_table",
                "location": "augur$AUC",
                "columns": ["cell_type", "auc"],
                "evidence": ["tutorial_output_contract"],
            }
        )
    if "dteg" in lower or "differentially-te" in lower or "differential translation" in lower:
        semantic.append(
            {
                "name": "dteg_result_table",
                "location": "Results",
                "evidence": ["tutorial_output_contract"],
            }
        )
    if "mkdir results" in lower or re.search(r"['\"]results['\"]", lower) or "sample_data/results" in lower:
        semantic.append(
            {
                "name": "result_directory",
                "location": "sample_data/Results" if "sample_data/results" in lower else "Results",
                "evidence": ["tutorial_output_contract"],
            }
        )
    if "fold_changes/" in lower:
        semantic.append(
            {
                "name": "fold_change_tables",
                "location": "Results/fold_changes",
                "evidence": ["tutorial_output_contract"],
            }
        )
    if "gene_lists/" in lower:
        semantic.append(
            {
                "name": "gene_list_tables",
                "location": "Results/gene_lists",
                "examples": sorted(set(re.findall(r"gene_lists/[A-Za-z0-9_.-]+", text))),
                "evidence": ["tutorial_output_contract"],
            }
        )
    if "rdata" in lower or ".rdata" in lower:
        semantic.append({"name": "rdata", "required": "optional", "evidence": ["tutorial_output_contract"]})
    return dedupe_semantic_outputs(semantic)


def dedupe_semantic_outputs(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (str(value.get("name")), str(value.get("location", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def flatten_semantic_outputs(values: list[dict[str, Any]]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        flattened.extend(string_values(value.get("name")))
        flattened.extend(string_values(value.get("location")))
        flattened.extend(string_values(value.get("columns", [])))
        flattened.extend(string_values(value.get("examples", [])))
    return flattened


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
