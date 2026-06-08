from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from paper2skill.common import PROJECT_ROOT
from paper2skill.generators.codex_skill_generator import build_context, example_inputs, generate_skill, plan_outputs
from paper2skill.validators.skill_validator import validate_skill


def test_generator_creates_complete_toy_python_skill(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    result = validate_skill(out)
    assert result["status"] == "pass", result
    assert (out / "references" / "algorithm_contract.yaml").exists()
    assert (out / "references" / "adapter_spec.yaml").exists()
    assert (out / "references" / "adapter_review.yaml").exists()
    assert (out / "references" / "notebook_execution_policy.json").exists()
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


def test_validate_skill_rejects_missing_or_invalid_adapter_spec(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    adapter_spec = out / "references" / "adapter_spec.yaml"
    adapter_spec.unlink()

    missing = validate_skill(out)
    assert missing["status"] == "fail"
    assert any("adapter_spec.yaml" in error for error in missing["errors"])

    out = generate_skill(context, tmp_path / "toy-python-skill-invalid")
    adapter_spec = out / "references" / "adapter_spec.yaml"
    adapter_spec.write_text(
        """
adapter_type: python_api
status: unsafe
entrypoint: null
command: null
module: toy_algorithm
function: summarize
evidence: []
caveats: []
""".lstrip(),
        encoding="utf-8",
    )

    invalid = validate_skill(out)
    assert invalid["status"] == "fail"
    assert any("adapter_spec.status" in error for error in invalid["errors"])


def test_validate_skill_accepts_reviewed_and_verified_adapter_statuses(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    adapter_spec = out / "references" / "adapter_spec.yaml"
    adapter_review = out / "references" / "adapter_review.yaml"
    spec = yaml.safe_load(adapter_spec.read_text(encoding="utf-8"))
    review = yaml.safe_load(adapter_review.read_text(encoding="utf-8"))

    spec["status"] = "reviewed"
    review.update({"status": "reviewed", "human_approved": True, "dry_run": {"status": "not_run"}, "expected_outputs": []})
    adapter_spec.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    adapter_review.write_text(yaml.safe_dump(review, sort_keys=False), encoding="utf-8")
    assert validate_skill(out)["status"] == "pass"

    spec["status"] = "verified"
    review.update({"status": "verified", "human_approved": True, "dry_run": {"status": "pass"}, "expected_outputs": ["results/summary.json"], "output_validation": {"status": "pass"}})
    adapter_spec.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    adapter_review.write_text(yaml.safe_dump(review, sort_keys=False), encoding="utf-8")
    assert validate_skill(out)["status"] == "pass"


def test_validate_skill_rejects_invalid_adapter_review_lifecycle(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    adapter_review = out / "references" / "adapter_review.yaml"
    review = yaml.safe_load(adapter_review.read_text(encoding="utf-8"))

    review.update({"status": "ready", "dry_run": {"status": "not_run"}})
    adapter_review.write_text(yaml.safe_dump(review, sort_keys=False), encoding="utf-8")

    invalid = validate_skill(out)
    assert invalid["status"] == "fail"
    assert any("adapter_review.dry_run.status" in error for error in invalid["errors"])

    review.update({"status": "verified", "dry_run": {"status": "pass"}, "expected_outputs": []})
    review.pop("output_validation", None)
    adapter_review.write_text(yaml.safe_dump(review, sort_keys=False), encoding="utf-8")

    invalid = validate_skill(out)
    assert invalid["status"] == "fail"
    assert any("adapter_review.output_validation.status" in error for error in invalid["errors"])

    review.update({"status": "verified", "dry_run": {"status": "pass"}, "expected_outputs": "results/summary.json", "output_validation": {"status": "pass"}})
    adapter_review.write_text(yaml.safe_dump(review, sort_keys=False), encoding="utf-8")

    invalid = validate_skill(out)
    assert invalid["status"] == "fail"
    assert any("adapter_review.expected_outputs: expected list" in error for error in invalid["errors"])


def test_adapter_review_human_approval_promotes_candidate_to_reviewed(tmp_path: Path):
    repo = tmp_path / "api-repo"
    package = repo / "reviewed_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .core import summarize\n", encoding="utf-8")
    (package / "core.py").write_text("def summarize(path):\n    return {'rows': 0}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='reviewed-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nReviewed Python API method.\n", encoding="utf-8")
    review = tmp_path / "adapter_review.yaml"
    review.write_text(
        """
adapter_type: python_api
status: reviewed
entrypoint: reviewed_pkg:summarize
command: null
module: reviewed_pkg
function: summarize
human_approved: true
dry_run:
  status: not_run
expected_outputs: []
evidence:
  - human_review
caveats: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))

    assert context["adapter_spec"]["status"] == "reviewed"
    assert context["adapter_spec"]["module"] == "reviewed_pkg"


def test_adapter_review_dry_run_promotes_candidate_to_ready_without_human_approval(tmp_path: Path):
    repo = tmp_path / "api-repo"
    package = repo / "ready_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .core import summarize\n", encoding="utf-8")
    (package / "core.py").write_text("def summarize(path):\n    return {'rows': 0}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='ready-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nDry-run validated Python API method.\n", encoding="utf-8")
    review = tmp_path / "adapter_review.yaml"
    review.write_text(
        """
adapter_type: python_api
status: ready
entrypoint: ready_pkg:summarize
command: null
module: ready_pkg
function: summarize
human_approved: false
dry_run:
  status: pass
expected_outputs: []
evidence:
  - dry_run
caveats: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))

    assert context["adapter_spec"]["status"] == "ready"
    assert context["adapter_spec"]["module"] == "ready_pkg"


def test_python_package_without_function_stays_candidate_not_demo_only(tmp_path: Path):
    repo = tmp_path / "class-repo"
    package = repo / "class_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .model import Model\n", encoding="utf-8")
    (package / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='class-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nPython package API method.\n", encoding="utf-8")

    context = build_context(paper=str(paper), repo=str(repo))

    assert context["adapter_spec"]["adapter_type"] == "python_api"
    assert context["adapter_spec"]["status"] == "candidate"
    assert context["adapter_spec"]["entrypoint"] is None


def test_python_package_source_without_public_api_stays_candidate(tmp_path: Path):
    repo = tmp_path / "package-repo"
    package = repo / "src" / "package_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='package-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nInstallable Python package method.\n", encoding="utf-8")

    context = build_context(paper=str(paper), repo=str(repo))

    assert context["adapter_spec"]["adapter_type"] == "python_api"
    assert context["adapter_spec"]["status"] == "candidate"
    assert context["adapter_spec"]["entrypoint"] is None


def test_python_package_metadata_with_notebook_tutorial_infers_notebook_adapter(tmp_path: Path):
    repo = tmp_path / "notebook-repo"
    notebooks = repo / "notebooks"
    notebooks.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='notebook-repo'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Tutorial\n"], "metadata": {}},
            {"cell_type": "code", "source": ["data = 'input.csv'\n"], "metadata": {}, "outputs": [], "execution_count": None},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (notebooks / "tutorial.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nNotebook-first Python method.\n", encoding="utf-8")

    context = build_context(paper=str(paper), repo=str(repo), tutorials=[str(notebooks / "tutorial.ipynb")])

    assert context["adapter_spec"]["adapter_type"] == "notebook"
    assert context["adapter_spec"]["status"] == "candidate"


def test_adapter_review_malformed_mapping_blocks_without_crashing(tmp_path: Path):
    repo = tmp_path / "api-repo"
    package = repo / "malformed_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .core import summarize\n", encoding="utf-8")
    (package / "core.py").write_text("def summarize(path):\n    return {'rows': 0}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='malformed-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nMalformed review mapping.\n", encoding="utf-8")
    review = tmp_path / "adapter_review.yaml"
    review.write_text(
        """
adapter_type: python_api
status: ready
entrypoint: malformed_pkg:summarize
command: null
module:
  - malformed_pkg
function: summarize
human_approved: false
dry_run:
  status: pass
expected_outputs: []
evidence:
  - dry_run
caveats: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))

    assert context["adapter_spec"]["status"] == "blocked"
    assert "explicit adapter mapping" in " ".join(context["adapter_spec"]["caveats"])


def test_adapter_review_requires_explicit_mapping_for_executable_status(tmp_path: Path):
    repo = tmp_path / "api-repo"
    package = repo / "reviewed_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .core import summarize\n", encoding="utf-8")
    (package / "core.py").write_text("def summarize(path):\n    return {'rows': 0}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='reviewed-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nReviewed Python API method.\n", encoding="utf-8")
    review = tmp_path / "adapter_review.yaml"
    review.write_text(
        """
adapter_type: python_api
status: reviewed
human_approved: true
dry_run:
  status: not_run
expected_outputs: []
evidence:
  - human_review
caveats: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))

    assert context["adapter_spec"]["status"] == "blocked"
    assert "explicit adapter mapping" in " ".join(context["adapter_spec"]["caveats"])


def test_adapter_review_verified_requires_output_validation(tmp_path: Path):
    repo = tmp_path / "api-repo"
    package = repo / "verified_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .core import summarize\n", encoding="utf-8")
    (package / "core.py").write_text("def summarize(path):\n    return {'rows': 0}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='verified-pkg'\nversion='0.1.0'\ndependencies=[]\n", encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nVerified Python API method.\n", encoding="utf-8")
    review = tmp_path / "adapter_review.yaml"
    review.write_text(
        """
adapter_type: python_api
status: verified
entrypoint: verified_pkg:summarize
command: null
module: verified_pkg
function: summarize
human_approved: true
dry_run:
  status: pass
expected_outputs:
  - results/summary.json
evidence:
  - human_review
caveats: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))
    assert context["adapter_spec"]["status"] == "blocked"

    review.write_text(
        review.read_text(encoding="utf-8")
        + "output_validation:\n"
        + "  status: pass\n",
        encoding="utf-8",
    )
    context = build_context(paper=str(paper), repo=str(repo), maturity_level="L2", adapter_review=str(review))
    assert context["adapter_spec"]["status"] == "verified"


def test_validate_skill_rejects_invalid_workflow_dag_and_environment_records(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    dag_path = out / "references" / "workflow_dag.json"
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    dag["nodes"][0].pop("step_id")
    dag_path.write_text(json.dumps(dag, indent=2) + "\n", encoding="utf-8")

    invalid_dag = validate_skill(out)
    assert invalid_dag["status"] == "fail"
    assert any("workflow_dag.nodes[0]" in error and "step_id" in error for error in invalid_dag["errors"])

    out = generate_skill(context, tmp_path / "toy-python-skill-invalid-env")
    env_path = out / "assets" / "environment_spec.yaml"
    env = yaml.safe_load(env_path.read_text(encoding="utf-8"))
    env["python"]["packages"] = [{"name": "missing-spec"}]
    env_path.write_text(yaml.safe_dump(env, sort_keys=False), encoding="utf-8")

    invalid_env = validate_skill(out)
    assert invalid_env["status"] == "fail"
    assert any("environment_spec.python.packages[0]" in error and "spec" in error for error in invalid_env["errors"])


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
