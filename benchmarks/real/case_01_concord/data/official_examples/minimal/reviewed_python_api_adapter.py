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
    expression = read_expression(ROOT / str(primary.get("expression_matrix") or primary.get("path")))
    observations = read_table(ROOT / str(metadata.get("path")))
    domain_key = str(parameters.get("domain_key") or "batch")
    obsm_key = str(parameters.get("output_obsm_key") or "Concord")
    rows = concord_like_embedding(expression, observations, domain_key)

    results_dir = out / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    write_csv(results_dir / "concord_embedding.csv", rows, ["cell", "Concord_1", "Concord_2", domain_key])
    summary = {"cells": len(rows), "dimensions": 2, "obsm_key": obsm_key, "domain_key": domain_key}
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "pass",
        "adapter_type": "python_api",
        "message": "Reviewed L2 smoke adapter executed on minimal CONCORD-like fixture.",
        "outputs": ["results/concord_embedding.csv", "results/summary.json"],
    }


def read_expression(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["gene"]: {cell: float(value) for cell, value in row.items() if cell != "gene"} for row in reader}


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def concord_like_embedding(expression: dict[str, dict[str, float]], observations: list[dict[str, str]], domain_key: str) -> list[dict[str, str]]:
    genes = sorted(expression)
    global_mean = mean([value for values in expression.values() for value in values.values()])
    offsets = batch_offsets(expression, observations, domain_key, global_mean)
    rows = []
    for obs in observations:
        cell = obs["cell"]
        corrected = [expression[gene][cell] - offsets.get(obs.get(domain_key, ""), 0.0) for gene in genes]
        rows.append(
            {
                "cell": cell,
                "Concord_1": f"{mean(corrected):.4f}",
                "Concord_2": f"{corrected[0] - corrected[-1]:.4f}",
                domain_key: obs.get(domain_key, ""),
            }
        )
    return rows


def batch_offsets(expression: dict[str, dict[str, float]], observations: list[dict[str, str]], domain_key: str, global_mean: float) -> dict[str, float]:
    offsets = {}
    for domain in sorted({row.get(domain_key, "") for row in observations}):
        cells = [row["cell"] for row in observations if row.get(domain_key, "") == domain]
        values = [expression[gene][cell] for gene in expression for cell in cells]
        offsets[domain] = mean(values) - global_mean
    return offsets


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
