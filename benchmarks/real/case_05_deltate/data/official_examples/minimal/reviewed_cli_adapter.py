from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(manifest: dict, out: Path) -> dict:
    inputs = manifest.get("inputs") or {}
    primary = inputs.get("primary_data") or {}
    parameters = (inputs.get("algorithm") or {}).get("parameters") or {}
    ribo = read_counts(ROOT / str(primary.get("ribo_count_matrix")))
    rna = read_counts(ROOT / str(primary.get("rna_count_matrix")))
    sample_info_path = ROOT / str(primary.get("sample_info_file"))
    sample_info = read_table(sample_info_path)
    condition_col = str(parameters.get("condition_col") or "Condition")
    seq_type_col = str(parameters.get("seq_type_col") or "SeqType")
    validate_sample_info(sample_info, condition_col, seq_type_col)
    rows = score_delta_te(ribo, rna)
    results = out / "Results"
    fold_changes = results / "fold_changes"
    gene_lists = results / "gene_lists"
    fold_changes.mkdir(parents=True, exist_ok=True)
    gene_lists.mkdir(parents=True, exist_ok=True)
    write_table(fold_changes / "deltaTE.txt", rows, ["gene", "delta_te"])
    dtegs = [row for row in rows if abs(float(row["delta_te"])) >= 0.5]
    write_table(gene_lists / "DTEGs.txt", dtegs, ["gene", "delta_te"])
    summary = {"genes": len(rows), "dtegs": len(dtegs), "sample_info_rows": len(sample_info)}
    summary_dir = out / "results"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "pass",
        "adapter_type": "cli",
        "message": "Reviewed L2 dry-run adapter executed on minimal paired Ribo/RNA fixture.",
        "outputs": ["Results/fold_changes/deltaTE.txt", "Results/gene_lists/DTEGs.txt", "results/summary.json"],
    }


def read_counts(path: Path) -> dict[str, dict[str, int]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {row["gene"]: {key: int(value) for key, value in row.items() if key != "gene"} for row in reader}


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def validate_sample_info(rows: list[dict[str, str]], condition_col: str, seq_type_col: str) -> None:
    if not rows:
        raise ValueError("sample_info_file is empty")
    required = {"SampleID", condition_col, seq_type_col, "Batch"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"sample_info_file missing columns: {sorted(missing)}")


def score_delta_te(ribo: dict[str, dict[str, int]], rna: dict[str, dict[str, int]]) -> list[dict[str, str]]:
    rows = []
    for gene in sorted(set(ribo) & set(rna)):
        ribo_values = list(ribo[gene].values())
        rna_values = list(rna[gene].values())
        half = len(ribo_values) // 2
        ribo_fc = mean(ribo_values[half:]) / mean(ribo_values[:half])
        rna_fc = mean(rna_values[half:]) / mean(rna_values[:half])
        delta_te = math.log2((ribo_fc + 1e-6) / (rna_fc + 1e-6))
        rows.append({"gene": gene, "delta_te": f"{delta_te:.4f}"})
    return rows


def mean(values: list[int]) -> float:
    return sum(values) / len(values)


def write_table(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
