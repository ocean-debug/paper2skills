from __future__ import annotations

import re
from typing import Any

from paper2skill.inference.bio_rules import GENE_ID_RULES, MATRIX_STATE_RULES, MODALITY_RULES, SPECIES_RULES, match_rules


def field_value(value: Any = "not_confirmed", confidence: str = "low", evidence: list[str] | None = None) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "evidence": evidence or []}


def default_bio_contract() -> dict[str, Any]:
    return {
        "bio_contract": {
            "modality": {"primary": "not_confirmed", "secondary": "not_confirmed"},
            "organism": {"species_supported": "not_confirmed", "genome_build": "not_confirmed", "gene_id_type": "not_confirmed"},
            "input_matrix_state": {
                "raw_counts_required": "not_confirmed",
                "normalized_allowed": "not_confirmed",
                "log_transformed_allowed": "not_confirmed",
                "matrix_orientation": "not_confirmed",
            },
            "metadata_requirements": {
                "celltype_key": "not_confirmed",
                "sample_key": "not_confirmed",
                "batch_key": "not_confirmed",
                "condition_key": "not_confirmed",
            },
            "minimum_data_requirements": {
                "min_cells": "not_confirmed",
                "min_genes": "not_confirmed",
                "min_cells_per_group": "not_confirmed",
            },
            "reference_resources": {
                "genome": "not_confirmed",
                "annotation": "not_confirmed",
                "database": "not_confirmed",
                "grn": "not_confirmed",
                "ligand_receptor_database": "not_confirmed",
            },
            "statistical_contract": {
                "multiple_testing": "not_confirmed",
                "fdr_threshold": "not_confirmed",
                "metric": "not_confirmed",
            },
            "interpretation_boundary": {
                "dry_run_is_not_biological_result": True,
                "demo_run_is_not_user_data_validation": True,
                "cross_species_mapping_requires_confirmation": True,
            },
        }
    }


def infer_bio_contract(
    tutorial_trace: dict[str, Any],
    paper_sections: list[dict[str, Any]] | None = None,
    dependency_evidence: dict[str, Any] | None = None,
    strict_evidence: bool = False,
) -> dict[str, Any]:
    text_items = evidence_texts(tutorial_trace, paper_sections or [])
    all_text = "\n".join(text for _eid, text, _source in text_items)
    modality = first_with_evidence(text_items, MODALITY_RULES, strict_evidence)
    species = first_with_evidence(text_items, SPECIES_RULES, strict_evidence)
    gene_id = first_with_evidence(text_items, GENE_ID_RULES, strict_evidence)
    transformations = transformation_chain(text_items, strict_evidence)
    celltype_key = metadata_key(all_text, "celltype_key", ["cell_type", "celltype", "celltypes"])
    base = default_bio_contract()["bio_contract"]
    base["modality"] = {
        "primary": field_value(modality[0], modality[2], modality[1]) if modality else field_value(),
        "secondary": field_value(),
    }
    base["organism"] = {
        "species_supported": field_value(species[0], species[2], species[1]) if species else field_value(),
        "genome_build": field_value(),
        "gene_id_type": field_value(gene_id[0], gene_id[2], gene_id[1]) if gene_id else field_value(),
    }
    base["input_matrix_state"] = {
        "raw_counts_required": field_value("raw_counts_loaded" in transformations, "high" if "raw_counts_loaded" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "raw_counts_loaded", strict_evidence)),
        "normalized_allowed": field_value("normalized" in transformations, "high" if "normalized" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "normalized", strict_evidence)),
        "log_transformed_allowed": field_value("log1p_transformed" in transformations, "high" if "log1p_transformed" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "log1p_transformed", strict_evidence)),
        "matrix_orientation": field_value(),
        "matrix_transformations": transformations,
    }
    base["metadata_requirements"] = {
        "celltype_key": field_value(celltype_key, "medium", ["tutorial_metadata_key"]) if celltype_key else field_value(),
        "sample_key": field_value(),
        "batch_key": field_value(metadata_key(all_text, "batch_key", ["batch"]), "medium", ["tutorial_metadata_key"]) if metadata_key(all_text, "batch_key", ["batch"]) else field_value(),
        "condition_key": field_value(metadata_key(all_text, "condition_key", ["condition"]), "medium", ["tutorial_metadata_key"]) if metadata_key(all_text, "condition_key", ["condition"]) else field_value(),
    }
    return {"bio_contract": base}


def evidence_texts(tutorial_trace: dict[str, Any], paper_sections: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    items = []
    for tutorial in tutorial_trace.get("tutorials", []):
        for step in tutorial.get("steps", tutorial.get("workflow_steps", [])):
            text = "\n".join([step.get("code_preview", ""), step.get("command_or_code", ""), " ".join(step.get("function_calls", [])), " ".join(step.get("imports", []))])
            items.append((step.get("evidence_id") or step.get("step_id", "tutorial:unknown"), text, "tutorial"))
    for section in paper_sections:
        role = section_role(section.get("section_id", ""), section.get("title", ""))
        items.append((section.get("section_id", "paper:unknown"), section.get("text", ""), f"paper:{role}"))
    return items


def first_with_evidence(items: list[tuple[str, str, str]], rules: dict[str, list[str]], strict_evidence: bool = False) -> tuple[str, list[str], str] | None:
    for evidence_id, text, source in items:
        matches = match_rules(text, rules)
        if matches:
            confidence = confidence_for_source(source)
            if strict_evidence and confidence == "low":
                continue
            return matches[0], [evidence_id], confidence
    return None


def transformation_chain(items: list[tuple[str, str, str]], strict_evidence: bool = False) -> list[str]:
    found = []
    for value in MATRIX_STATE_RULES:
        if evidence_for_value(items, MATRIX_STATE_RULES, value, strict_evidence):
            found.append(value)
    return found


def evidence_for_value(items: list[tuple[str, str, str]], rules: dict[str, list[str]], value: str, strict_evidence: bool = False) -> list[str]:
    words = rules[value]
    evidence = []
    for evidence_id, text, source in items:
        if strict_evidence and confidence_for_source(source) == "low":
            continue
        if any(word.lower() in text.lower() for word in words):
            evidence.append(evidence_id)
    return evidence


def metadata_key(text: str, _field: str, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if re.search(rf"['\"]{re.escape(candidate)}['\"]", text) or candidate in text:
            return candidate
    return None


def section_role(section_id: str, title: str) -> str:
    text = f"{section_id} {title}".lower()
    if any(word in text for word in ["methods", "method", "data", "code", "software"]):
        return "methods"
    if any(word in text for word in ["results", "benchmark", "evaluation"]):
        return "results"
    if any(word in text for word in ["discussion", "limitation", "abstract", "introduction", "background"]):
        return "background"
    return "unknown"


def confidence_for_source(source: str) -> str:
    if source == "tutorial" or source.startswith("docs") or source.startswith("api"):
        return "high"
    if source in {"paper:methods", "paper:data", "paper:code"}:
        return "medium"
    return "low"
