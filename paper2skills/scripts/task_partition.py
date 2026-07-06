"""Capability partitioning into task_type entries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common import as_list, canonical_task_type, lower_join, now_utc
from constants import SCHEMA_VERSION, TASK_HEURISTICS
from execution_grounding import execution_status_for


def infer_task_types(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> list[str]:
    requested = [canonical_task_type(str(item), "task") for item in as_list(request.get("requested_task_types"))]
    if requested:
        merged_requested: list[str] = []
        for task_type in requested:
            if task_type not in merged_requested:
                merged_requested.append(task_type)
        return merged_requested

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
            inferred.extend(canonical_task_type(str(item), "task") for item in card.get("task_type_candidates", []))
    merged = []
    for task_type in inferred:
        if task_type not in merged:
            merged.append(task_type)
    return merged or ["general_algorithm_use"]


def task_evidence_refs(
    task_type: str,
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> list[str]:
    return task_evidence_record(task_type, sources, evidence_cards)["refs"]


def task_evidence_record(
    task_type: str,
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = []
    normalized_task_type = canonical_task_type(task_type)
    if evidence_cards:
        for card in evidence_cards.get("cards", []):
            card_task_types = {canonical_task_type(str(item), "task") for item in card.get("task_type_candidates", [])}
            if normalized_task_type in card_task_types and (
                normalized_task_type != "general_algorithm_use" or card.get("claim_type") != "task_support"
            ):
                refs.append(str(card.get("evidence_card_id")))
    for source in sources:
        haystack = str(source.get("uri", "")).lower()
        if normalized_task_type != "general_algorithm_use" and (
            normalized_task_type.replace("_", "-") in haystack or normalized_task_type in haystack.replace("-", "_")
        ):
            refs.append(str(source["evidence_id"]))
    support = "task_specific"
    if not refs:
        refs = [str(source["evidence_id"]) for source in sources[:3]]
        support = "fallback_only"
    return {"refs": refs, "support": support}


def evidence_summaries_for(
    evidence_cards: dict[str, Any] | None,
    task_type: str,
    claim_type: str,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if not evidence_cards:
        return []
    matches = []
    normalized_task_type = canonical_task_type(task_type)
    for card in evidence_cards.get("cards", []):
        if card.get("claim_type") != claim_type:
            continue
        card_task_types = {canonical_task_type(str(item), "task") for item in card.get("task_type_candidates", [])}
        if normalized_task_type not in card_task_types:
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


TASK_OPERATION_HINTS = {
    "perturbation_prediction": [
        "predict",
        "perturb",
        "stim",
        "ctrl",
        "condition",
        "delta",
        "response",
    ],
    "batch_removal": [
        "batch_removal",
        "batch",
        "correct",
        "integrat",
        "latent",
    ],
    "integration": [
        "integrat",
        "batch",
        "correct",
        "harmon",
        "latent",
    ],
    "cell_annotation": [
        "annot",
        "label",
        "classif",
        "predict",
        "reference",
        "query",
    ],
    "trajectory": [
        "trajectory",
        "pseudotime",
        "lineage",
        "velocity",
        "fate",
    ],
    "differential_analysis": [
        "differential",
        "marker",
        "rank",
        "contrast",
        "group",
    ],
    "spatial_mapping": [
        "spatial",
        "coordinate",
        "visium",
        "map",
    ],
    "preprocessing": [
        "preprocess",
        "filter",
        "normalize",
        "qc",
    ],
    "visualization": [
        "plot",
        "visual",
        "umap",
        "embedding",
    ],
}

GENERIC_REQUIRED_INPUTS = {
    "analysis goal mapped to task_type",
    "input data path and format",
    "metadata fields required by the selected task_type",
}

GENERIC_EXPECTED_OUTPUTS = {
    "package-specific result object or files documented by official evidence",
    "run summary or result location",
}

GENERIC_VALIDATION_CHECKS = {
    "expected output exists",
    "output format can be opened by the documented reader",
    "required result fields are present when evidence specifies them",
}


def unique_items(items: list[Any], limit: int | None = None) -> list[str]:
    values: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
        if limit is not None and len(values) >= limit:
            break
    return values


def task_hint_terms(task_type: str) -> list[str]:
    hints = TASK_OPERATION_HINTS.get(task_type, [])
    fallback = [part for part in task_type.replace("-", "_").split("_") if len(part) > 2]
    return unique_items(hints + fallback)


def interface_text(interface: dict[str, Any]) -> str:
    pieces = [
        interface.get("name"),
        interface.get("qualname"),
        interface.get("signature"),
        interface.get("docstring_summary"),
        interface.get("source_path"),
        " ".join(str(item) for item in interface.get("task_type_candidates", [])),
    ]
    return lower_join(pieces)


def tutorial_text(tutorial: dict[str, Any]) -> str:
    step_text = []
    for step in tutorial.get("steps", []):
        step_text.append(str(step.get("summary") or ""))
        step_text.extend(str(item) for item in step.get("api_calls", []))
        step_text.extend(str(item) for item in step.get("imports", []))
    return lower_join([tutorial.get("source_path"), tutorial.get("source_type"), *step_text])


def interface_matches_task(interface: dict[str, Any], task_type: str) -> bool:
    normalized = canonical_task_type(task_type)
    candidate_tasks = {canonical_task_type(str(item), "task") for item in interface.get("task_type_candidates", [])}
    if normalized in candidate_tasks:
        return True
    text = interface_text(interface)
    return any(term in text for term in task_hint_terms(normalized))


def tutorial_matches_task(tutorial: dict[str, Any], task_type: str) -> bool:
    text = tutorial_text(tutorial)
    return any(term in text for term in task_hint_terms(canonical_task_type(task_type)))


def interface_label(interface: dict[str, Any]) -> str:
    qualname = str(interface.get("qualname") or interface.get("name") or "").strip()
    signature = str(interface.get("signature") or qualname).strip()
    if qualname and "." in qualname:
        bare = qualname.rsplit(".", 1)[-1]
        if signature.startswith(f"{bare}("):
            return f"{qualname}{signature[len(bare):]}"
    return signature or qualname


def categorize_interface(interface: dict[str, Any], task_type: str) -> str:
    text = interface_text(interface)
    name = str(interface.get("qualname") or interface.get("name") or "").lower()
    task_type = canonical_task_type(task_type)
    if "setup_anndata" in text or "setup" in name or "register" in text:
        return "setup"
    if interface.get("kind") == "class" or name.endswith(".__init__") or name == "__init__":
        return "model"
    if any(term in name for term in ["train", "fit"]):
        return "train"
    if any(term in name for term in ["save", "load", "write", "read"]):
        return "persistence"
    primary_terms = task_hint_terms(task_type)
    if task_type == "perturbation_prediction" and any(term in name for term in ["predict", "delta"]):
        return "primary"
    if task_type in {"batch_removal", "integration"} and any(term in name for term in ["batch", "correct", "integrat", "transform"]):
        return "primary"
    if task_type == "cell_annotation" and any(term in name for term in ["predict", "annot", "classif", "label"]):
        return "primary"
    if task_type == "differential_analysis" and any(term in name for term in ["rank", "differential", "marker", "test"]):
        return "primary"
    if any(term in name for term in primary_terms):
        return "primary"
    if any(term in name for term in ["latent", "plot", "score", "metric", "validate", "check"]):
        return "diagnostic"
    return "support"


def selected_interfaces(interface_grounding: dict[str, Any], task_type: str) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "setup": [],
        "model": [],
        "train": [],
        "primary": [],
        "diagnostic": [],
        "persistence": [],
        "support": [],
    }
    for interface in interface_grounding.get("interfaces", []):
        if not interface_matches_task(interface, task_type):
            continue
        buckets[categorize_interface(interface, task_type)].append(interface)
    for key, values in buckets.items():
        seen = set()
        deduped = []
        for interface in values:
            label = interface_label(interface)
            if label in seen:
                continue
            seen.add(label)
            deduped.append(interface)
        buckets[key] = deduped[:6]
    return buckets


def api_candidate_to_interface(candidate: dict[str, Any]) -> dict[str, Any]:
    symbol = str(candidate.get("symbol") or "")
    return {
        "interface_id": candidate.get("api_candidate_id"),
        "kind": candidate.get("kind") or "api_candidate",
        "name": symbol.split(".")[-1],
        "qualname": symbol,
        "signature": symbol,
        "parameters": [],
        "returns": None,
        "docstring_summary": None,
        "branch_parameter_values": {},
        "source_evidence_id": candidate.get("source_evidence_id"),
        "source_path": candidate.get("source_path"),
        "task_type_candidates": candidate.get("task_type_candidates", []),
        "evidence_refs": candidate.get("evidence_refs", []),
        "confidence": candidate.get("confidence") or "api_grounding_candidate",
    }


def selected_api_interfaces(api_grounding: dict[str, Any], task_type: str) -> list[dict[str, Any]]:
    interfaces = []
    seen = set()
    for candidate in api_grounding.get("api_candidates", []):
        interface = api_candidate_to_interface(candidate)
        label = interface_label(interface)
        if label in seen or not interface_matches_task(interface, task_type):
            continue
        seen.add(label)
        interfaces.append(interface)
    return interfaces[:30]


def merge_api_interfaces(
    selected: dict[str, list[dict[str, Any]]],
    api_interfaces: list[dict[str, Any]],
    task_type: str,
) -> dict[str, list[dict[str, Any]]]:
    merged = deepcopy(selected)
    seen = {interface_label(interface) for values in merged.values() for interface in values}
    for interface in api_interfaces:
        label = interface_label(interface)
        if label in seen:
            continue
        seen.add(label)
        category = categorize_interface(interface, task_type)
        merged.setdefault(category, []).append(interface)
    for key, values in merged.items():
        merged[key] = values[:6]
    return merged


def tutorial_step_score(step: dict[str, Any], task_type: str) -> int:
    text = lower_join(
        [
            step.get("summary"),
            " ".join(str(item) for item in step.get("api_calls", [])),
            " ".join(str(item) for item in step.get("imports", [])),
        ]
    )
    terms = task_hint_terms(canonical_task_type(task_type))
    score = sum(1 for term in terms if term in text)
    if step.get("api_calls"):
        score += 2
    if any(term in text for term in ["fit", "train", "predict", "transform", "batch", "correct", "integrat"]):
        score += 1
    return score


def matched_tutorial_steps(tutorial_catalog: dict[str, Any], task_type: str, limit: int = 6) -> list[dict[str, Any]]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for tutorial in tutorial_catalog.get("tutorials", []):
        for step in tutorial.get("steps", []):
            summary = str(step.get("summary") or "").strip()
            api_calls = unique_items(step.get("api_calls", []), limit=6)
            if not api_calls:
                continue
            score = tutorial_step_score(step, task_type)
            if score <= 0:
                continue
            candidates.append(
                (
                    score,
                    {
                        "source_path": tutorial.get("source_path"),
                        "step_index": step.get("step_index"),
                        "kind": step.get("kind"),
                        "summary": summary or "code step",
                        "api_calls": api_calls,
                        "match_score": score,
                    },
                )
            )
    candidates.sort(key=lambda item: (-item[0], str(item[1].get("source_path")), int(item[1].get("step_index") or 0)))
    return [step for _score, step in candidates[:limit]]


def parameter_records_for_task(parameter_catalog: dict[str, Any], task_type: str) -> list[dict[str, Any]]:
    bucket = parameter_catalog.get("by_task_type", {}).get(task_type, {})
    records = []
    seen = set()
    for parameter in bucket.get("parameters", []):
        name = str(parameter.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        records.append(parameter)
        if len(records) >= 40:
            break
    return records


def has_anywhere(needles: list[str], interfaces: list[dict[str, Any]], tutorials: list[dict[str, Any]]) -> bool:
    text = lower_join(
        [interface_text(interface) for interface in interfaces]
        + [str(step.get("summary") or "") + " " + " ".join(step.get("api_calls", [])) for step in tutorials]
    )
    return any(needle.lower() in text for needle in needles)


def build_operational_inputs(
    task_type: str,
    parameters: list[dict[str, Any]],
    all_interfaces: list[dict[str, Any]],
    tutorial_steps: list[dict[str, Any]],
) -> list[str]:
    items = ["selected `task_type` and biological goal"]
    parameter_names = {str(parameter.get("name") or "") for parameter in parameters}
    required_parameters = [parameter for parameter in parameters if parameter.get("required")]
    if has_anywhere(["AnnData", "adata", "h5ad"], all_interfaces, tutorial_steps):
        items.append("input AnnData object or `.h5ad` path with expression matrix in the documented slot")
        items.append("confirmed `obs` metadata columns used by the selected workflow")
    for parameter in required_parameters[:8]:
        name = str(parameter.get("name") or "")
        annotation = str(parameter.get("annotation") or "").strip()
        suffix = f" ({annotation})" if annotation and annotation != "None" else ""
        items.append(f"required API parameter `{name}`{suffix}")
    if any(parameter.get("required") and parameter.get("name") in {"batch_key", "labels_key"} for parameter in parameters):
        items.append("`batch_key` column in `adata.obs` with the technical condition, batch, or condition labels")
        items.append("`labels_key` column in `adata.obs` with biological labels such as cell type")
    if task_type == "perturbation_prediction":
        items.extend(
            [
                "`ctrl_key` value for the control condition",
                "`stim_key` value for the stimulated or perturbed condition",
                "exactly one prediction target: `celltype_to_predict` or `adata_to_predict`",
            ]
        )
    if task_type in {"batch_removal", "integration"}:
        items.extend(
            [
                "batch or sample labels to remove or align",
                "biological labels or grouping metadata to preserve during diagnostics",
            ]
        )
    if task_type == "cell_annotation":
        items.append("reference labels or annotation field used for transfer/classification")
    if task_type == "differential_analysis":
        items.append("contrast groups and grouping metadata for the comparison")
    if task_type == "spatial_mapping":
        items.append("spatial coordinate fields or spatial assay metadata")
    return unique_items(items, limit=10)


def build_operational_outputs(
    task_type: str,
    all_interfaces: list[dict[str, Any]],
    tutorial_steps: list[dict[str, Any]],
) -> list[str]:
    outputs = ["machine-readable run summary with task_type, inputs, parameters, output paths, and validation status"]
    if task_type == "perturbation_prediction" or has_anywhere(["predict"], all_interfaces, tutorial_steps):
        outputs.append("predicted cells or result object returned by the documented prediction API")
        if has_anywhere(["delta"], all_interfaces, tutorial_steps):
            outputs.append("latent perturbation delta or response vector when the API returns one")
    if task_type in {"batch_removal", "integration"} or has_anywhere(["batch_removal", "corrected"], all_interfaces, tutorial_steps):
        outputs.append("corrected or integrated data object produced by the documented batch/integration API")
    if has_anywhere(["latent", "embedding"], all_interfaces, tutorial_steps):
        outputs.append("latent embeddings or corrected latent embeddings when documented")
    if has_anywhere(["plot", "reg_mean", "reg_var", "figure"], all_interfaces, tutorial_steps):
        outputs.append("diagnostic plots or metric values produced by documented plotting/diagnostic APIs")
    if has_anywhere(["save", "load"], all_interfaces, tutorial_steps):
        outputs.append("model or artifact save location when persistence is requested")
    return unique_items(outputs, limit=10)


def build_operational_validation(
    task_type: str,
    all_interfaces: list[dict[str, Any]],
    tutorial_steps: list[dict[str, Any]],
) -> list[str]:
    checks = [
        "all expected output files or objects exist",
        "outputs can be opened by the documented reader or inspected in memory",
        "reported parameters and metadata fields match the run summary",
    ]
    if has_anywhere(["AnnData", "adata", "h5ad"], all_interfaces, tutorial_steps):
        checks.extend(
            [
                "AnnData observation and variable axes remain aligned with the intended input or target subset",
                "result expression matrix has no NaN or infinite values",
            ]
        )
    if task_type == "perturbation_prediction" or has_anywhere(["predict"], all_interfaces, tutorial_steps):
        checks.append("predicted result has the expected feature axis and target metadata labels")
        if has_anywhere(["delta"], all_interfaces, tutorial_steps):
            checks.append("latent delta length matches the trained latent dimension")
    if task_type in {"batch_removal", "integration"} or has_anywhere(["batch_removal", "corrected_latent"], all_interfaces, tutorial_steps):
        checks.append("corrected object keeps the expected cell and feature dimensions")
        checks.append("latent or corrected_latent embeddings, when documented, have one row per cell")
    if has_anywhere(["reg_mean", "reg_var", "plot"], all_interfaces, tutorial_steps):
        checks.append("diagnostic plots or returned metric values are recorded, or a skipped-validation reason is reported")
    if has_anywhere(["save", "load"], all_interfaces, tutorial_steps):
        checks.append("saved model or result artifact can be reloaded when persistence is part of the request")
    checks.append("biological interpretation is reported as a sanity check unless official evidence defines a hard metric")
    return unique_items(checks, limit=12)


def build_operational_steps(
    task_type: str,
    selected: dict[str, list[dict[str, Any]]],
    required_inputs: list[str],
    outputs: list[str],
    validation: list[str],
) -> list[str]:
    steps = [
        "Confirm the selected `task_type`, input object/path, and required metadata before touching the environment.",
    ]
    setup_labels = [interface_label(interface) for interface in selected.get("setup", [])[:2]]
    model_labels = [interface_label(interface) for interface in selected.get("model", [])[:2]]
    train_labels = [interface_label(interface) for interface in selected.get("train", [])[:2]]
    primary_labels = [interface_label(interface) for interface in selected.get("primary", [])[:3]]
    diagnostic_labels = [interface_label(interface) for interface in selected.get("diagnostic", [])[:3]]
    persistence_labels = [interface_label(interface) for interface in selected.get("persistence", [])[:2]]
    if required_inputs:
        steps.append("Check required inputs: " + "; ".join(required_inputs[:4]) + ".")
    if setup_labels:
        steps.append("Register or prepare data with " + "; ".join(f"`{label}`" for label in setup_labels) + " before constructing or running the model.")
    if model_labels:
        steps.append("Construct the documented model/object with " + "; ".join(f"`{label}`" for label in model_labels) + " and record architecture/configuration changes.")
    if train_labels:
        steps.append("Train or fit with " + "; ".join(f"`{label}`" for label in train_labels) + "; record epochs, batch size, device, seed, and early-stopping choices.")
    if primary_labels:
        steps.append("Run the primary task API: " + "; ".join(f"`{label}`" for label in primary_labels) + ".")
    else:
        steps.append("Do not execute until an evidence-backed primary API for this task_type is identified.")
    if outputs:
        steps.append("Persist or return outputs: " + "; ".join(outputs[:4]) + ".")
    if diagnostic_labels:
        steps.append("Run documented diagnostics when applicable: " + "; ".join(f"`{label}`" for label in diagnostic_labels) + ".")
    if persistence_labels:
        steps.append("Use documented persistence APIs when saving reusable models or artifacts: " + "; ".join(f"`{label}`" for label in persistence_labels) + ".")
    if validation:
        steps.append("Validate before reporting success: " + "; ".join(validation[:4]) + ".")
    return unique_items(steps, limit=10)


def build_api_sequence(selected: dict[str, list[dict[str, Any]]]) -> list[str]:
    sequence = []
    for category in ("setup", "model", "train", "primary", "diagnostic", "persistence"):
        for interface in selected.get(category, [])[:4]:
            label = interface_label(interface)
            if label:
                sequence.append(f"{category}: `{label}`")
    return unique_items(sequence, limit=14)


def build_clarifying_questions(task_type: str, required_inputs: list[str]) -> list[str]:
    questions = [
        "Which input data object or file should be used?",
        "Which metadata columns correspond to the required biological or technical roles?",
    ]
    if task_type == "perturbation_prediction":
        questions.extend(
            [
                "What are the control and stimulated/perturbed condition values?",
                "Should prediction target a cell type label or a supplied unperturbed AnnData subset?",
            ]
        )
    if task_type in {"batch_removal", "integration"}:
        questions.append("Which batch labels should be removed or aligned, and which biological labels must be preserved?")
    if not required_inputs:
        questions.append("Which official tutorial/API path should define this task before execution?")
    return unique_items(questions, limit=6)


def build_task_troubleshooting(
    task_type: str,
    selected: dict[str, list[dict[str, Any]]],
    all_interfaces: list[dict[str, Any]],
    tutorial_steps: list[dict[str, Any]],
) -> list[str]:
    tips = [
        "If a required metadata column is absent or semantically unclear, stop and ask for the correct field instead of guessing.",
        "If an API signature in the installed package differs from the source-grounded signature, record the mismatch and do not silently patch upstream code.",
    ]
    if has_anywhere(["AnnData", "adata", "h5ad"], all_interfaces, tutorial_steps):
        tips.append("For AnnData inputs, verify `.obs` columns, `.var_names`, shape, and matrix dtype before training or prediction.")
    if selected.get("train"):
        tips.append("When training is slow or unstable, reduce epochs only for smoke checks and label the result as not biologically validated.")
    if task_type == "perturbation_prediction":
        tips.append("Do not pass both `celltype_to_predict` and `adata_to_predict` unless official evidence says that combination is supported.")
    if task_type in {"batch_removal", "integration"}:
        tips.append("Do not claim successful integration from visual overlap alone; report batch mixing and biological-label preservation separately.")
    return unique_items(tips, limit=8)


def build_operational_recipe(
    request: dict[str, Any],
    task: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    parameter_catalog: dict[str, Any],
) -> dict[str, Any]:
    task_type = str(task.get("task_type") or "task")
    selected = merge_api_interfaces(
        selected_interfaces(interface_grounding, task_type),
        selected_api_interfaces(api_grounding, task_type),
        task_type,
    )
    all_interfaces = [interface for values in selected.values() for interface in values]
    tutorial_steps = matched_tutorial_steps(tutorial_catalog, task_type)
    parameters = parameter_records_for_task(parameter_catalog, task_type)
    required_inputs = build_operational_inputs(task_type, parameters, all_interfaces, tutorial_steps)
    outputs = build_operational_outputs(task_type, all_interfaces, tutorial_steps)
    validation = build_operational_validation(task_type, all_interfaces, tutorial_steps)
    workflow_steps = build_operational_steps(task_type, selected, required_inputs, outputs, validation)
    primary_api_count = len(selected.get("primary", []))
    tutorial_count = len(tutorial_steps)
    evidence_refs = unique_items(
        task.get("evidence_refs", [])
        + [ref for interface in all_interfaces for ref in interface.get("evidence_refs", [])],
        limit=20,
    )
    confidence = "review_required"
    if primary_api_count and tutorial_count:
        confidence = "tutorial_and_api_grounded"
    elif primary_api_count:
        confidence = "api_grounded"
    elif tutorial_count:
        confidence = "tutorial_grounded_primary_api_missing"
    abstraction_warnings = []
    if not primary_api_count:
        abstraction_warnings.append("No task-specific primary API was selected from static interface grounding; require agent review before execution.")
    if not tutorial_count:
        abstraction_warnings.append("No matching tutorial steps were mined; keep workflow source-grounded and avoid claiming reproduction.")
    return {
        "status": "ready" if primary_api_count else "needs_agent_review",
        "confidence": confidence,
        "goal": f"Execute the evidence-backed `{task_type}` workflow for {request.get('method_name') or request.get('package_name')}.",
        "required_inputs": required_inputs,
        "workflow_steps": workflow_steps,
        "api_sequence": build_api_sequence(selected),
        "expected_outputs": outputs,
        "validation_checks": validation,
        "clarifying_questions": build_clarifying_questions(task_type, required_inputs),
        "troubleshooting": build_task_troubleshooting(task_type, selected, all_interfaces, tutorial_steps),
        "tutorial_step_hints": tutorial_steps,
        "evidence_refs": evidence_refs or task.get("evidence_refs", []),
        "abstraction_warnings": abstraction_warnings,
    }


def refine_task_contracts_with_recipe(task: dict[str, Any], recipe: dict[str, Any]) -> None:
    input_contract = task.setdefault("input_contract", {})
    output_contract = task.setdefault("output_contract", {})
    existing_inputs = [
        item for item in input_contract.get("required_from_user", []) if item not in GENERIC_REQUIRED_INPUTS
    ]
    existing_outputs = [
        item for item in output_contract.get("expected_outputs", []) if item not in GENERIC_EXPECTED_OUTPUTS
    ]
    existing_validation = [
        item for item in output_contract.get("minimum_validation", []) if item not in GENERIC_VALIDATION_CHECKS
    ]
    input_contract["required_from_user"] = unique_items(recipe.get("required_inputs", []) + existing_inputs, limit=12)
    output_contract["expected_outputs"] = unique_items(recipe.get("expected_outputs", []) + existing_outputs, limit=12)
    output_contract["minimum_validation"] = unique_items(recipe.get("validation_checks", []) + existing_validation, limit=14)
    for warning in recipe.get("abstraction_warnings", []):
        task.setdefault("review_warnings", [])
        if warning not in task["review_warnings"]:
            task["review_warnings"].append(warning)


def add_recipe_refusal_boundaries(task: dict[str, Any], recipe: dict[str, Any]) -> None:
    boundaries = task.setdefault("refusal_boundaries", [])
    reason_keys = {boundary.get("reason_key") for boundary in boundaries}
    if recipe.get("status") != "ready" and "no_source_grounded_primary_api" not in reason_keys:
        boundaries.append(
            {
                "reason_key": "no_source_grounded_primary_api",
                "refusal_type": "unsupported",
                "when": "No evidence-backed primary API was selected for this task_type.",
            }
        )
    for warning in recipe.get("abstraction_warnings", []):
        if "No matching tutorial steps" in warning and "no_task_specific_tutorial_steps" not in reason_keys:
            boundaries.append(
                {
                    "reason_key": "no_task_specific_tutorial_steps",
                    "refusal_type": "fixable",
                    "when": "The task lacks mined tutorial steps; execution may continue only from source/API evidence and must not claim tutorial reproduction.",
                }
            )
            reason_keys.add("no_task_specific_tutorial_steps")


def attach_operational_recipes(
    task_catalog: dict[str, Any],
    request: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    parameter_catalog: dict[str, Any],
) -> dict[str, Any]:
    catalog = deepcopy(task_catalog)
    for task in catalog.get("tasks", []):
        recipe = build_operational_recipe(request, task, tutorial_catalog, api_grounding, interface_grounding, parameter_catalog)
        task["operational_recipe"] = recipe
        refine_task_contracts_with_recipe(task, recipe)
        add_recipe_refusal_boundaries(task, recipe)
    return catalog


def build_task_catalog(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tasks = []
    for task_type in infer_task_types(request, sources, evidence_cards):
        execution = execution_status_for(task_type, request)
        evidence = task_evidence_record(task_type, sources, evidence_cards)
        refs = evidence["refs"]
        tasks.append(
            {
                "task_type": task_type,
                "capability_name": task_type.replace("_", " "),
                "skill_scope": "same_child_skill",
                "evidence_refs": refs,
                "evidence_support": evidence["support"],
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
