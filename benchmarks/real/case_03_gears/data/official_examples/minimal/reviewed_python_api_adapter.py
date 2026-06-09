from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(manifest: dict, out: Path) -> dict:
    inputs = manifest.get("inputs") or {}
    primary = inputs.get("primary_data") or {}
    parameters = (inputs.get("algorithm") or {}).get("parameters") or {}
    expression = read_expression(ROOT / str(primary.get("expression_matrix") or primary.get("path")))
    observations = read_table(ROOT / str(primary.get("obs")))
    var_rows = read_table(ROOT / str(primary.get("var")))
    condition_key = str(parameters.get("condition_key") or "condition")
    perturbation_query = [str(item) for item in parameters.get("perturbation_query") or []]
    rows = predict_perturbation(expression, observations, var_rows, condition_key, perturbation_query)

    results_dir = out / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    write_csv(results_dir / "perturbation_prediction.csv", rows, ["gene", "baseline_expression", "predicted_expression", "query"])
    summary = {"genes": len(rows), "query": perturbation_query, "cells": len(observations)}
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "pass",
        "adapter_type": "python_api",
        "message": "Reviewed L2 smoke adapter executed on minimal GEARS-like perturb-seq fixture.",
        "outputs": ["results/perturbation_prediction.csv", "results/summary.json"],
    }


def read_expression(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["gene"]: {cell: float(value) for cell, value in row.items() if cell != "gene"} for row in reader}


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def predict_perturbation(
    expression: dict[str, dict[str, float]],
    observations: list[dict[str, str]],
    var_rows: list[dict[str, str]],
    condition_key: str,
    perturbation_query: list[str],
) -> list[dict[str, str]]:
    control_cells = [row["cell"] for row in observations if row.get(condition_key) in {"ctrl", "control"}]
    perturbed_cells = [row["cell"] for row in observations if row.get(condition_key) in set(perturbation_query)]
    query_strength = len(perturbation_query) or 1
    rows = []
    for var in var_rows:
        gene = var.get("gene_name") or var.get("gene")
        if not gene or gene not in expression:
            continue
        baseline = mean([expression[gene][cell] for cell in control_cells])
        observed_delta = mean([expression[gene][cell] for cell in perturbed_cells]) - baseline if perturbed_cells else 0.0
        direct_bonus = 1.0 if gene in perturbation_query else 0.0
        predicted = baseline + observed_delta / query_strength + direct_bonus
        rows.append(
            {
                "gene": gene,
                "baseline_expression": f"{baseline:.4f}",
                "predicted_expression": f"{predicted:.4f}",
                "query": "+".join(perturbation_query),
            }
        )
    return rows


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
