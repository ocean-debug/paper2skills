from __future__ import annotations

from pathlib import Path

from paper2skill.miners.api_miner import r_namespace_imports
from paper2skill.miners.script_miner import mine_script


def test_python_script_trace_extracts_imports_calls_and_paths():
    trace = mine_script("tests/fixtures/toy_script.py")
    assert trace["language"] == "python"
    assert "csv" in trace["imports"]
    assert "data/demo_input.csv" in trace["parameters"].values()
    assert trace["workflow_steps"]


def test_r_script_trace_extracts_library_and_io():
    trace = mine_script("tests/fixtures/toy_script.R")
    assert trace["language"] == "r"
    assert "stats" in trace["imports"]
    assert "data/demo_input.csv" in trace["file_reads"]
    assert "results/summary.csv" in trace["file_writes"]


def test_r_script_trace_extracts_namespace_calls_file_path_and_source(tmp_path: Path):
    script = tmp_path / "analysis.R"
    script.write_text(
        """
library(Seurat)
source("R/helpers.R")
data_dir <- "data"
out_dir <- "results"
input_file <- file.path(data_dir, "pbmc.rds")
obj <- Seurat::Read10X(input_file)
saveRDS(obj, file.path(out_dir, "pbmc.rds"))
ggsave(file.path(out_dir, "umap.png"))
""".strip()
        + "\n",
        encoding="utf-8",
    )

    trace = mine_script(script)

    assert "Seurat" in trace["imports"]
    assert "R/helpers.R" in trace["source_files"]
    assert "data/pbmc.rds" in trace["file_reads"]
    assert "results/pbmc.rds" in trace["file_writes"]
    assert "results/umap.png" in trace["file_writes"]
    assert any(call["package"] == "Seurat" and call["function"] == "Read10X" for call in trace["function_calls"])


def test_r_namespace_imports_exports_and_s3_methods(tmp_path: Path):
    namespace = tmp_path / "NAMESPACE"
    namespace.write_text(
        """
import(Seurat)
importFrom(DESeq2, DESeqDataSetFromMatrix, results)
export(run_demo)
S3method(plot, demo)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    parsed = r_namespace_imports(tmp_path)

    assert {"package": "Seurat", "source": "NAMESPACE:import"} in parsed["imports"]
    assert {"package": "DESeq2", "function": "results", "source": "NAMESPACE:importFrom"} in parsed["import_from"]
    assert {"name": "run_demo", "source": "NAMESPACE:export"} in parsed["exports"]
    assert {"generic": "plot", "class": "demo", "source": "NAMESPACE:S3method"} in parsed["s3methods"]
