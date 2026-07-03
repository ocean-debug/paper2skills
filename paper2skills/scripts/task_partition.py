"""Capability partitioning into task_type entries."""

from __future__ import annotations

from typing import Any

from common import as_list, lower_join, now_utc, slugify
from constants import SCHEMA_VERSION, TASK_HEURISTICS
from execution_grounding import execution_status_for


def infer_task_types(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> list[str]:
    requested = [slugify(str(item), "task") for item in as_list(request.get("requested_task_types"))]
    inferred: list[str] = []
    text = lower_join(
        [request.get("package_name"), request.get("method_name"), request.get("repo_url")]
        + [source.get("uri") for source in sources]
    )
    for task_type, needles in TASK_HEURISTICS.items():
        if any(needle in text for needle in needles):
            inferred.append(task_type)
    if evidence_cards:
        for card in evidence_cards.get("cards", []):
            inferred.extend(card.get("task_type_candidates", []))
    merged = []
    for task_type in requested + inferred:
        if task_type not in merged:
            merged.append(task_type)
    return merged or ["general_algorithm_use"]


def task_evidence_refs(
    task_type: str,
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> list[str]:
    refs = []
    if evidence_cards:
        for card in evidence_cards.get("cards", []):
            if task_type in card.get("task_type_candidates", []):
                refs.append(str(card.get("evidence_card_id")))
    for source in sources:
        haystack = str(source.get("uri", "")).lower()
        if task_type == "general_algorithm_use" or task_type.replace("_", "-") in haystack:
            refs.append(str(source["evidence_id"]))
    if not refs:
        refs = [str(source["evidence_id"]) for source in sources[:3]]
    return refs


def evidence_summaries_for(
    evidence_cards: dict[str, Any] | None,
    task_type: str,
    claim_type: str,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if not evidence_cards:
        return []
    matches = []
    for card in evidence_cards.get("cards", []):
        if card.get("claim_type") != claim_type:
            continue
        if task_type not in card.get("task_type_candidates", []):
            continue
        matches.append(
            {
                "summary": card.get("summary"),
                "evidence_ref": card.get("evidence_card_id"),
                "confidence": card.get("confidence"),
            }
        )
    return matches[:limit]


def routing_cues(task_type: str) -> list[str]:
    readable = task_type.replace("_", " ")
    cues = {
        "integration": [
            "User asks to integrate datasets or correct batch effects.",
            "Input mentions batches, donors, technologies, or harmonization.",
        ],
        "multiomics_integration": [
            "User asks to combine modalities such as RNA, ATAC, protein, or CITE-seq.",
            "Input includes modality-specific matrices or paired multiome data.",
        ],
        "cell_annotation": [
            "User asks to annotate, classify, transfer labels, or map query cells.",
            "A reference label set or known annotation field is required.",
        ],
        "trajectory": [
            "User asks for pseudotime, lineage, fate, velocity, or differentiation order.",
            "Data must be appropriate for trajectory-style interpretation.",
        ],
        "differential_analysis": [
            "User asks for markers, DE genes, contrasts, or condition differences.",
            "Required grouping or condition metadata must be available.",
        ],
        "perturbation_prediction": [
            "User asks for perturbation response, stimulated vs control prediction, or counterfactual states.",
            "Control and perturbation condition semantics must be explicit.",
        ],
        "spatial_mapping": [
            "User asks to map or analyze spatial transcriptomics coordinates.",
            "Spatial coordinates or spatial assay metadata must be present.",
        ],
        "preprocessing": [
            "User asks for QC, filtering, normalization, or preprocessing before analysis.",
            "Raw or partially processed input should be clearly described.",
        ],
        "visualization": [
            "User asks only for plotting, embeddings, or visual summaries.",
            "Use only if the package evidence supports visualization as an intended task.",
        ],
    }
    return cues.get(
        task_type,
        [
            f"User asks for the package's documented {readable} workflow.",
            "Use only within official evidence-backed package scope.",
        ],
    )


def default_input_contract(task_type: str, evidence_cards: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "required_from_user": [
            "analysis goal mapped to task_type",
            "input data path and format",
            "metadata fields required by the selected task_type",
        ],
        "must_confirm": [
            "input modality matches official evidence",
            "required metadata exists and has the intended biological meaning",
            "package backend is supported",
        ],
        "notes": f"Specific fields for {task_type} must be filled from official tutorial/API evidence during review.",
        "evidence_observed": evidence_summaries_for(evidence_cards, task_type, "input_contract"),
    }


def default_output_contract(task_type: str, evidence_cards: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "expected_outputs": [
            "package-specific result object or files documented by official evidence",
            "run summary or result location",
        ],
        "minimum_validation": [
            "expected output exists",
            "output format can be opened by the documented reader",
            "required result fields are present when evidence specifies them",
        ],
        "notes": f"Do not promise biological quality metrics for {task_type} unless official evidence defines them.",
        "evidence_observed": evidence_summaries_for(evidence_cards, task_type, "output_contract"),
        "api_entrypoints_observed": evidence_summaries_for(evidence_cards, task_type, "api_entrypoint"),
        "validation_observed": evidence_summaries_for(evidence_cards, task_type, "validation_rule"),
    }


def default_refusal_boundaries(task_type: str, request: dict[str, Any]) -> list[dict[str, str]]:
    boundaries = [
        {
            "reason_key": "missing_required_input",
            "refusal_type": "fixable",
            "when": "Required data path, task_type, metadata field, or parameter is missing.",
        },
        {
            "reason_key": "unsupported_task_type",
            "refusal_type": "unsupported",
            "when": "The user goal does not match any evidence-backed task_type in this skill.",
        },
        {
            "reason_key": "unsupported_modality_or_format",
            "refusal_type": "unsupported",
            "when": "The data modality or file format is outside official evidence for this task_type.",
        },
        {
            "reason_key": "unconfirmed_install",
            "refusal_type": "fixable",
            "when": "Execution would require dependency installation or environment changes without approval.",
        },
    ]
    if request.get("language_backend") != "python":
        boundaries.append(
            {
                "reason_key": "backend_not_implemented",
                "refusal_type": "unsupported",
                "when": "The current backend supports Python first; R is reserved as a backend extension.",
            }
        )
    return boundaries


def build_task_catalog(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tasks = []
    for task_type in infer_task_types(request, sources, evidence_cards):
        execution = execution_status_for(task_type, request)
        refs = task_evidence_refs(task_type, sources, evidence_cards)
        tasks.append(
            {
                "task_type": task_type,
                "capability_name": task_type.replace("_", " "),
                "skill_scope": "same_child_skill",
                "evidence_refs": refs,
                "verification_status": execution["status"],
                "execution_grounded": execution["execution_grounded"],
                "trace_ref": execution["trace_ref"],
                "routing_cues": routing_cues(task_type),
                "input_contract": default_input_contract(task_type, evidence_cards),
                "output_contract": default_output_contract(task_type, evidence_cards),
                "refusal_boundaries": default_refusal_boundaries(task_type, request),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "one_package_one_skill": True,
        "tasks": tasks,
    }
