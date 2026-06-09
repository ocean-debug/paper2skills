from __future__ import annotations

import json
import subprocess
from pathlib import Path

from paper2skill.env_rebuilder.__main__ import main
from paper2skill.env_rebuilder.env_paths import resolve_env_path, uv_python_executable
from paper2skill.env_rebuilder.executor import apply_install_plan
from paper2skill.env_rebuilder.lockfile import export_lock_artifacts
from paper2skill.env_rebuilder.planner import plan_environment, plan_from_install_request
from paper2skill.env_rebuilder.repair import diagnose_failure
from paper2skill.env_rebuilder.scanner import scan_repo, select_python_version


def test_scan_repo_detects_environment_files_and_install_hints(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.11"\n', encoding="utf-8")
    (repo / "requirements.txt").write_text("torch\nscanpy\n", encoding="utf-8")
    (repo / "environment.yml").write_text("name: demo\ndependencies:\n- python=3.11\n", encoding="utf-8")
    (repo / "renv.lock").write_text("{}", encoding="utf-8")
    (repo / "DESCRIPTION").write_text("Imports:\n    DESeq2,\n    ggplot2\n", encoding="utf-8")
    (repo / "README.md").write_text("Install with `pip install demo-tool` and CUDA torch.", encoding="utf-8")
    (repo / "Snakefile").write_text("rule all:\n  input: []\n", encoding="utf-8")
    (repo / "setup.cfg").write_text("[metadata]\nname = setup-demo\n[options]\npython_requires = >=3.10\ninstall_requires =\n    h5py\n", encoding="utf-8")
    (repo / "Dockerfile").write_text("RUN mamba install -y -c conda-forge snakemake\n", encoding="utf-8")
    (repo / "NAMESPACE").write_text("importFrom(Matrix, Matrix)\n", encoding="utf-8")
    (repo / "install.R").write_text("BiocManager::install(c('SingleCellExperiment'))\n", encoding="utf-8")

    scan = scan_repo(repo)

    names = {item["name"] for item in scan["environment_files"]}
    assert {"pyproject.toml", "requirements.txt", "environment.yml", "renv.lock", "DESCRIPTION"} <= names
    assert scan["python"]["project_name"] == "demo"
    assert scan["python"]["selected_python"] == "3.11"
    assert scan["r"]["has_r"] is True
    assert "DESeq2" in scan["r"]["description_packages"]
    assert "Matrix" in scan["r"]["namespace_packages"]
    assert "SingleCellExperiment" in scan["r"]["install_r_packages"]
    assert scan["gpu"]["uses_torch"] is True
    assert scan["workflow_engines"][0]["engine"] == "snakemake"
    assert any(command["source"] == "Dockerfile" and command["kind"] == "conda" for command in scan["install_commands"])


def test_plan_environment_prioritizes_lockfiles_and_conda_for_r_stack(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "renv.lock").write_text("{}", encoding="utf-8")
    (repo / "DESCRIPTION").write_text("Imports:\n    DESeq2,\n    apeglm\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    assert plan["manager"] == "conda"
    assert plan["commands"][0]["kind"] == "conda_env_create"
    assert any(command["kind"] == "lockfile_restore" and command["tier"] == 1 for command in plan["commands"])
    r_commands = [command for command in plan["commands"] if command["kind"] == "r_bioc_conda_packages"]
    assert r_commands
    assert "bioconductor-deseq2" in r_commands[0]["packages"]
    assert "bioconductor-apeglm" in r_commands[0]["packages"]


def test_plan_environment_uses_uv_for_python_torch_cuda(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "torch-demo"\nrequires-python = ">=3.10"\n', encoding="utf-8")
    (repo / "README.md").write_text("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env=".venv", torch_backend="cu128")

    assert plan["manager"] == "uv"
    assert plan["commands"][0]["kind"] == "uv_venv_create"
    torch_commands = [command for command in plan["commands"] if command["kind"] == "readme_uv_pip_install"]
    assert torch_commands
    assert "--torch-backend=cu128" in torch_commands[0]["command"]
    assert "--python" in torch_commands[0]["command"]


def test_plan_from_install_request_layers_conda_uv_and_github_plan_only():
    request = {
        "conda_channels": ["conda-forge", "bioconda"],
        "missing_python_packages": ["scanpy", "paper-only"],
        "missing_r_packages": ["DESeq2"],
        "missing_executables": ["Rscript", "git"],
        "r_github_packages": ["neurorestore/Augur"],
    }

    plan = plan_from_install_request(request, target="new", env="p2s_l2_case", allow_github_install="ask")

    assert plan["status"] == "blocked_manual"
    assert plan["manager"] == "conda+uv"
    conda_packages = [command for command in plan["commands"] if command["kind"] == "conda_packages"][0]["packages"]
    assert "bioconductor-deseq2" in conda_packages
    assert "scanpy" in conda_packages
    uv_command = [command for command in plan["commands"] if command["kind"] == "uv_python_packages"][0]["command"]
    assert uv_command[:5] == ["conda", "run", "-n", "p2s_l2_case", "uv"]
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["approved_for_execution"] is False
    assert plan["manual_approval_required"] is True


def test_plan_from_install_request_allows_github_only_when_approved():
    request = {"r_github_packages": ["neurorestore/Augur"]}

    plan = plan_from_install_request(request, target="new", env="p2s_l2_case", allow_github_install="approved")

    assert plan["status"] == "ready"
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["approved_for_execution"] is True


def test_uv_env_name_resolves_under_skill_benchmark_envs(tmp_path: Path):
    resolved = resolve_env_path("p2s_l2_demo", tmp_path)

    assert resolved == str(tmp_path / ".benchmark" / "envs" / "p2s_l2_demo")
    assert uv_python_executable(resolved).endswith("p2s_l2_demo/bin/python") or uv_python_executable(resolved).endswith("p2s_l2_demo\\Scripts\\python")


def test_plan_from_install_request_uses_resolved_uv_path(tmp_path: Path):
    env_path = resolve_env_path("p2s_l2_demo", tmp_path)

    plan = plan_from_install_request({"missing_python_packages": ["paper-only"]}, target="new", env="p2s_l2_demo", env_path=env_path)

    assert plan["manager"] == "uv"
    assert plan["resolved_env_path"] == env_path
    assert plan["commands"][0]["command"][-1] == env_path
    assert plan["commands"][1]["command"][:4] == ["uv", "pip", "install", "--python"]
    assert plan["commands"][1]["command"][4] == env_path


def test_existing_env_plan_only_installs_missing_diff():
    request = {
        "missing_python_packages": ["scanpy", "paper-only"],
        "missing_r_packages": ["DESeq2", "ggplot2"],
        "missing_executables": ["Rscript", "snakemake"],
        "installed_python_packages": ["scanpy"],
        "installed_r_packages": ["ggplot2"],
        "available_executables": ["Rscript"],
    }

    plan = plan_from_install_request(request, target="existing", env="p2s_l2_case")

    all_packages = [package for command in plan["commands"] for package in command.get("packages") or []]
    assert "scanpy" not in all_packages
    assert "r-ggplot2" not in all_packages
    assert "r-base" not in all_packages
    assert "paper-only" in all_packages
    assert "bioconductor-deseq2" in all_packages
    assert "snakemake" in all_packages
    assert plan["existing_environment_diff"]["mode"] == "preflight_missing_diff"


def test_unknown_r_package_becomes_manual_block():
    plan = plan_from_install_request({"missing_r_packages": ["unknownRpkg"]}, target="new", env="p2s_l2_case")

    assert plan["status"] == "blocked_manual"
    manual = [command for command in plan["commands"] if command["kind"] == "manual_r_package"]
    assert manual and manual[0]["packages"] == ["unknownRpkg"]


def test_mamba_missing_falls_back_to_conda(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "mamba":
            raise FileNotFoundError("mamba")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    plan = {
        "status": "ready",
        "env": "p2s_l2_case",
        "commands": [
            {
                "kind": "conda_packages",
                "installer": "mamba_or_conda",
                "packages": ["numpy"],
                "command": ["mamba", "install", "-y", "-n", "p2s_l2_case", "numpy"],
                "fallback_command": ["conda", "install", "-y", "-n", "p2s_l2_case", "numpy"],
            }
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "executed"
    assert calls[0][0] == "mamba"
    assert calls[1][0] == "conda"
    assert report["execution_results"][0]["used_fallback"] is True
    assert report["execution_results"][0]["primary_failed"]["error_type"] == "executable_not_found"


def test_apply_install_plan_with_no_commands_is_noop_success():
    report = apply_install_plan({"status": "ready", "env": "p2s_l2_case", "commands": []}, yes=True)

    assert report["status"] == "executed"
    assert report["auto_install_performed"] is False
    assert report["execution_results"] == []


def test_export_lock_writes_partial_structured_report(tmp_path: Path, monkeypatch):
    def fake_run(command, **kwargs):
        if command[:3] == ["conda", "env", "export"]:
            return subprocess.CompletedProcess(command, 0, stdout="name: demo\n", stderr="")
        raise FileNotFoundError(command[0])

    monkeypatch.setattr("paper2skill.env_rebuilder.lockfile.subprocess.run", fake_run)

    report = export_lock_artifacts("p2s_l2_demo", tmp_path / "lock", manager="conda")

    assert report["status"] == "partial"
    assert (tmp_path / "lock" / "environment.yml").exists()
    assert (tmp_path / "lock" / "lock_export_report.json").exists()
    assert any(item["exit_code"] == 127 for item in report["results"])


def test_repair_diagnoses_common_bio_environment_failures():
    report = diagnose_failure(
        {
            "stderr": (
                "metadata-generation-failed: meson build error\n"
                "Error in library(DESeq2): there is no package called 'DESeq2'\n"
                "CUDA driver version is insufficient\n"
                "No matching distribution found for demo_pkg\n"
            )
        }
    )

    modes = {item["failure_mode"] for item in report["findings"]}
    assert "python_source_build_failure" in modes
    assert "missing_r_package" in modes
    assert "cuda_mismatch" in modes
    assert "pypi_package_unavailable" in modes


def test_cli_scan_plan_repair_and_export_lock_write_json(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("torch\n", encoding="utf-8")
    scan_out = tmp_path / "scan.json"
    plan_out = tmp_path / "plan.json"
    failure = tmp_path / "failure.json"
    failure.write_text(json.dumps({"stderr": "failed building wheel for scikit-misc: meson"}), encoding="utf-8")
    repair_out = tmp_path / "repair.json"
    lock_out = tmp_path / "lock_plan.json"

    def fake_export_lock_artifacts(env, out, **kwargs):
        return {
            "status": "partial",
            "env": env,
            "out": str(out),
            "dry_run": False,
            "auto_export_performed": True,
            "results": [{"kind": "conda_env_export", "exit_code": 0}],
        }

    monkeypatch.setattr("paper2skill.env_rebuilder.__main__.export_lock_artifacts", fake_export_lock_artifacts)

    assert main(["scan", "--repo", str(repo), "--out", str(scan_out)]) == 0
    assert main(["plan", "--scan", str(scan_out), "--target", "new", "--env", ".venv", "--out", str(plan_out)]) == 0
    assert main(["repair", "--failure-report", str(failure), "--out", str(repair_out)]) == 0
    assert main(["export-lock", "--env", "p2s_l2_demo", "--out", str(tmp_path / "lock"), "--plan-out", str(lock_out)]) == 0
    assert json.loads(scan_out.read_text(encoding="utf-8"))["status"] == "scanned"
    assert json.loads(plan_out.read_text(encoding="utf-8"))["status"] == "ready"
    assert json.loads(repair_out.read_text(encoding="utf-8"))["status"] == "repair_plan_available"
    assert json.loads(lock_out.read_text(encoding="utf-8"))["status"] == "partial"


def test_select_python_version_respects_minimum_310():
    assert select_python_version(">=3.8") == "3.10"
    assert select_python_version("==3.9") == "3.10"
    assert select_python_version(">=3.11") == "3.11"
    assert select_python_version(">=3.8,<3.11") == "3.10"
