from __future__ import annotations

import json
import subprocess
from pathlib import Path

from paper2skill.env_rebuilder.__main__ import main
from paper2skill.env_rebuilder.canonical_env import derive_canonical_environment, trust_lockfiles
from paper2skill.env_rebuilder.env_paths import resolve_env_path, uv_python_executable
from paper2skill.env_rebuilder.executor import apply_install_plan, run_command_with_fallback
from paper2skill.env_rebuilder.lockfile import export_lock_artifacts
from paper2skill.env_rebuilder.planner import build_bio_env_plan, environment_probe_command, plan_environment, plan_from_install_request
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
    assert scan["r"]["description_suggests"] == []
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
    assert plan["commands"][0]["kind"] in {"conda_env_create", "derived_conda_environment"}
    assert not any(command["kind"] == "lockfile_restore" and command.get("installer") == "renv" for command in plan["commands"])
    r_commands = [command for command in plan["commands"] if command["kind"] == "r_bioc_conda_packages"]
    assert r_commands
    assert "bioconductor-deseq2" in r_commands[0]["packages"]
    assert "bioconductor-apeglm" in r_commands[0]["packages"]
    assert plan["lock_trust"]["blocked"][0]["name"] == "renv.lock"


def test_plan_environment_routes_torch_cuda_to_manual_special_route(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "torch-demo"\nrequires-python = ">=3.10"\n', encoding="utf-8")
    (repo / "README.md").write_text("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env=".venv", torch_backend="cu128")

    torch_commands = [command for command in plan["commands"] if command["kind"] == "manual_special_route"]
    assert torch_commands
    assert torch_commands[0]["special_route"]["route"] == "special_torch"
    assert torch_commands[0]["manual_approval_required"] is True


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
    assert "--strict-channel-priority" in [token for command in plan["commands"] for token in command.get("command", [])]
    uv_command = [command for command in plan["commands"] if command["kind"] == "uv_python_packages"][0]["command"]
    assert uv_command[:5] == ["conda", "run", "-n", "p2s_l2_case", "uv"]
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["approved_for_execution"] is False
    assert plan["manual_approval_required"] is True


def test_plan_from_install_request_allows_github_only_when_approved():
    request = {"r_github_packages": ["neurorestore/Augur"]}

    plan = plan_from_install_request(request, target="new", env="p2s_l2_case", allow_github_install="approved")

    assert plan["status"] == "ready"
    assert plan["manager"] == "conda"
    assert plan["needs_r_runtime"] is True
    assert plan["r_runtime_reason"] == "r_github_install"
    assert plan["conda_packages_added"] == ["r-base", "r-remotes"]
    conda_packages = [package for command in plan["commands"] if command["kind"] == "conda_packages" for package in command.get("packages") or []]
    assert "r-base" in conda_packages
    assert "r-remotes" in conda_packages
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["approved_for_execution"] is True


def test_bio_env_r_github_only_approved_requires_conda_r_runtime(tmp_path: Path):
    skill = tmp_path / "skill"
    skill.mkdir()

    plan = build_bio_env_plan(
        skill_dir=skill,
        install_request={"r_github_packages": ["owner/pkg"]},
        target="new",
        env="p2s_l2_case",
        allow_github_install="approved",
    )

    assert plan["status"] == "ready"
    assert plan["manager"] == "conda"
    assert plan["needs_r_runtime"] is True
    assert plan["r_runtime_reason"] == "r_github_install"
    assert plan["conda_packages_added"] == ["r-base", "r-remotes"]
    assert plan["layers"]["needs_r_runtime"] is True
    assert plan["layers"]["r_runtime_reason"] == "r_github_install"
    runtime = [command for command in plan["commands"] if command["kind"] == "r_runtime_conda_packages"]
    assert runtime
    assert runtime[0]["packages"] == ["r-base", "r-remotes"]
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["approved_for_execution"] is True
    assert github["command"][:5] == ["conda", "run", "-n", "p2s_l2_case", "Rscript"]


def test_bio_env_r_github_only_unapproved_stays_manual_without_conda_runtime(tmp_path: Path):
    skill = tmp_path / "skill"
    skill.mkdir()

    plan = build_bio_env_plan(
        skill_dir=skill,
        install_request={"r_github_packages": ["owner/pkg"]},
        target="new",
        env="p2s_l2_case",
        allow_github_install="ask",
    )

    assert plan["status"] == "blocked_manual"
    assert plan["manager"] == "uv"
    assert plan["needs_r_runtime"] is False
    assert plan["r_runtime_reason"] is None
    assert plan["conda_packages_added"] == []
    assert not any(command["kind"] == "r_runtime_conda_packages" for command in plan["commands"])
    assert not any(command["kind"] == "conda_env_create" for command in plan["commands"])
    github = [command for command in plan["commands"] if command["kind"] == "r_github_packages"][0]
    assert github["manual_approval_required"] is True


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


def test_pep508_marker_python_spec_stays_in_uv_segment(tmp_path: Path):
    env_path = resolve_env_path("p2s_l2_demo", tmp_path)

    plan = plan_from_install_request(
        {"missing_python_packages": ['paper-only>=1.0; python_version >= "3.10"']},
        target="new",
        env="p2s_l2_demo",
        env_path=env_path,
    )

    uv_commands = [command for command in plan["commands"] if command["kind"] == "uv_python_packages"]
    assert uv_commands
    assert 'paper-only>=1.0; python_version >= "3.10"' in uv_commands[0]["packages"]
    assert not any(command["kind"] == "manual_special_route" for command in plan["commands"])


def test_compiled_pep508_marker_routes_to_conda_without_marker():
    plan = plan_from_install_request(
        {"missing_python_packages": ['scanpy>=1.10; python_version >= "3.10"']},
        target="new",
        env="p2s_l2_case",
    )

    conda_packages = [package for command in plan["commands"] if command["kind"] == "conda_packages" for package in command.get("packages") or []]
    assert "scanpy>=1.10" in conda_packages
    assert all(";" not in package and "python_version" not in package for package in conda_packages)
    migrations = plan["route_resolution"]["python"]["migrations"]
    assert migrations[0]["dropped_marker"] == 'python_version >= "3.10"'


def test_compiled_pep508_extras_routes_to_conda_without_extras():
    plan = plan_from_install_request({"missing_python_packages": ["scanpy[leiden]>=1.10"]}, target="new", env="p2s_l2_case")

    conda_packages = [package for command in plan["commands"] if command["kind"] == "conda_packages" for package in command.get("packages") or []]
    assert "scanpy>=1.10" in conda_packages
    assert all("[" not in package and "]" not in package for package in conda_packages)
    migrations = plan["route_resolution"]["python"]["migrations"]
    assert migrations[0]["dropped_extras"] == ["leiden"]


def test_direct_url_and_vcs_python_requirements_require_manual_approval():
    request = {
        "missing_python_packages": [
            "mypkg @ https://example.com/pkg.whl",
            "https://example.com/other.whl",
            "git+https://github.com/example/pkg.git",
        ]
    }

    plan = plan_from_install_request(request, target="new", env="p2s_l2_case")

    assert plan["status"] == "blocked_manual"
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])
    manual_blocks = plan["route_resolution"]["python"]["manual"]
    assert {item["type"] for item in manual_blocks} == {"direct_url_requirement", "vcs_requirement"}
    assert all(item["manual_approval_required"] for item in manual_blocks)


def test_approved_direct_url_requirement_enters_uv_segment():
    url_req = "mypkg @ https://example.com/pkg.whl"
    plan = plan_from_install_request(
        {
            "missing_python_packages": [url_req],
            "install_approval": {
                "python_direct_urls": [{"url": "https://example.com/pkg.whl", "hashes": ["sha256:abc"]}],
                "approval_source": "reviewed_adapter",
                "reason": "reviewed wheel URL",
            },
        },
        target="new",
        env="p2s_l2_case",
    )

    assert plan["status"] == "ready"
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert url_req in uv_packages
    assert plan["route_resolution"]["python"]["manual"] == []
    assert plan["route_resolution"]["python"]["approved_urls"][0]["approval_source"] == "reviewed_adapter"


def test_install_approval_merges_skill_and_request_sources(tmp_path: Path):
    skill = tmp_path / "skill"
    approval_dir = skill / "assets" / "env"
    approval_dir.mkdir(parents=True)
    (approval_dir / "approved_install_sources.yaml").write_text(
        """
approval_source: generated_skill_review
python_direct_urls:
  - url: https://example.com/skill.whl
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_bio_env_plan(
        skill_dir=skill,
        install_request={
            "missing_python_packages": [
                "skillpkg @ https://example.com/skill.whl",
                "casepkg @ https://example.com/case.whl",
            ],
            "install_approval": {
                "approval_source": "case_reviewed_adapter",
                "python_direct_urls": [{"url": "https://example.com/case.whl"}],
            },
        },
        target="new",
        env="p2s_l2_case",
    )

    urls = {record["url"]: record["approval_source"] for record in plan["install_approval"]["python_direct_urls"]}
    assert urls == {
        "https://example.com/skill.whl": "generated_skill_review",
        "https://example.com/case.whl": "case_reviewed_adapter",
    }
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "skillpkg @ https://example.com/skill.whl" in uv_packages
    assert "casepkg @ https://example.com/case.whl" in uv_packages
    assert plan["manual_blocks"] == []


def test_readme_direct_url_install_requires_approval(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("Install with `pip install mypkg @ https://example.com/pkg.whl`.\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    assert plan["status"] == "blocked_manual"
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])
    assert any((block.get("special_route") or block).get("type") == "direct_url_requirement" for block in plan["manual_blocks"])


def test_unapproved_url_with_similar_prefix_stays_manual_block():
    plan = plan_from_install_request(
        {
            "missing_python_packages": ["https://example.com/pkg-extra.whl"],
            "install_approval": {"python_direct_urls": [{"url": "https://example.com/pkg.whl"}]},
        },
        target="new",
        env="p2s_l2_case",
    )

    assert plan["status"] == "blocked_manual"
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])
    assert plan["route_resolution"]["python"]["manual"][0]["type"] == "direct_url_requirement"


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


def test_existing_env_diff_matches_pep508_extras_and_normalized_names():
    request = {
        "missing_python_packages": ["scanpy[leiden]>=1.10", "scikit_learn>=1.4"],
        "installed_python_packages": [
            {"name": "scanpy", "version": "1.10.0"},
            {"name": "scikit-learn", "version": "1.4.0"},
        ],
    }

    plan = plan_from_install_request(request, target="existing", env="p2s_l2_case")

    all_packages = [package for command in plan["commands"] for package in command.get("packages") or []]
    assert "scanpy>=1.10" not in all_packages
    assert "scikit-learn>=1.4" not in all_packages
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])


def test_existing_env_plan_without_probe_is_diagnostic_only():
    scan = {
        "repo": "repo",
        "signals": {"has_conda_spec": True},
        "case_install_request": {
            "conda_packages": ["numpy"],
            "missing_python_packages": ["scanpy"],
            "missing_r_packages": ["DESeq2"],
            "missing_executables": ["Rscript"],
        },
    }

    plan = plan_environment(scan, target="existing", env="p2s_l2_case")

    assert plan["status"] == "blocked_diagnostic"
    assert plan["mode"] == "existing_inventory_probe_required"
    assert [command["kind"] for command in plan["commands"]] == ["environment_inventory_probe"]
    assert not any(command["kind"] in {"derived_conda_environment_update", "conda_packages", "uv_python_packages"} for command in plan["commands"])


def test_blocked_diagnostic_inventory_probe_can_execute(monkeypatch):
    payload = {
        "probe_type": "package_inventory",
        "inventory_complete": True,
        "installed_python_packages": ["scanpy"],
        "installed_r_packages": [],
        "installed_conda_packages": ["python"],
    }

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    plan = {
        "status": "blocked_diagnostic",
        "target": "existing",
        "env": "p2s_l2_case",
        "commands": [
            {
                "kind": "environment_inventory_probe",
                "installer": "probe",
                "command": ["conda", "run", "-n", "p2s_l2_case", "python", "-c", "probe"],
            }
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "diagnostic_executed"
    assert report["auto_install_performed"] is True
    assert report["execution_results"][0]["probe"]["probe_type"] == "package_inventory"


def test_existing_env_plan_with_activation_only_probe_is_still_diagnostic():
    scan = {
        "repo": "repo",
        "signals": {},
        "case_install_request": {
            "missing_python_packages": ["scanpy"],
        },
        "environment_probe": {
            "sys_executable": "/env/bin/python",
            "which_python": "/env/bin/python",
        },
    }

    plan = plan_environment(scan, target="existing", env="p2s_l2_case")

    assert plan["status"] == "blocked_diagnostic"
    assert plan["mode"] == "existing_inventory_probe_required"
    assert [command["kind"] for command in plan["commands"]] == ["environment_inventory_probe"]


def test_existing_env_plan_with_package_inventory_probe_installs_only_missing_diff():
    scan = {
        "repo": "repo",
        "signals": {},
        "case_install_request": {
            "missing_python_packages": ["scanpy", "paper-only"],
            "missing_r_packages": ["DESeq2", "ggplot2"],
            "missing_executables": ["Rscript", "snakemake"],
        },
        "environment_probe": {
            "probe_type": "package_inventory",
            "inventory_complete": True,
            "installed_python_packages": ["scanpy"],
            "installed_r_packages": ["ggplot2"],
            "installed_conda_packages": [],
            "available_executables": ["Rscript"],
            "which_python": "/env/bin/python",
            "rscript_path": "/env/bin/Rscript",
        },
    }

    plan = plan_environment(scan, target="existing", env="p2s_l2_case")

    kinds = [command["kind"] for command in plan["commands"]]
    assert "derived_conda_environment_update" not in kinds
    assert kinds[-1] == "environment_probe"
    all_packages = [package for command in plan["commands"] for package in command.get("packages") or []]
    assert "scanpy" not in all_packages
    assert "r-ggplot2" not in all_packages
    assert "r-base" not in all_packages
    assert "paper-only" in all_packages
    assert "bioconductor-deseq2" in all_packages
    assert "snakemake" in all_packages


def test_existing_env_missing_diff_preserves_conda_runtime_when_diff_is_empty():
    scan = {
        "repo": "repo",
        "signals": {"has_conda_spec": True},
        "case_install_request": {
            "missing_python_packages": ["scanpy[leiden]>=1.10"],
        },
        "environment_probe": {
            "probe_type": "package_inventory",
            "inventory_complete": True,
            "installed_python_packages": ["scanpy"],
            "installed_r_packages": [],
            "installed_conda_packages": ["python"],
            "which_python": "/env/bin/python",
        },
    }

    plan = plan_environment(scan, target="existing", env="p2s_l2_case")

    assert plan["mode"] == "existing_missing_diff"
    assert plan["manager"] == "conda"
    assert [command["kind"] for command in plan["commands"]] == ["environment_probe"]
    assert plan["commands"][0]["command"][:4] == ["conda", "run", "-n", "p2s_l2_case"]


def test_existing_env_missing_diff_ignores_unrelated_canonical_manual_blocks():
    scan = {
        "repo": "repo",
        "signals": {"has_conda_spec": True},
        "pip_segment": ["unknown-url @ https://example.com/pkg.whl"],
        "case_install_request": {
            "missing_python_packages": ["scanpy"],
        },
        "environment_probe": {
            "probe_type": "package_inventory",
            "inventory_complete": True,
            "installed_python_packages": ["scanpy"],
            "installed_r_packages": [],
            "installed_conda_packages": ["python"],
            "which_python": "/env/bin/python",
        },
    }

    plan = plan_environment(scan, target="existing", env="p2s_l2_case")

    assert plan["mode"] == "existing_missing_diff"
    assert plan["status"] == "ready"
    assert plan["manual_blocks"] == []
    assert [command["kind"] for command in plan["commands"]] == ["environment_probe"]


def test_new_canonical_plan_ends_with_environment_probe(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("scanpy\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    assert plan["commands"][-1]["kind"] == "environment_probe"


def test_canonical_environment_keeps_pip_segment_out_of_environment_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "environment.yml").write_text(
        """
name: demo
channels:
  - conda-forge
dependencies:
  - python=3.10
  - pip:
      - paper-only
      - scanpy>=1.10
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    dependencies = plan["canonical_environment"]["environment"]["dependencies"]
    assert not any(isinstance(item, dict) and "pip" in item for item in dependencies)
    assert plan["canonical_environment"]["report"]["pip_segment"] == ["paper-only"]
    uv_commands = [command for command in plan["commands"] if command["kind"] == "uv_python_packages"]
    assert any(command.get("source") == "assets/env/paper2skill.environment.yml" and command["packages"] == ["paper-only"] for command in uv_commands)
    conda_packages = [package for command in plan["commands"] for package in command.get("packages") or []]
    assert "scanpy>=1.10" in conda_packages


def test_generated_skill_normalization_report_pip_segment_enters_uv_plan(tmp_path: Path):
    skill = tmp_path / "skill"
    env_dir = skill / "assets" / "env"
    env_dir.mkdir(parents=True)
    (env_dir / "normalization_report.json").write_text(json.dumps({"pip_segment": ["paper-only>=0.1"]}), encoding="utf-8")

    plan = build_bio_env_plan(skill_dir=skill, target="new", env="p2s_l2_demo")

    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "paper-only>=0.1" in uv_packages
    assert plan["canonical_environment"]["report"]["pip_segment"] == ["paper-only>=0.1"]
    assert not any(isinstance(item, dict) and "pip" in item for item in plan["canonical_environment"]["environment"]["dependencies"])


def test_generated_skill_assets_requirements_enters_uv_plan(tmp_path: Path):
    skill = tmp_path / "skill"
    requirements = skill / "assets" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.write_text("scanpy>=1.10\nscikit-learn==1.4.0\npaper-only==1.0\n", encoding="utf-8")

    plan = build_bio_env_plan(skill_dir=skill, target="new", env="p2s_l2_demo")

    assert plan["manager"] == "conda"
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "paper-only==1.0" in uv_packages
    assert "scanpy>=1.10" not in uv_packages
    assert "scikit-learn==1.4.0" not in uv_packages
    assert plan["canonical_environment"]["report"]["pip_segment"] == ["paper-only==1.0"]
    deps = plan["canonical_environment"]["environment"]["dependencies"]
    assert "scanpy>=1.10" in deps
    assert "scikit-learn==1.4.0" in deps
    assert not any(isinstance(item, dict) and "pip" in item for item in plan["canonical_environment"]["environment"]["dependencies"])


def test_generated_skill_assets_requirements_url_requirements_stay_manual(tmp_path: Path):
    skill = tmp_path / "skill"
    requirements = skill / "assets" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.write_text(
        "mypkg @ https://example.com/pkg.whl\n"
        "git+https://github.com/example/pkg.git\n",
        encoding="utf-8",
    )

    plan = build_bio_env_plan(skill_dir=skill, target="new", env="p2s_l2_demo")

    assert plan["status"] == "blocked_manual"
    manual_types = {block.get("type") for block in plan["manual_blocks"]}
    assert {"direct_url_requirement", "vcs_requirement"} <= manual_types
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "mypkg @ https://example.com/pkg.whl" not in uv_packages
    assert "git+https://github.com/example/pkg.git" not in uv_packages


def test_generated_skill_assets_requirements_approved_urls_enter_uv_plan(tmp_path: Path):
    skill = tmp_path / "skill"
    requirements = skill / "assets" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.write_text(
        "mypkg @ https://example.com/pkg.whl\n"
        "git+https://github.com/example/pkg.git\n",
        encoding="utf-8",
    )
    approval_dir = skill / "assets" / "env"
    approval_dir.mkdir(parents=True)
    (approval_dir / "approved_install_sources.yaml").write_text(
        """
approval_source: generated_skill_review
python_direct_urls:
  - url: https://example.com/pkg.whl
python_vcs_urls:
  - url: git+https://github.com/example/pkg.git
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_bio_env_plan(skill_dir=skill, target="new", env="p2s_l2_demo")

    assert plan["status"] == "ready"
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "mypkg @ https://example.com/pkg.whl" in uv_packages
    assert "git+https://github.com/example/pkg.git" in uv_packages
    assert plan["manual_blocks"] == []


def test_generated_skill_assets_requirements_approval_requires_exact_url(tmp_path: Path):
    skill = tmp_path / "skill"
    requirements = skill / "assets" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.write_text("mypkg @ https://example.com/pkg-extra.whl\n", encoding="utf-8")
    approval_dir = skill / "assets" / "env"
    approval_dir.mkdir(parents=True)
    (approval_dir / "approved_install_sources.yaml").write_text(
        """
approval_source: generated_skill_review
python_direct_urls:
  - url: https://example.com/pkg.whl
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_bio_env_plan(skill_dir=skill, target="new", env="p2s_l2_demo")

    assert plan["status"] == "blocked_manual"
    uv_packages = [package for command in plan["commands"] if command["kind"] == "uv_python_packages" for package in command.get("packages") or []]
    assert "mypkg @ https://example.com/pkg-extra.whl" not in uv_packages
    assert any(block.get("type") == "direct_url_requirement" for block in plan["manual_blocks"])


def test_r_runtime_probe_checks_rscript_version():
    command = environment_probe_command({"uses_conda": True, "manager": "conda"}, env="p2s_l2_case", env_path="p2s_l2_case", needs_r_runtime=True)

    script = command["command"][-1]
    assert command["needs_r_runtime"] is True
    assert 'run(["Rscript", "--version"])' in script
    assert 'payload["error_type"] = "activation_failure"' in script


def test_executor_parses_environment_probe_json(monkeypatch):
    payload = {
        "sys_executable": "/env/bin/python",
        "sys_version": "3.11.0",
        "which_python": "/env/bin/python",
        "python_version": {"exit_code": 0, "stdout": "Python 3.11.0", "stderr": ""},
        "rscript_path": None,
        "rscript_version": {"exit_code": 127, "stdout": "", "stderr": "Rscript not found"},
        "needs_r_runtime": True,
        "probe_failure": "rscript_missing_or_failed",
        "error_type": "activation_failure",
    }

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 3, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)

    result = run_command_with_fallback({"kind": "environment_probe", "command": ["probe"]})

    assert result["exit_code"] == 3
    assert result["probe"]["sys_executable"] == "/env/bin/python"
    assert result["error_type"] == "activation_failure"
    assert result["probe_failure"] == "rscript_missing_or_failed"


def test_executor_parses_environment_inventory_probe_json(monkeypatch):
    payload = {
        "probe_type": "package_inventory",
        "inventory_complete": True,
        "installed_python_packages": ["scanpy"],
        "installed_r_packages": [],
        "installed_conda_packages": ["python"],
    }

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)

    result = run_command_with_fallback({"kind": "environment_inventory_probe", "command": ["probe"]})

    assert result["exit_code"] == 0
    assert result["probe"]["probe_type"] == "package_inventory"
    assert result["probe"]["inventory_complete"] is True


def test_unknown_r_package_becomes_manual_block():
    plan = plan_from_install_request({"missing_r_packages": ["unknownRpkg"]}, target="new", env="p2s_l2_case")

    assert plan["status"] == "blocked_manual"
    manual = [command for command in plan["commands"] if command["kind"] == "manual_r_package"]
    assert manual and manual[0]["packages"] == ["unknownRpkg"]


def test_description_suggests_do_not_enter_required_install_plan(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "DESCRIPTION").write_text("Imports:\n    DESeq2\nSuggests:\n    apeglm\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    packages = [package for command in plan["commands"] for package in command.get("packages") or []]
    assert "bioconductor-deseq2" in packages
    assert "bioconductor-apeglm" not in packages


def test_torch_cpu_uses_special_conda_route_not_uv():
    plan = plan_from_install_request({"missing_python_packages": ["torch"]}, target="new", env="p2s_l2_case", torch_backend="cpu")

    special = [command for command in plan["commands"] if command["kind"] == "special_torch_conda_packages"]
    assert special
    assert special[0]["special_route"]["profile"] == "conda_cpu"
    assert "pytorch" in special[0]["command"]
    assert not any(command["kind"] == "uv_python_packages" and "torch" in command.get("packages", []) for command in plan["commands"])


def test_torch_companion_packages_are_not_dropped():
    plan = plan_from_install_request({"missing_python_packages": ["torchvision", "torchaudio"]}, target="new", env="p2s_l2_case", torch_backend="cpu")

    packages = [package for command in plan["commands"] if command["kind"] == "special_torch_conda_packages" for package in command.get("packages", [])]
    assert "pytorch" in packages
    assert "torchvision" in packages
    assert "torchaudio" in packages
    assert "cpuonly" in packages


def test_setup_cfg_special_routes_enter_install_plan(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "setup.cfg").write_text("[metadata]\nname = setup-demo\n[options]\ninstall_requires =\n    torchvision\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo", torch_backend="cpu")

    special = [command for command in plan["commands"] if command["kind"] == "special_torch_conda_packages" and command.get("source") == "setup.cfg"]
    assert special
    assert "torchvision" in special[0]["packages"]
    assert not any(command["kind"] == "uv_python_packages" and "torchvision" in command.get("packages", []) for command in plan["commands"])


def test_conda_lock_trust_and_renv_requires_explicit_mode(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "conda-lock.yml").write_text(
        """
metadata:
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: linux-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/linux-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "renv.lock").write_text("{}", encoding="utf-8")

    scan = scan_repo(repo)

    default = trust_lockfiles(scan)
    assert any(item["name"] == "conda-lock.yml" and item["trusted"] for item in default["trusted"])
    assert any(item["name"] == "renv.lock" for item in default["blocked"])
    renv = trust_lockfiles(scan, r_mode="renv", allow_renv=True)
    assert any(item["name"] == "renv.lock" and item["trusted"] for item in renv["trusted"])

    plan = plan_environment(scan, target="new", env="p2s_l2_demo")
    assert plan["mode"] == "lockfile_restore"
    assert plan["frozen"] is True
    assert [command["kind"] for command in plan["commands"]] == ["restore_conda_lock", "environment_probe"]
    assert plan["commands"][0]["installer"] == "conda-lock"
    assert not any(command["kind"] == "derived_conda_environment" for command in plan["commands"])
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])


def test_platform_mismatch_conda_lock_falls_back_to_canonical_env(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "conda-lock.yml").write_text(
        """
metadata:
  platforms:
    - osx-64
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: osx-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/osx-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "environment.yml").write_text("name: demo\ndependencies:\n  - python=3.10\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    assert plan["mode"] == "canonical_env"
    assert plan["frozen"] is False
    assert plan["commands"][0]["kind"] == "derived_conda_environment"
    assert plan["lock_trust"]["trusted"] == []
    assert "platform linux-64 not in lockfile platforms" in plan["lock_trust"]["blocked"][0]["reason"]


def test_conda_lock_trust_plan_contains_only_restore_and_probe(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "conda-lock.yml").write_text(
        """
metadata:
  platforms:
    - linux-64
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: linux-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/linux-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "requirements.txt").write_text("scanpy\npaper-only\n", encoding="utf-8")
    (repo / "DESCRIPTION").write_text("Imports:\n    DESeq2\n", encoding="utf-8")

    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo")

    assert plan["mode"] == "lockfile_restore"
    assert plan["frozen"] is True
    assert [command["kind"] for command in plan["commands"]] == ["restore_conda_lock", "environment_probe"]
    assert not any(command["kind"] in {"conda_python_packages", "uv_python_packages", "r_bioc_conda_packages"} for command in plan["commands"])
    assert plan["commands"][0]["installer"] == "conda-lock"


def test_build_bio_env_plan_uses_skill_trusted_lockfile_before_case_dependencies(tmp_path: Path):
    skill = tmp_path / "skill"
    lock_dir = skill / "assets" / "env"
    lock_dir.mkdir(parents=True)
    (lock_dir / "conda-lock.yml").write_text(
        """
metadata:
  platforms:
    - linux-64
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: linux-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/linux-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )

    plan = build_bio_env_plan(
        skill_dir=skill,
        install_request={"missing_python_packages": ["paper-only"], "missing_r_packages": ["DESeq2"]},
        target="new",
        env="p2s_l2_case",
        env_path=str(tmp_path / ".benchmark" / "envs" / "p2s_l2_case"),
    )

    assert plan["mode"] == "lockfile_restore"
    assert plan["plan_source"] == "lockfile_restore"
    assert plan["frozen"] is True
    assert [command["kind"] for command in plan["commands"]] == ["restore_conda_lock", "environment_probe"]
    assert not any(command["kind"] == "uv_python_packages" for command in plan["commands"])
    assert any(item["name"] == "conda-lock.yml" for item in plan["scanned_artifacts"])


def test_lockfile_trust_blocks_unsafe_path_and_wrong_channels():
    scan = {
        "lockfiles": [
            {
                "name": "conda-lock.yml",
                "path": "../conda-lock.yml",
                "platforms": ["linux-64"],
                "channels": ["defaults"],
            },
            {"name": "uv.lock", "path": "/tmp/uv.lock"},
        ]
    }

    trust = trust_lockfiles(scan)

    assert trust["trusted"] == []
    reasons = " ".join(str(item.get("reason")) for item in trust["blocked"])
    assert "safe" in reasons
    assert "conda-forge and bioconda" in reasons


def test_conda_lock_without_parsed_metadata_is_not_trusted():
    scan = {
        "lockfiles": [
            {
                "name": "conda-lock.yml",
                "path": "conda-lock.yml",
                "platforms": ["linux-64"],
                "channels": ["conda-forge", "bioconda"],
            }
        ]
    }

    trust = trust_lockfiles(scan)

    assert trust["trusted"] == []
    assert trust["blocked"][0]["trusted"] is False
    assert "could not be parsed" in trust["blocked"][0]["reason"]


def test_uv_lock_is_only_pip_segment_restore(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    env_path = str(tmp_path / ".benchmark" / "envs" / "p2s_l2_demo")
    plan = plan_environment(scan_repo(repo), target="new", env="p2s_l2_demo", env_path=env_path)

    uv_locks = [command for command in plan["commands"] if command["kind"] == "uv_lock_segment_restore"]
    assert uv_locks
    assert uv_locks[0]["scope"] == "pip_uv_segment"
    assert uv_locks[0]["requires_base_environment"] is True
    assert uv_locks[0]["resolved_env_path"] == env_path
    assert uv_locks[0]["environment"]["UV_PROJECT_ENVIRONMENT"] == env_path


def test_canonical_environment_derives_without_overwriting_upstream(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    upstream = repo / "environment.yml"
    upstream.write_text(
        """
name: upstream
channels:
  - defaults
dependencies:
  - python=3.8
  - pip
  - pip:
      - scanpy
      - demo-top
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "DESCRIPTION").write_text("Imports:\n    DESeq2\n", encoding="utf-8")

    derived = derive_canonical_environment(scan_repo(repo), env_name="p2s_l2_demo", python_version="3.10")

    env = derived["environment"]
    deps_text = json.dumps(env["dependencies"])
    assert env["channels"][:2] == ["conda-forge", "bioconda"]
    assert "channel_priority" not in env
    assert derived["report"]["channel_priority"] == "strict"
    assert "scanpy" in deps_text
    assert "bioconductor-deseq2" in deps_text
    assert any(item["type"] == "python_version_conflict" for item in derived["report"]["conflicts"])
    assert upstream.read_text(encoding="utf-8").startswith("name: upstream")


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


def test_executor_runs_planner_conda_install_command_kinds(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    executable_kinds = [
        "conda_python_packages",
        "case_dependency_conda_packages",
        "r_runtime_conda_packages",
        "setup_cfg_conda_python_packages",
        "special_torch_conda_packages",
        "workflow_engine_conda_packages",
    ]
    plan = {
        "status": "ready",
        "env": "p2s_l2_case",
        "commands": [
            {
                "kind": kind,
                "installer": "mamba_or_conda",
                "packages": ["numpy"],
                "command": ["mamba", "install", "-y", "-n", "p2s_l2_case", "numpy"],
            }
            for kind in executable_kinds
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "executed"
    assert len(calls) == len(executable_kinds)
    assert not any(result.get("skipped") for result in report["execution_results"])


def test_apply_install_plan_with_no_commands_is_noop_success():
    report = apply_install_plan({"status": "ready", "env": "p2s_l2_case", "commands": []}, yes=True)

    assert report["status"] == "executed"
    assert report["auto_install_performed"] is False
    assert report["execution_results"] == []


def test_apply_install_plan_passes_command_environment(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["env"] = kwargs.get("env", {})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    plan = {
        "status": "ready",
        "env": "p2s_l2_case",
        "commands": [
            {
                "kind": "uv_lock_segment_restore",
                "installer": "uv",
                "command": ["uv", "sync", "--frozen"],
                "environment": {"UV_PROJECT_ENVIRONMENT": "/tmp/p2s_l2_case"},
            }
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "executed"
    assert captured["env"]["UV_PROJECT_ENVIRONMENT"] == "/tmp/p2s_l2_case"
    assert report["execution_results"][0]["environment"]["UV_PROJECT_ENVIRONMENT"] == "/tmp/p2s_l2_case"


def test_apply_install_plan_materializes_derived_environment_file(tmp_path: Path, monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    plan = {
        "status": "ready",
        "env": "p2s_l2_case",
        "canonical_environment": {
                "environment": {
                    "name": "p2s_l2_case",
                    "channels": ["conda-forge", "bioconda"],
                    "dependencies": ["python=3.10", "pip"],
                }
            },
        "commands": [
            {
                "kind": "derived_conda_environment",
                "installer": "mamba_or_conda",
                "source": "assets/env/paper2skill.environment.yml",
                "command": ["mamba", "env", "create", "-n", "p2s_l2_case", "--strict-channel-priority", "-f", "assets/env/paper2skill.environment.yml"],
            }
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "executed"
    assert (tmp_path / "assets" / "env" / "paper2skill.environment.yml").exists()
    written = (tmp_path / "assets" / "env" / "paper2skill.environment.yml").read_text(encoding="utf-8")
    assert "channel_priority" not in written


def test_apply_install_plan_materializes_derived_environment_under_workdir(tmp_path: Path, monkeypatch):
    caller = tmp_path / "caller"
    repo = tmp_path / "repo"
    caller.mkdir()
    repo.mkdir()

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.chdir(caller)
    monkeypatch.setattr("paper2skill.env_rebuilder.executor.subprocess.run", fake_run)
    plan = {
        "status": "ready",
        "env": "p2s_l2_case",
        "workdir": str(repo),
        "canonical_environment": {
            "environment": {
                "name": "p2s_l2_case",
                "channels": ["conda-forge", "bioconda"],
                "dependencies": ["python=3.10", "pip"],
            }
        },
        "commands": [
            {
                "kind": "derived_conda_environment",
                "installer": "mamba_or_conda",
                "source": "assets/env/paper2skill.environment.yml",
                "cwd": str(repo),
                "command": ["mamba", "env", "create", "-n", "p2s_l2_case", "--strict-channel-priority", "-f", "assets/env/paper2skill.environment.yml"],
            }
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "executed"
    assert (repo / "assets" / "env" / "paper2skill.environment.yml").exists()
    assert not (caller / "assets" / "env" / "paper2skill.environment.yml").exists()
    assert report["execution_results"][0]["cwd"] == str(repo)


def test_new_target_blocks_uv_segment_when_env_create_is_skipped(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    def fake_exists(command, plan):
        return command.get("kind") == "derived_conda_environment"

    def fake_run(command):
        calls.append(command["command"])
        return {
            "kind": command["kind"],
            "exit_code": 0,
            "stdout": json.dumps({"sys_executable": "/env/bin/python"}),
            "stderr": "",
            "skipped": False,
        }

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.should_skip_existing_environment", fake_exists)
    monkeypatch.setattr("paper2skill.env_rebuilder.executor.run_command_with_fallback", fake_run)
    plan = {
        "status": "ready",
        "target": "new",
        "env": "p2s_l2_case",
        "workdir": str(tmp_path),
        "canonical_environment": {
            "environment": {
                "name": "p2s_l2_case",
                "channels": ["conda-forge", "bioconda"],
                "dependencies": ["python=3.10", "pip", "uv"],
            }
        },
        "commands": [
            {
                "kind": "derived_conda_environment",
                "installer": "mamba_or_conda",
                "source": "assets/env/paper2skill.environment.yml",
                "skip_if_env_exists": True,
                "creates_env": True,
                "blocks_dependents_on_skip": True,
                "command": ["mamba", "env", "create", "-n", "p2s_l2_case", "-f", "assets/env/paper2skill.environment.yml"],
            },
            {
                "kind": "uv_python_packages",
                "installer": "uv",
                "packages": ["paper-only"],
                "depends_on_env_create": True,
                "command": ["conda", "run", "-n", "p2s_l2_case", "uv", "pip", "install", "paper-only"],
            },
            {
                "kind": "environment_probe",
                "installer": "probe",
                "command": ["conda", "run", "-n", "p2s_l2_case", "python", "-c", "probe"],
            },
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "blocked"
    assert report["env_create_blocked"] is True
    results = report["execution_results"]
    assert results[0]["skipped"] is True
    assert results[1]["kind"] == "uv_python_packages"
    assert results[1]["blocked"] is True
    assert "target=existing with a package inventory probe" in results[1]["reason"]
    assert calls == [["conda", "run", "-n", "p2s_l2_case", "python", "-c", "probe"]]


def test_new_target_skipped_env_create_with_only_probe_is_blocked(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []

    def fake_exists(command, plan):
        return command.get("kind") == "derived_conda_environment"

    def fake_run(command):
        calls.append(command["command"])
        return {
            "kind": command["kind"],
            "exit_code": 0,
            "stdout": json.dumps({"sys_executable": "/env/bin/python"}),
            "stderr": "",
            "skipped": False,
        }

    monkeypatch.setattr("paper2skill.env_rebuilder.executor.should_skip_existing_environment", fake_exists)
    monkeypatch.setattr("paper2skill.env_rebuilder.executor.run_command_with_fallback", fake_run)
    plan = {
        "status": "ready",
        "target": "new",
        "env": "p2s_l2_case",
        "workdir": str(tmp_path),
        "canonical_environment": {
            "environment": {
                "name": "p2s_l2_case",
                "channels": ["conda-forge", "bioconda"],
                "dependencies": ["python=3.10", "pip", "uv"],
            }
        },
        "commands": [
            {
                "kind": "derived_conda_environment",
                "installer": "mamba_or_conda",
                "source": "assets/env/paper2skill.environment.yml",
                "skip_if_env_exists": True,
                "creates_env": True,
                "blocks_dependents_on_skip": True,
                "command": ["mamba", "env", "create", "-n", "p2s_l2_case", "-f", "assets/env/paper2skill.environment.yml"],
            },
            {
                "kind": "environment_probe",
                "installer": "probe",
                "command": ["conda", "run", "-n", "p2s_l2_case", "python", "-c", "probe"],
            },
        ],
    }

    report = apply_install_plan(plan, yes=True)

    assert report["status"] == "blocked"
    assert report["reason"] == "target=new skipped environment creation"
    assert report["env_create_blocked"] is True
    assert report["execution_results"][0]["skipped"] is True
    assert calls == [["conda", "run", "-n", "p2s_l2_case", "python", "-c", "probe"]]


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
    cuda = next(item for item in report["findings"] if item["failure_mode"] == "cuda_mismatch")
    assert cuda["manual_block"] is True


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
