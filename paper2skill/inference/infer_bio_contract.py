from __future__ import annotations

import re
from typing import Any

from paper2skill.inference.bio_rules import GENE_ID_RULES, MATRIX_STATE_RULES, MODALITY_RULES, SPECIES_RULES, match_rules

MODALITY_PRIORITY = {
    "ribo_rna_seq": 4,
    "perturb-seq": 3,
    "scRNA-seq": 2,
    "bulk_RNA-seq": 1,
}

NEGATED_NORMALIZATION_PATTERNS = [
    r"\bnot\s+(?:be\s+)?normalized\b",
    r"\bnot\s+normalized\b",
    r"\bshould\s+not\s+be\s+normalized\b",
    r"\bmust\s+not\s+be\s+normalized\b",
    r"\bnormalized\s+or\s+batch\s+corrected\b",
]

NEGATED_BATCH_PATTERNS = [
    r"\bnot\s+(?:be\s+)?batch\s+corrected\b",
    r"\bnot\s+batch\s+corrected\b",
    r"\bshould\s+not\s+be\s+batch\s+corrected\b",
    r"\bnormalized\s+or\s+batch\s+corrected\b",
]

BATCH_ACCOUNTED_PATTERNS = [
    r"batch effects? (?:are |should be )?(?:accounted for|removed|corrected)",
    r"batch effects?.{0,160}(?:accounted for|removed|corrected)",
    r"account(?:ed)? for .*batch effects?",
    r"remove .*batch effects?",
]


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
                "label_key": "not_confirmed",
                "seqtype_key": "not_confirmed",
                "perturbation_key": "not_confirmed",
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
    all_text = "\n".join(item["text"] for item in text_items)
    modality = best_modality_with_evidence(text_items, strict_evidence)
    species = first_with_evidence(text_items, SPECIES_RULES, strict_evidence)
    gene_id = first_with_evidence(text_items, GENE_ID_RULES, strict_evidence)
    transformations = transformation_chain(text_items, strict_evidence)
    normalized_disallowed = evidence_for_patterns(text_items, NEGATED_NORMALIZATION_PATTERNS, strict_evidence)
    batch_disallowed = evidence_for_patterns(text_items, NEGATED_BATCH_PATTERNS, strict_evidence)
    batch_accounted_for = evidence_for_patterns(text_items, BATCH_ACCOUNTED_PATTERNS, strict_evidence)
    base = default_bio_contract()["bio_contract"]
    base["modality"] = {
        "primary": field_value(normalize_modality(modality[0]), modality[2], modality[1]) if modality else field_value(),
        "secondary": field_value(),
    }
    base["organism"] = {
        "species_supported": field_value(species[0], species[2], species[1]) if species else field_value(),
        "genome_build": field_value(),
        "gene_id_type": field_value(gene_id[0], gene_id[2], gene_id[1]) if gene_id else field_value(),
    }
    base["input_matrix_state"] = {
        "raw_counts_required": field_value("raw_counts_loaded" in transformations, "high" if "raw_counts_loaded" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "raw_counts_loaded", strict_evidence)),
        "preprocessed_required": field_value("preprocessed" in transformations, "high" if "preprocessed" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "preprocessed", strict_evidence)),
        "normalized_allowed": field_value("normalized" in transformations and not normalized_disallowed, "high" if "normalized" in transformations and not normalized_disallowed else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "normalized", strict_evidence)),
        "normalized_input_disallowed": field_value(bool(normalized_disallowed), "high" if normalized_disallowed else "low", normalized_disallowed),
        "batch_corrected_input_disallowed": field_value(bool(batch_disallowed), "high" if batch_disallowed else "low", batch_disallowed),
        "batch_effects_accounted_for": field_value(bool(batch_accounted_for), "high" if batch_accounted_for else "low", batch_accounted_for),
        "log_transformed_allowed": field_value("log1p_transformed" in transformations, "high" if "log1p_transformed" in transformations else "low", evidence_for_value(text_items, MATRIX_STATE_RULES, "log1p_transformed", strict_evidence)),
        "matrix_orientation": field_value(),
        "matrix_transformations": transformations,
    }
    base["metadata_requirements"] = metadata_requirements(all_text)
    base["modality_contracts"] = modality_contracts(base, all_text)
    return {"bio_contract": base}


def evidence_texts(tutorial_trace: dict[str, Any], paper_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    seen_steps: set[str] = set()
    for tutorial in tutorial_trace.get("tutorials", []):
        for step in tutorial.get("steps", tutorial.get("workflow_steps", [])):
            seen_steps.add(step.get("step_id", step.get("evidence_id", "")))
            text = step_text(step)
            source = "tutorial"
            items.append({"evidence_id": step.get("evidence_id") or step.get("step_id", "tutorial:unknown"), "text": text, "source_type": source, "section_role": "code", "weight": source_weight(source)})
    for step in tutorial_trace.get("workflow_steps", []):
        step_id = step.get("step_id", step.get("evidence_id", ""))
        if step_id in seen_steps:
            continue
        source = "tutorial"
        items.append({"evidence_id": step.get("evidence_id") or step.get("step_id", "tutorial:unknown"), "text": step_text(step), "source_type": source, "section_role": "code", "weight": source_weight(source)})
    for section in paper_sections:
        role = section_role(section.get("section_id", ""), section.get("title", ""))
        source = f"paper:{role}"
        items.append({"evidence_id": section.get("section_id", "paper:unknown"), "text": section.get("text", ""), "source_type": source, "section_role": role, "weight": source_weight(source)})
    return items


def step_text(step: dict[str, Any]) -> str:
    return "\n".join(
        [
            step.get("code_preview", ""),
            step.get("command_or_code", ""),
            " ".join(str(call) for call in step.get("function_calls", [])),
            " ".join(step.get("imports", [])),
        ]
    )


def first_with_evidence(items: list[dict[str, Any]], rules: dict[str, list[str]], strict_evidence: bool = False) -> tuple[str, list[str], str] | None:
    candidates = []
    for item in items:
        matches = match_rules(item["text"], rules)
        if matches:
            confidence = confidence_for_source(item["source_type"])
            if strict_evidence and confidence == "low":
                continue
            candidates.append((item["weight"], confidence_rank(confidence), matches[0], [item["evidence_id"]], confidence))
    if not candidates:
        return None
    _weight, _rank, value, evidence, confidence = sorted(candidates, reverse=True)[0]
    return value, evidence, confidence


def best_modality_with_evidence(items: list[dict[str, Any]], strict_evidence: bool = False) -> tuple[str, list[str], str] | None:
    scores: dict[str, float] = {}
    evidence: dict[str, set[str]] = {}
    confidence: dict[str, str] = {}
    for item in items:
        source_confidence = confidence_for_source(item["source_type"])
        if strict_evidence and source_confidence == "low":
            continue
        for value, words in MODALITY_RULES.items():
            matched_words = [word for word in words if rule_in_text(item["text"], word)]
            if not matched_words:
                continue
            scores[value] = scores.get(value, 0.0) + item["weight"] * len(set(matched_words))
            scores[value] += MODALITY_PRIORITY.get(value, 0) * 0.1
            evidence.setdefault(value, set()).add(item["evidence_id"])
            if confidence_rank(source_confidence) >= confidence_rank(confidence.get(value, "low")):
                confidence[value] = source_confidence
    if not scores:
        return None
    value = sorted(scores, key=lambda item: (scores[item], MODALITY_PRIORITY.get(item, 0), item), reverse=True)[0]
    return value, sorted(evidence.get(value, [])), confidence.get(value, "low")


def transformation_chain(items: list[dict[str, Any]], strict_evidence: bool = False) -> list[str]:
    found = []
    for value in MATRIX_STATE_RULES:
        if evidence_for_value(items, MATRIX_STATE_RULES, value, strict_evidence):
            found.append(value)
    return found


def evidence_for_value(items: list[dict[str, Any]], rules: dict[str, list[str]], value: str, strict_evidence: bool = False) -> list[str]:
    words = rules[value]
    matches = []
    for item in items:
        if strict_evidence and confidence_for_source(item["source_type"]) == "low":
            continue
        if value == "normalized" and has_negated_normalization(item["text"]):
            continue
        if any(rule_in_text(item["text"], word) for word in words):
            matches.append(item)
    return [item["evidence_id"] for item in sorted(matches, key=lambda value: value["weight"], reverse=True)]


def evidence_for_patterns(items: list[dict[str, Any]], patterns: list[str], strict_evidence: bool = False) -> list[str]:
    matches = []
    for item in items:
        if strict_evidence and confidence_for_source(item["source_type"]) == "low":
            continue
        if any(re.search(pattern, item["text"], flags=re.IGNORECASE | re.DOTALL) for pattern in patterns):
            matches.append(item)
    return [item["evidence_id"] for item in sorted(matches, key=lambda value: value["weight"], reverse=True)]


def has_negated_normalization(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in NEGATED_NORMALIZATION_PATTERNS)


def rule_in_text(text: str, word: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9_+-]+", word):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None
    return word.lower() in text.lower()


def metadata_requirements(text: str) -> dict[str, Any]:
    return {
        "celltype_key": metadata_field(text, ["cell.type", "cell_type", "celltype", "celltypes", "cell type"], "cell_type"),
        "sample_key": metadata_field(text, ["SampleID", "sample_id", "sample id", "sample"], "sample"),
        "batch_key": metadata_field(text, ["Batch", "batch"], "Batch"),
        "condition_key": metadata_field(text, ["Condition", "condition"], "condition"),
        "label_key": metadata_field(text, ["label_col", "label"], "label"),
        "seqtype_key": metadata_field(text, ["SeqType", "seqtype", "sequencing type"], "SeqType"),
        "perturbation_key": metadata_field(text, ["perturbation_key", "perturbation", "perturbed"], "perturbation"),
    }


def metadata_field(text: str, candidates: list[str], canonical: str) -> dict[str, Any]:
    matched = metadata_key(text, "", candidates)
    if not matched:
        return field_value()
    value = field_value(canonical, "medium", ["tutorial_metadata_key"])
    aliases = sorted({candidate for candidate in candidates if metadata_key(text, "", [candidate])})
    if aliases:
        value["aliases"] = aliases
    return value


def metadata_key(text: str, _field: str, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if re.search(rf"['\"]{re.escape(candidate)}['\"]", text) or re.search(rf"\b{re.escape(candidate)}\b", text, flags=re.IGNORECASE):
            return candidate
    return None


def normalize_modality(value: str) -> str:
    return {
        "bulk_RNA-seq": "bulk RNA-seq",
        "ribo_rna_seq": "Ribo-seq/RNA-seq",
        "spatial_transcriptomics": "spatial",
    }.get(value, value)


def matrix_state_value(base: dict[str, Any]) -> dict[str, Any]:
    matrix = base.get("input_matrix_state", {})
    transformations = matrix.get("matrix_transformations", []) or []
    if "log1p_transformed" in transformations:
        return field_value("log1p", "high", matrix.get("log_transformed_allowed", {}).get("evidence", []))
    if "normalized" in transformations:
        return field_value("normalized", "high", matrix.get("normalized_allowed", {}).get("evidence", []))
    if "preprocessed" in transformations or matrix.get("preprocessed_required", {}).get("value") is True:
        return field_value("preprocessed", "high", matrix.get("preprocessed_required", {}).get("evidence", []))
    if "raw_counts_loaded" in transformations or matrix.get("raw_counts_required", {}).get("value") is True:
        return field_value("raw_counts", "high", matrix.get("raw_counts_required", {}).get("evidence", []))
    return field_value()


def modality_contracts(base: dict[str, Any], all_text: str) -> dict[str, Any]:
    modality = ((base.get("modality") or {}).get("primary") or {}).get("value")
    metadata = base.get("metadata_requirements", {})
    contracts = {
        "scrna_seq": {
            "input_state": {"matrix_state": field_value(), "formats": ["10x_mtx", "h5ad", "rds"]},
            "metadata": {"celltype_key": field_value(), "sample_key": field_value(), "batch_key": field_value(), "condition_key": field_value()},
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
        "bulk_rna_seq": {
            "input_state": {"matrix_state": field_value(), "formats": ["count_matrix", "csv", "tsv"]},
            "metadata": {"sample_key": field_value(), "condition_key": field_value(), "batch_key": field_value()},
            "statistical": {"design_formula": field_value(), "replicates": field_value()},
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
        "perturb_seq": {
            "input_state": {"matrix_state": matrix_state_value(base), "formats": ["h5ad", "AnnData_object"]},
            "metadata": {
                "condition_key": metadata.get("condition_key", field_value()),
                "celltype_key": metadata.get("celltype_key", field_value()),
                "perturbation_key": metadata.get("perturbation_key", field_value()),
            },
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
        "ribo_rna_seq": {
            "input_state": {"matrix_state": matrix_state_value(base), "formats": ["count_matrix", "csv", "tsv"]},
            "metadata": {
                "sample_key": metadata.get("sample_key", field_value()),
                "condition_key": metadata.get("condition_key", field_value()),
                "seqtype_key": metadata.get("seqtype_key", field_value()),
                "batch_key": metadata.get("batch_key", field_value()),
            },
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
        "spatial": {
            "input_state": {"matrix_state": field_value(), "formats": ["h5ad", "rds", "spatial_directory"]},
            "metadata": {"spatial_coordinates": field_value(), "image": field_value()},
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
        "proteomics": {
            "input_state": {"matrix_state": field_value(), "formats": ["csv", "tsv"]},
            "metadata": {},
            "reference_resources": {},
            "outputs": {"required": []},
        },
        "general": {
            "input_state": {"matrix_state": matrix_state_value(base), "formats": []},
            "metadata": metadata,
            "reference_resources": base.get("reference_resources", {}),
            "outputs": {"required": []},
        },
    }
    if modality == "scRNA-seq":
        contracts["scrna_seq"]["input_state"]["matrix_state"] = matrix_state_value(base)
        contracts["scrna_seq"]["metadata"] = {
            key: metadata.get(key, field_value())
            for key in ["celltype_key", "sample_key", "batch_key", "condition_key", "label_key"]
        }
    if modality == "bulk RNA-seq":
        contracts["bulk_rna_seq"]["input_state"]["matrix_state"] = matrix_state_value(base)
        contracts["bulk_rna_seq"]["metadata"]["condition_key"] = metadata.get("condition_key", field_value())
        formula = design_formula(all_text)
        if formula:
            contracts["bulk_rna_seq"]["statistical"]["design_formula"] = field_value(formula, "high", ["tutorial_design_formula"])
    if modality == "perturb-seq":
        contracts["perturb_seq"]["input_state"]["matrix_state"] = matrix_state_value(base)
    if modality == "Ribo-seq/RNA-seq":
        contracts["ribo_rna_seq"]["input_state"]["matrix_state"] = matrix_state_value(base)
    if modality == "spatial":
        contracts["spatial"]["input_state"]["matrix_state"] = matrix_state_value(base)
    return contracts


def design_formula(text: str) -> str | None:
    match = re.search(r"design\s*=\s*(~\s*[A-Za-z0-9_+. ]+)", text)
    if not match:
        return None
    return match.group(1).strip()


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


def source_weight(source: str) -> float:
    if source == "tutorial":
        return 1.0
    if source.startswith("api") or source.startswith("docs"):
        return 0.9
    if source in {"paper:methods", "paper:data", "paper:code"}:
        return 0.6
    if source.startswith("paper:"):
        return 0.2
    return 0.0


def confidence_rank(confidence: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(confidence, 0)
