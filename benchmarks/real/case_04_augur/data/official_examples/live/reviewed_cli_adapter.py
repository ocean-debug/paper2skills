from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run(manifest: dict, out: Path) -> dict:
    script = out / "run_augur_live.R"
    results = out / "results"
    results.mkdir(parents=True, exist_ok=True)
    script.write_text(
        r'''
library(Augur)
set.seed(1)
n_genes <- 12
n_cells <- 80
expr <- matrix(rpois(n_genes * n_cells, lambda = 5), nrow = n_genes)
rownames(expr) <- paste0("gene", seq_len(n_genes))
colnames(expr) <- paste0("cell", seq_len(n_cells))
cell_type <- rep(c("T", "B"), each = 40)
condition <- rep(rep(c("ctrl", "stim"), each = 20), times = 2)
expr[1:3, condition == "stim" & cell_type == "T"] <- expr[1:3, condition == "stim" & cell_type == "T"] + 5
expr[4:6, condition == "stim" & cell_type == "B"] <- expr[4:6, condition == "stim" & cell_type == "B"] + 3
meta <- data.frame(cell=colnames(expr), cell.type=cell_type, condition=condition)
rownames(meta) <- meta$cell
augur <- tryCatch(
  calculate_auc(expr, meta, cell_type_col="cell.type", label_col="condition", n_threads=1, n_subsamples=2, subsample_size=20),
  error=function(e) {
    if (grepl("unused argument", conditionMessage(e))) {
      calculate_auc(expr, meta, cell_type_col="cell.type", label_col="condition", n_threads=1)
    } else {
      stop(e)
    }
  }
)
auc <- augur$AUC
write.csv(auc, file="results/augur_auc.csv", row.names=FALSE)
write('{"status":"pass"}', file="results/summary.json")
''',
        encoding="utf-8",
    )
    completed = subprocess.run(["Rscript", str(script)], cwd=out, text=True, capture_output=True, check=False, timeout=600)
    if completed.returncode != 0:
        return {"status": "blocked", "adapter_type": "cli", "message": "Augur live Rscript failed", "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]}
    return {"status": "pass", "adapter_type": "cli", "outputs": ["results/augur_auc.csv", "results/summary.json"]}
