from __future__ import annotations

from typing import Any


STEP_TYPE_RULES = {
    "load_data": ["read", "read_csv", "read_h5ad", "read_10x", "read10x", "load", "import"],
    "qc": ["calculate_qc", "filter_cells", "filter_genes", "mito", "qc"],
    "filtering": ["filter", "subset"],
    "normalization": ["normalize", "normalizedata", "normalize_total"],
    "transformation": ["log1p", "lognormalize", "scale", "scaledata"],
    "feature_selection": ["highly_variable", "variablefeatures"],
    "dimensionality_reduction": ["pca", "umap", "tsne", "neighbors"],
    "clustering": ["leiden", "louvain", "findclusters"],
    "differential_expression": ["rank_genes", "findmarkers", "deseq", "edger", "limma"],
    "model_training": ["fit", "train"],
    "prediction": ["predict", "classify"],
    "visualization": ["plot", "scatter", "umap", "tsne", "savefig", "ggsave"],
    "save_output": ["write", "to_csv", "save", "saverds", "write_h5ad"],
}


def infer_workflow(tutorial_trace: dict[str, Any]) -> dict[str, Any]:
    steps = tutorial_trace.get("workflow_steps", [])
    dag = build_workflow_dag(steps)
    return {
        "steps": steps,
        "workflow_dag": dag,
        "evidence_priority": ["tutorial", "docs", "api", "dependency_files", "paper", "readme"],
    }


def build_workflow_dag(steps: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    edges = []
    last_object_producer: dict[str, str] = {}
    last_file_producer: dict[str, str] = {}
    for index, step in enumerate(steps):
        step_id = step.get("step_id") or step.get("id") or f"step_{index + 1:03d}"
        node_type = classify_step_type(step)
        input_objects = list(dict.fromkeys(step.get("input_objects", []) or []))
        output_objects = list(dict.fromkeys(step.get("output_objects", []) or []))
        input_files = list(dict.fromkeys(step.get("read_files", step.get("inputs", [])) or []))
        output_files = list(dict.fromkeys(step.get("write_files", step.get("outputs", [])) or []))
        for name in input_objects:
            producer = last_object_producer.get(name)
            if producer and producer != step_id:
                edges.append({"from": producer, "to": step_id, "reason": f"shared_object:{name}"})
        for name in input_files:
            producer = last_file_producer.get(name)
            if producer and producer != step_id:
                edges.append({"from": producer, "to": step_id, "reason": f"shared_file:{name}"})
        for name in output_objects:
            last_object_producer[name] = step_id
        for name in output_files:
            last_file_producer[name] = step_id
        nodes.append(
            {
                "step_id": step_id,
                "type": node_type,
                "language": step.get("language", "unknown"),
                "source": step.get("source"),
                "input_files": input_files,
                "output_files": output_files,
                "input_objects": input_objects,
                "output_objects": output_objects,
                "object_state_after": object_state_after(step, output_objects or input_objects, node_type),
                "parameters": step.get("parameters", {}),
                "evidence": [step.get("evidence_id") or step_id],
                "confidence": step.get("confidence", "medium"),
            }
        )
    return {"nodes": nodes, "edges": dedupe_edges(edges)}


def classify_step_type(step: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            str(step.get("description", "")),
            str(step.get("command_or_code", "")),
            " ".join(str(value) for value in step.get("function_calls", []) or []),
            " ".join(str(value) for value in step.get("bio_signals", []) or []),
        ]
    ).lower()
    for step_type, words in STEP_TYPE_RULES.items():
        if any(word.lower() in haystack for word in words):
            return step_type
    if step.get("write_files") or step.get("outputs"):
        return "save_output"
    if step.get("read_files") or step.get("inputs"):
        return "load_data"
    return "other"


def object_state_after(step: dict[str, Any], objects: list[str], node_type: str) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    signals = set(step.get("bio_signals", []) or [])
    for name in objects:
        value: dict[str, Any] = {}
        if "single_cell" in signals:
            value["modality"] = "scRNA-seq"
        if node_type == "load_data" or "raw_counts" in signals:
            value["matrix_state"] = "raw_counts"
        if node_type == "normalization" or "normalization" in signals:
            value["matrix_state"] = "normalized"
        if node_type == "transformation" or "log_transform" in signals:
            value["matrix_state"] = "log1p"
        if value:
            state[name] = value
    return state


def dedupe_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["reason"])
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result
