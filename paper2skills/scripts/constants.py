"""Shared constants for the Papert2Skills builder."""

from __future__ import annotations

SCHEMA_VERSION = "papert2skills.v0.1"
BUILDER_VERSION = "papert2skills-builder.v0.1"

EVIDENCE_PRIORITY = [
    "execution_trace",
    "official_tutorial_or_docs",
    "source_code_or_api",
    "paper",
]

REQUIRED_CHILD_REFERENCES = [
    "task-types.md",
    "input-output-contracts.md",
    "limitations-and-refusal.md",
    "validation.md",
    "troubleshooting.md",
    "evidence.md",
    "environment.md",
]

EXECUTION_SUCCESS_STATUSES = {"pass", "passed", "ok", "success", "verified"}

TASK_HEURISTICS = {
    "preprocessing": [
        "preprocess",
        "qc",
        "quality control",
        "filter",
        "normalize",
        "normalization",
    ],
    "integration": [
        "integration",
        "integrate",
        "batch",
        "harmon",
        "alignment",
        "correct",
    ],
    "multiomics_integration": [
        "multiomics",
        "multi-omics",
        "multiome",
        "rna+atac",
        "atac",
        "cite",
        "totalvi",
        "multivi",
    ],
    "cell_annotation": [
        "annotation",
        "annotate",
        "label",
        "classification",
        "classifier",
        "reference mapping",
        "query",
    ],
    "trajectory": [
        "trajectory",
        "pseudotime",
        "lineage",
        "velocity",
        "fate",
        "differentiation",
    ],
    "differential_analysis": [
        "differential",
        "marker",
        "markers",
        "deg",
        "de gene",
        "rank_genes",
    ],
    "perturbation_prediction": [
        "perturb",
        "counterfactual",
        "stim",
        "response",
        "intervention",
    ],
    "spatial_mapping": [
        "spatial",
        "visium",
        "slide",
        "coordinate",
        "mapping",
    ],
    "visualization": [
        "visual",
        "plot",
        "umap",
        "embedding",
        "heatmap",
    ],
}

TEXT_FILE_SUFFIXES = {
    ".md",
    ".rst",
    ".txt",
    ".py",
    ".r",
    ".R",
    ".ipynb",
    ".html",
    ".htm",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
}

DEFAULT_MAX_FETCH_BYTES = 5_000_000
DEFAULT_MAX_INDEX_BYTES = 250_000
DEFAULT_MAX_INDEX_FILES = 500

CLAIM_KEYWORDS = {
    "input_contract": [
        "AnnData",
        "h5ad",
        "loom",
        "csv",
        "matrix",
        "count",
        "metadata",
        "batch_key",
        "labels_key",
        "condition",
        "obs",
        "var",
    ],
    "output_contract": [
        "write",
        "save",
        "output",
        "result",
        "embedding",
        "latent",
        "prediction",
        "plot",
        "figure",
        "csv",
        "h5ad",
    ],
    "api_entrypoint": [
        "fit",
        "train",
        "predict",
        "transform",
        "run",
        "main",
        "model",
        "class",
        "def ",
    ],
    "environment_requirement": [
        "pip install",
        "conda install",
        "requirements",
        "environment",
        "python",
        "torch",
        "cuda",
        "gpu",
    ],
    "validation_rule": [
        "assert",
        "check",
        "validate",
        "shape",
        "exists",
        "load",
        "read",
    ],
    "refusal_boundary": [
        "requires",
        "must",
        "only",
        "not support",
        "unsupported",
        "cannot",
        "should not",
    ],
}
