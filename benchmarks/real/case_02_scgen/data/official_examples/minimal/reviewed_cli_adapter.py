from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(manifest: dict, out: Path) -> dict:
    inputs = manifest.get("inputs") or {}
    primary = inputs.get("primary_data") or {}
    metadata = inputs.get("metadata") or {}
    parameters = (inputs.get("algorithm") or {}).get("parameters") or {}
    workflow = str(parameters.get("workflow") or "perturbation_prediction")
    expression = read_expression(ROOT / str(primary.get("expression_matrix") or primary.get("path")))
    observations = read_table(ROOT / str(metadata.get("path")))
    results_dir = out / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if workflow == "batch_removal":
        outputs = write_batch_removed_embedding(results_dir, expression, observations, str(parameters.get("batch_key") or "batch"))
    else:
        outputs = write_perturbation_prediction(
            results_dir,
            expression,
            observations,
            condition_key=str(parameters.get("condition_key") or "condition"),
            control_label=str(parameters.get("control_label") or "control"),
            target_label=str(parameters.get("target_label") or "stimulated"),
        )

    summary = {"workflow": workflow, "genes": len(expression), "cells": len(observations), "outputs": outputs}
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "pass",
        "adapter_type": "python_api",
        "message": "Reviewed L2 smoke adapter executed on minimal scGen-like fixture.",
        "outputs": outputs + ["results/summary.json"],
    }


def read_expression(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["gene"]: {cell: float(value) for cell, value in row.items() if cell != "gene"} for row in reader}


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_perturbation_prediction(
    results_dir: Path,
    expression: dict[str, dict[str, float]],
    observations: list[dict[str, str]],
    *,
    condition_key: str,
    control_label: str,
    target_label: str,
) -> list[str]:
    control_cells = [row["cell"] for row in observations if row.get(condition_key) == control_label]
    target_cells = [row["cell"] for row in observations if row.get(condition_key) == target_label]
    rows = []
    for gene, values in sorted(expression.items()):
        control_mean = mean([values[cell] for cell in control_cells])
        target_mean = mean([values[cell] for cell in target_cells])
        rows.append({"gene": gene, "control_mean": f"{control_mean:.4f}", "predicted_target_mean": f"{target_mean:.4f}", "predicted_delta": f"{target_mean - control_mean:.4f}"})
    write_csv(results_dir / "predicted_response.csv", rows, ["gene", "control_mean", "predicted_target_mean", "predicted_delta"])
    return ["results/predicted_response.csv"]


def write_batch_removed_embedding(results_dir: Path, expression: dict[str, dict[str, float]], observations: list[dict[str, str]], batch_key: str) -> list[str]:
    gene_names = sorted(expression)
    rows = []
    batch_offsets = batch_mean_offsets(expression, observations, batch_key)
    for obs in observations:
        cell = obs["cell"]
        corrected = [expression[gene][cell] - batch_offsets.get(obs.get(batch_key, ""), 0.0) for gene in gene_names]
        rows.append({"cell": cell, "embedding_1": f"{mean(corrected):.4f}", "embedding_2": f"{corrected[0] - corrected[-1]:.4f}", "batch": obs.get(batch_key, "")})
    write_csv(results_dir / "batch_corrected_representation.csv", rows, ["cell", "embedding_1", "embedding_2", "batch"])
    return ["results/batch_corrected_representation.csv"]


def batch_mean_offsets(expression: dict[str, dict[str, float]], observations: list[dict[str, str]], batch_key: str) -> dict[str, float]:
    global_mean = mean([value for gene_values in expression.values() for value in gene_values.values()])
    offsets = {}
    for batch in sorted({row.get(batch_key, "") for row in observations}):
        cells = [row["cell"] for row in observations if row.get(batch_key, "") == batch]
        values = [expression[gene][cell] for gene in expression for cell in cells]
        offsets[batch] = mean(values) - global_mean
    return offsets


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
