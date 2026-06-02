from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_three_stage_build_outputs_evidence_bundle(tmp_path: Path):
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nWe used single-cell RNA data and Read10X.\n", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Tutorial\n"], "metadata": {}},
            {
                "cell_type": "code",
                "source": ["import scanpy as sc\nadata = sc.read_10x_mtx('data/')\nsc.pp.normalize_total(adata)\n"],
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (repo / "docs" / "tutorial.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\ndependencies=['scanpy']\n", encoding="utf-8")
    out = tmp_path / "skill"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paper2skill.cli",
            "build",
            "--paper",
            str(paper),
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--no-execute-tutorials",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for rel in [
        "SKILL.md",
        "references/paper.md",
        "references/paper_sections.json",
        "references/repo_manifest.json",
        "references/repo_index.json",
        "references/tutorial_candidates.json",
        "references/tutorial_trace.json",
        "references/evidence_graph.json",
        "references/bio_contract.yaml",
        "references/io_contract.yaml",
    ]:
        assert (out / rel).exists(), rel
