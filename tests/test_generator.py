from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from paper2skill.common import PROJECT_ROOT
from paper2skill.generators.codex_skill_generator import build_context, example_inputs, generate_skill, plan_outputs
from paper2skill.validators.skill_validator import validate_skill


def test_generator_creates_complete_toy_python_skill(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    result = validate_skill(out)
    assert result["status"] == "pass", result
    assert (out / "references" / "algorithm_contract.yaml").exists()
    assert (out / "references" / "bio_contract.yaml").exists()
    assert (out / "references" / "workflow_dag.json").exists()
    assert (out / "scripts" / "adapters" / "python_api_adapter.py").exists()


def test_generator_creates_toy_r_skill(tmp_path: Path):
    context = build_context(**example_inputs("toy_r"))
    out = generate_skill(context, tmp_path / "toy-r-skill")
    result = validate_skill(out)
    assert result["status"] == "pass", result
    assert (out / "assets" / "environment_spec.yaml").exists()


def test_generated_public_files_do_not_include_absolute_paths(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    assert_no_absolute_path_markers(out)


def test_generated_dependency_assets_redact_local_file_urls(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    private_dep = "localpkg @ file:///tmp/paper2skill-private/localpkg"
    context["environment_spec"]["python"]["packages"] = [{"spec": private_dep, "required": True}]
    context["environment_report"]["python"]["packages"] = [{"name": private_dep, "import_name": "localpkg", "installed": False, "required": True}]
    out = generate_skill(context, tmp_path / "toy-python-skill")
    plan = plan_outputs(context, tmp_path / "plan")
    public_text = "\n".join(
        [
            (out / "assets" / "requirements.txt").read_text(encoding="utf-8"),
            (out / "assets" / "environment.yml").read_text(encoding="utf-8"),
            (out / "assets" / "environment_spec.yaml").read_text(encoding="utf-8"),
            (out / "references" / "environment_report.json").read_text(encoding="utf-8"),
            (plan / "environment_report.json").read_text(encoding="utf-8"),
        ]
    )
    assert "file:///tmp/paper2skill-private" not in public_text
    assert "/tmp/paper2skill-private" not in public_text
    assert "localpkg" in public_text


def test_generated_environment_yml_uses_pip_section_for_python_specs(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    context["environment_spec"]["python"]["packages"] = [{"spec": "scikit-learn==1.4.0", "required": True}]
    out = generate_skill(context, tmp_path / "toy-python-skill")
    environment_yml = (out / "assets" / "environment.yml").read_text(encoding="utf-8")
    requirements_txt = (out / "assets" / "requirements.txt").read_text(encoding="utf-8")
    assert "- pip:" in environment_yml
    assert "  - scikit-learn==1.4.0" in environment_yml
    assert "scikit-learn==1.4.0" in requirements_txt


def test_plan_outputs_do_not_include_absolute_paths(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = plan_outputs(context, tmp_path / "plan")
    assert_no_absolute_path_markers(out)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for file:// remote build")
def test_remote_file_repo_build_uses_cloned_path_for_mining(tmp_path: Path):
    repo = tmp_path / "remote-source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, text=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True, text=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True, text=True, capture_output=True)
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nWe used scRNA-seq data.\n", encoding="utf-8")
    (repo / "docs").mkdir()
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# PBMC tutorial\n"], "metadata": {}},
            {"cell_type": "code", "source": ["import scanpy as sc\nadata = sc.read_10x_mtx('data/')\n"], "metadata": {}, "outputs": [], "execution_count": None},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (repo / "docs" / "pbmc.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='remote-demo'\nversion='0.1.0'\ndependencies=['scanpy']\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, text=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, text=True, capture_output=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()

    context = build_context(
        paper=str(paper),
        repo=repo.as_uri(),
        repo_ref=sha,
        collection_dir=tmp_path / "collection",
        no_execute_tutorials=True,
    )
    manifest = context["source_manifest"]["repo"]["manifest"]
    assert manifest["clone_status"] == "cloned"
    assert manifest["requested_ref"] == sha
    assert manifest["commit_sha"] == sha
    assert "scanpy" in context["dependency_evidence"]["python"]
    assert context["tutorial_trace"]["workflow_steps"]
    out = generate_skill(context, tmp_path / "skill")
    written_manifest = json.loads((out / "references" / "repo_manifest.json").read_text(encoding="utf-8"))
    assert written_manifest["commit_sha"] == sha
    assert "pyproject.toml" in (out / "references" / "repo_index.json").read_text(encoding="utf-8")


def test_generate_skill_does_not_collect_repo_again(tmp_path: Path, monkeypatch):
    context = build_context(**example_inputs("toy_python"))

    def fail_collect(*_args, **_kwargs):
        raise AssertionError("generate_skill must not collect repos")

    monkeypatch.setattr("paper2skill.generators.codex_skill_generator.collect_repo", fail_collect)
    out = generate_skill(context, tmp_path / "skill")
    assert (out / "references" / "repo_manifest.json").exists()


def test_skip_repo_clone_disables_remote_repo_mining(tmp_path: Path):
    context = build_context(repo="https://example.invalid/demo.git", skip_repo_clone=True, collection_dir=tmp_path / "collection")
    repo = context["source_manifest"]["repo"]
    assert repo["manifest"]["clone_status"] == "skipped"
    assert context["dependency_evidence"]["python"] == []
    assert "remote repo clone was skipped" in " ".join(context["warnings"])


def test_tutorial_filter_changes_candidates_and_trace(tmp_path: Path):
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
    context = build_context(repo=str(repo), tutorial_filter="pbmc")
    candidates = context["tutorial_trace"]["tutorial_candidates"]
    assert [item["path"] for item in candidates] == ["docs/pbmc.ipynb"]
    assert context["tutorial_trace"]["tutorials"][0]["path"] == "docs/pbmc.ipynb"


def assert_no_absolute_path_markers(root: Path) -> None:
    markers = {
        str(PROJECT_ROOT),
        str(PROJECT_ROOT).replace("\\", "/"),
        "/home/",
        "\\Users\\",
        "C:\\",
        "D:\\",
    }
    leaks = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker and marker in text:
                leaks.append(f"{path.relative_to(root)} contains {marker}")
    assert leaks == []
