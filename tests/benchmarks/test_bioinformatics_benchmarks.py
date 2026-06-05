from __future__ import annotations

import json
from pathlib import Path

import yaml

from paper2skill.generators.codex_skill_generator import build_context, generate_skill
from paper2skill.validators.skill_validator import validate_skill


def test_scanpy_10x_benchmark_generates_contracts_and_adapter_spec(tmp_path: Path):
    repo = tmp_path / "scanpy_repo"
    (repo / "docs").mkdir(parents=True)
    write_notebook(repo / "docs" / "pbmc.ipynb", "import scanpy as sc\nadata = sc.read_10x_mtx('data/')\nsc.pp.normalize_total(adata)\nsc.pp.log1p(adata)\n")
    (repo / "pyproject.toml").write_text("[project]\nname='scanpy-demo'\nversion='0.1.0'\ndependencies=['scanpy']\n", encoding="utf-8")

    out = build_benchmark_skill(tmp_path, repo)

    assert validate_skill(out)["status"] == "pass"
    env = yaml.safe_load((out / "assets" / "environment_spec.yaml").read_text(encoding="utf-8"))
    io_contract = yaml.safe_load((out / "references" / "io_contract.yaml").read_text(encoding="utf-8"))
    dag = json.loads((out / "references" / "workflow_dag.json").read_text(encoding="utf-8"))
    adapter = yaml.safe_load((out / "references" / "adapter_spec.yaml").read_text(encoding="utf-8"))
    assert env["python"]["packages"][0]["name"] == "scanpy"
    assert io_contract["input_contract"]["required"]["primary_data"]["format"]["value"] == "10x_mtx"
    assert dag["nodes"]
    assert adapter["status"] in {"candidate", "demo_only"}


def test_seurat_rds_benchmark_generates_r_contracts(tmp_path: Path):
    repo = tmp_path / "seurat_repo"
    (repo / "examples").mkdir(parents=True)
    (repo / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\nImports: Seurat\n", encoding="utf-8")
    (repo / "examples" / "demo.R").write_text("library(Seurat)\nobj <- readRDS('input.rds')\nobj <- NormalizeData(obj)\n", encoding="utf-8")

    out = build_benchmark_skill(tmp_path, repo)

    assert validate_skill(out)["status"] == "pass"
    env = yaml.safe_load((out / "assets" / "environment_spec.yaml").read_text(encoding="utf-8"))
    io_contract = yaml.safe_load((out / "references" / "io_contract.yaml").read_text(encoding="utf-8"))
    assert env["r"]["required"] is True
    assert env["r"]["packages"][0]["name"] == "Seurat"
    assert io_contract["input_contract"]["required"]["primary_data"]["format"]["value"] == "rds"


def test_deseq_count_matrix_benchmark_keeps_bioconductor_dependency_required(tmp_path: Path):
    repo = tmp_path / "deseq_repo"
    (repo / "examples").mkdir(parents=True)
    (repo / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\nImports: DESeq2\nSuggests: testthat\n", encoding="utf-8")
    (repo / "examples" / "demo.R").write_text("library(DESeq2)\ncounts <- read.csv('counts.csv')\n", encoding="utf-8")

    out = build_benchmark_skill(tmp_path, repo)

    env = yaml.safe_load((out / "assets" / "environment_spec.yaml").read_text(encoding="utf-8"))
    dep_names = [item["name"] for item in env["r"]["packages"]]
    assert "DESeq2" in dep_names
    assert "testthat" not in dep_names
    assert validate_skill(out)["status"] == "pass"


def test_python_cli_benchmark_marks_adapter_candidate(tmp_path: Path):
    repo = tmp_path / "cli_repo"
    package = repo / "demo_cli"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo-cli'\nversion='0.1.0'\ndependencies=[]\n[project.scripts]\ndemo-cli='demo_cli.cli:main'\n",
        encoding="utf-8",
    )

    out = build_benchmark_skill(tmp_path, repo)

    adapter = yaml.safe_load((out / "references" / "adapter_spec.yaml").read_text(encoding="utf-8"))
    assert adapter["adapter_type"] == "cli"
    assert adapter["status"] == "candidate"
    assert validate_skill(out)["status"] == "pass"


def test_workflow_engine_benchmark_marks_adapter_candidate(tmp_path: Path):
    repo = tmp_path / "workflow_repo"
    repo.mkdir()
    (repo / "Snakefile").write_text("rule all:\n    input: 'results/done.txt'\n", encoding="utf-8")

    out = build_benchmark_skill(tmp_path, repo)

    adapter = yaml.safe_load((out / "references" / "adapter_spec.yaml").read_text(encoding="utf-8"))
    assert adapter["adapter_type"] == "workflow_engine"
    assert adapter["status"] == "candidate"
    assert validate_skill(out)["status"] == "pass"


def build_benchmark_skill(tmp_path: Path, repo: Path) -> Path:
    paper = tmp_path / f"{repo.name}_paper.md"
    paper.write_text("# Methods\n\nBenchmark method with official tutorial evidence.\n", encoding="utf-8")
    context = build_context(paper=str(paper), repo=str(repo), no_execute_tutorials=True)
    return generate_skill(context, tmp_path / f"{repo.name}_skill")


def write_notebook(path: Path, source: str) -> None:
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Tutorial\n"], "metadata": {}},
            {"cell_type": "code", "source": [source], "metadata": {}, "outputs": [], "execution_count": None},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
