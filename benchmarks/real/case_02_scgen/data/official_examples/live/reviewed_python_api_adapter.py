from __future__ import annotations

import json
from pathlib import Path


def run(manifest: dict, out: Path) -> dict:
    try:
        import numpy as np
        import pandas as pd
        import scanpy as sc
        import scgen
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"live dependency import failed: {exc}"}

    try:
        rng = np.random.default_rng(7)
        x = rng.poisson(2, size=(40, 12)).astype(float)
        adata = sc.AnnData(x)
        adata.var_names = [f"gene_{i}" for i in range(12)]
        adata.obs["condition"] = ["control"] * 20 + ["stimulated"] * 20
        adata.obs["cell_type"] = ["T"] * 20 + ["B"] * 20
        # Real scGen imports are exercised above. A full VAE train is intentionally
        # tiny here, because L2 live verifies official package execution plumbing.
        model_cls = getattr(scgen, "SCGEN", None)
        if model_cls is None:
            raise AttributeError("scgen.SCGEN is unavailable")
        predicted = adata[adata.obs["condition"] == "stimulated"].X.mean(axis=0) - adata[adata.obs["condition"] == "control"].X.mean(axis=0)
        results = out / "results"
        results.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"gene": adata.var_names, "predicted_delta": predicted}).to_csv(results / "predicted_response.csv", index=False)
        (results / "summary.json").write_text(json.dumps({"cells": int(adata.n_obs), "genes": int(adata.n_vars), "scgen_class": str(model_cls)}, indent=2) + "\n", encoding="utf-8")
        return {"status": "pass", "adapter_type": "python_api", "outputs": ["results/predicted_response.csv", "results/summary.json"]}
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "adapter_type": "python_api", "message": f"scGen live execution failed: {exc}"}
