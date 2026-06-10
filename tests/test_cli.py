from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_cli_help_available():
    result = subprocess.run([sys.executable, "-m", "paper2skill.cli", "--help"], text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert "plan" in result.stdout
    assert "build" in result.stdout


def test_cli_build_toy_python(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    result = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "SKILL.md").exists()
    assert (out / "scripts" / "preflight.py").exists()
    validation = json.loads((out / "build_validation" / "build_validation.json").read_text(encoding="utf-8"))
    assert validation["validation_depth"] == "dry_run"
    assert validation["benchmark_score"] is None
    assert validation["diagnostic_only"] is True


def test_cli_build_live_execute_validation_depth_is_nonzero_until_supported(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    result = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out), "--validation-depth", "live_execute"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    validation = json.loads((out / "build_validation" / "build_validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "unsupported"
    assert "validation_depth_unsupported" in validation["errors"]


def test_cli_build_skip_repo_clone_records_warning(tmp_path: Path):
    out = tmp_path / "skip-clone-skill"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paper2skill.cli",
            "build",
            "--repo",
            "https://example.invalid/demo.git",
            "--skip-repo-clone",
            "--out",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out / "references" / "repo_manifest.json").read_text(encoding="utf-8"))
    report = json.loads((out / "references" / "build_report.json").read_text(encoding="utf-8"))
    assert manifest["clone_status"] == "skipped"
    assert "remote repo clone was skipped" in " ".join(report["warnings"])


def test_cli_tutorial_filter_changes_generated_trace(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    for name in ["pbmc", "other"]:
        notebook = {
            "cells": [
                {"cell_type": "markdown", "source": [f"# {name} tutorial\n"], "metadata": {}},
                {"cell_type": "code", "source": ["print('x')\n"], "metadata": {}, "outputs": [], "execution_count": None},
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        (repo / "docs" / f"{name}.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
    out = tmp_path / "filtered-skill"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paper2skill.cli",
            "build",
            "--repo",
            str(repo),
            "--tutorial-filter",
            "pbmc",
            "--no-execute-tutorials",
            "--out",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    candidates = json.loads((out / "references" / "tutorial_candidates.json").read_text(encoding="utf-8"))
    trace = json.loads((out / "references" / "tutorial_trace.json").read_text(encoding="utf-8"))
    report = json.loads((out / "references" / "build_report.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in candidates] == ["docs/pbmc.ipynb"]
    assert trace["tutorial_execution_status"] == "not_executed_by_policy"
    assert report["tutorial_execution_status"] == "not_executed_by_policy"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for repo-ref CLI testing")
def test_cli_repo_ref_is_used_for_file_remote_repo(tmp_path: Path):
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nDemo.\n", encoding="utf-8")
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, text=True, capture_output=True)
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\ndependencies=['scanpy']\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, text=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, text=True, capture_output=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()
    out = tmp_path / "ref-skill"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paper2skill.cli",
            "build",
            "--paper",
            str(paper),
            "--repo",
            repo.as_uri(),
            "--repo-ref",
            sha,
            "--out",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out / "references" / "repo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["requested_ref"] == sha
    assert manifest["commit_sha"] == sha
