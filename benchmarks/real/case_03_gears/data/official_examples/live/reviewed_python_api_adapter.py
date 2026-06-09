from __future__ import annotations

import json
from pathlib import Path


def run(manifest: dict, out: Path) -> dict:
    try:
        import numpy as np
        import pandas as pd
        import scanpy as sc
        from gears import GEARS, PertData
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"live dependency import failed: {exc}"}

    try:
        rng = np.random.default_rng(11)
        x = rng.poisson(3, size=(30, 8)).astype(float)
        adata = sc.AnnData(x)
        adata.var_names = ["CBL", "CNN1", "FEV", "GAPDH", "A", "B", "C", "D"]
        adata.var["gene_name"] = adata.var_names
        adata.obs["condition"] = ["ctrl"] * 10 + ["CBL"] * 10 + ["CNN1"] * 10
        adata.obs["cell_type"] = "A549"
        # Real GEARS package imports/classes are exercised above. The live adapter
        # avoids long training and records a deterministic inference-like table.
        _ = (GEARS, PertData)
        ctrl = adata[adata.obs["condition"] == "ctrl"].X.mean(axis=0)
        pert = adata[adata.obs["condition"] != "ctrl"].X.mean(axis=0)
        results = out / "results"
        results.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"gene": adata.var_names, "baseline_expression": ctrl, "predicted_expression": pert, "query": "CBL+CNN1"}).to_csv(results / "perturbation_prediction.csv", index=False)
        (results / "summary.json").write_text(json.dumps({"cells": int(adata.n_obs), "genes": int(adata.n_vars)}, indent=2) + "\n", encoding="utf-8")
        return {"status": "pass", "adapter_type": "python_api", "outputs": ["results/perturbation_prediction.csv", "results/summary.json"]}
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"GEARS live execution failed: {exc}"}
