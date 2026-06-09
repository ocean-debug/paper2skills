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
    expr_path = ROOT / str(primary.get("path"))
    meta_path = ROOT / str(metadata.get("path"))
    cell_type_col = str(parameters.get("cell_type_col") or "cell.type")
    label_col = str(parameters.get("label_col") or "condition")
    expression = read_expression(expr_path)
    rows = read_metadata(meta_path)
    auc_rows = auc_like_table(expression, rows, cell_type_col, label_col)
    results_dir = out / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    auc_path = results_dir / "augur_auc.csv"
    with auc_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cell_type", "auc"])
        writer.writeheader()
        writer.writerows(auc_rows)
    summary = {"rows": len(auc_rows), "auc_min": min(row["auc"] for row in auc_rows), "auc_max": max(row["auc"] for row in auc_rows)}
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "pass",
        "adapter_type": "cli",
        "message": "Reviewed L2 dry-run adapter executed on minimal scRNA fixture.",
        "outputs": ["results/augur_auc.csv", "results/summary.json"],
    }


def read_expression(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["gene"]: {cell: float(value) for cell, value in row.items() if cell != "gene"} for row in reader}


def read_metadata(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def auc_like_table(expression: dict[str, dict[str, float]], rows: list[dict[str, str]], cell_type_col: str, label_col: str) -> list[dict[str, float | str]]:
    result = []
    for cell_type in sorted({row[cell_type_col] for row in rows}):
        cells = [row for row in rows if row[cell_type_col] == cell_type]
        labels = sorted({row[label_col] for row in cells})
        if len(labels) < 2:
            score = 0.5
        else:
            first = [row["cell"] for row in cells if row[label_col] == labels[0]]
            second = [row["cell"] for row in cells if row[label_col] == labels[1]]
            diffs = []
            for values in expression.values():
                left = sum(values[cell] for cell in first) / len(first)
                right = sum(values[cell] for cell in second) / len(second)
                diffs.append(abs(left - right))
            score = min(1.0, 0.5 + (sum(diffs) / len(diffs)) / 20.0)
        result.append({"cell_type": cell_type, "auc": round(score, 4)})
    return result
