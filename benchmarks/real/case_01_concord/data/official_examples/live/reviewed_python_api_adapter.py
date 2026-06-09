from __future__ import annotations

import json
from pathlib import Path


def run(manifest: dict, out: Path) -> dict:
    try:
        import numpy as np
        import pandas as pd
        import scanpy as sc
        import concord as ccd
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"live dependency import failed: {exc}"}

    try:
        adata = sc.datasets.pbmc3k_processed()
        if adata.n_obs > 300:
            adata = adata[:300].copy()
        adata.obs["batch"] = np.where(np.arange(adata.n_obs) % 2 == 0, "batch1", "batch2")
        if hasattr(ccd, "Concord"):
            model = ccd.Concord()
            embedding = model.fit_transform(adata)
        else:
            raise AttributeError("concord.Concord is unavailable")
        if embedding is None:
            embedding = adata.obsm.get("Concord")
        if embedding is None:
            raise RuntimeError("CONCORD did not return or store an embedding")
        adata.obsm["Concord"] = embedding
        results = out / "results"
        results.mkdir(parents=True, exist_ok=True)
        rows = pd.DataFrame(embedding[:, : min(2, embedding.shape[1])], index=adata.obs_names)
        rows.columns = [f"Concord_{i + 1}" for i in range(rows.shape[1])]
        rows.insert(0, "cell", rows.index)
        rows.to_csv(results / "concord_embedding.csv", index=False)
        (results / "summary.json").write_text(json.dumps({"cells": int(adata.n_obs), "dimensions": int(embedding.shape[1])}, indent=2) + "\n", encoding="utf-8")
        return {"status": "pass", "adapter_type": "python_api", "outputs": ["results/concord_embedding.csv", "results/summary.json"]}
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"CONCORD live execution failed: {exc}"}
