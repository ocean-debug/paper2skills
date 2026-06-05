from __future__ import annotations

import json
from pathlib import Path

from paper2skill.miners.notebook_miner import mine_notebook


def test_notebook_trace_includes_ordered_code_cells():
    trace = mine_notebook("tests/fixtures/toy_notebook.ipynb")
    code_cells = [cell for cell in trace["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert code_cells[0]["index"] == 1
    assert "csv" in code_cells[0]["imports"]
    assert trace["workflow_steps"][0]["evidence_id"].endswith("cell:1")


def test_notebook_trace_detects_magic_parameters_paths_and_policy(tmp_path: Path):
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["input_dir = 'data'\noutput_file = 'results/out.csv'\n"],
                "metadata": {"tags": ["parameters"]},
                "outputs": [],
            },
            {"cell_type": "code", "source": ["!pip install scanpy\n!wget https://example.org/data.h5ad\n"], "metadata": {}, "outputs": []},
            {"cell_type": "code", "source": ["%%R\nlibrary(Seurat)\nobj <- readRDS('data/pbmc.rds')\nsaveRDS(obj, 'results/pbmc.rds')\n"], "metadata": {}, "outputs": []},
            {"cell_type": "code", "source": ["%%capture\nimport pandas as pd\ncaptured = input_dir + '/captured.csv'\ndf = pd.read_csv(captured)\n"], "metadata": {}, "outputs": []},
            {"cell_type": "code", "source": ["%%html\n<div>not python</div>\n"], "metadata": {}, "outputs": []},
            {"cell_type": "code", "source": ["path = input_dir + '/matrix.csv'\ndef load():\n    return pd.read_csv(path)\n"], "metadata": {}, "outputs": [{"output_type": "display_data", "data": {"image/png": "x" * 200000}}]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = tmp_path / "rich.ipynb"
    path.write_text(json.dumps(notebook), encoding="utf-8")

    trace = mine_notebook(path)

    policy = trace["execution_policy"]
    assert policy["will_execute"] is False
    assert policy["parameter_cells"] == [0]
    assert policy["shell_magics"][0]["command"].startswith("pip install")
    assert policy["cell_magics"][0]["magic"] == "R"
    assert any(item["magic"] == "capture" for item in policy["cell_magics"])
    assert any(item["magic"] == "html" for item in policy["cell_magics"])
    assert "install_command" in policy["risks"]
    assert "network_download" in policy["risks"]
    assert "large_output" in policy["risks"]
    assert trace["parameters"]["input_dir"] == "data"
    assert any(step["language"] == "r" and "data/pbmc.rds" in step["read_files"] for step in trace["workflow_steps"])
    assert any("data/captured.csv" in step["read_files"] and "pandas" in step["imports"] for step in trace["workflow_steps"])
    assert not any("<div>not python</div>" in step["command_or_code"] for step in trace["workflow_steps"])
    assert any("data/matrix.csv" in step["read_files"] for step in trace["workflow_steps"])
