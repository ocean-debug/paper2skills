from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from paper2skill.runtime.env_manager import inspect_environment
from paper2skill.runtime import env_manager
from paper2skill.runtime.install_planner import build_install_plan
from paper2skill.runtime.python_probe import import_name_from_spec, probe_python_package


def test_python_spec_strips_extras_but_preserves_spec(monkeypatch):
    monkeypatch.setenv("PAPER2SKILL_FORCE_MISSING_PACKAGES", "scanpy")
    spec = {"install_policy": "ask", "python": {"packages": [{"spec": 'scanpy[leiden]>=1.10; python_version >= "3.10"'}]}, "r": {"required": False, "packages": []}, "executables": []}
    report = inspect_environment(spec, non_interactive=True)
    pkg = report["python"]["packages"][0]
    assert import_name_from_spec(pkg["name"]) == "scanpy"
    assert pkg["name"].startswith("scanpy[leiden]")
    assert report["status"] == "blocked_dependencies_missing"
    assert report["effective_install_policy"] == "never"


def test_python_direct_reference_uses_distribution_name_as_import_probe():
    spec = "localpkg @ file:///tmp/private/localpkg"
    record = probe_python_package(spec)
    assert import_name_from_spec(spec) == "localpkg"
    assert record["name"] == spec
    assert record["import_name"] == "localpkg"


def test_missing_r_package_blocks_when_rscript_available(monkeypatch):
    from paper2skill.runtime import env_manager

    def fake_probe_r(packages, require_rscript=False):
        return {
            "rscript_available": True,
            "rscript": "/usr/bin/Rscript",
            "version": "R scripting front-end",
            "required": True,
            "packages": [{"name": "Seurat", "installed": False, "source": "CRAN_or_unknown", "required": True}],
        }

    monkeypatch.setattr(env_manager, "probe_r", fake_probe_r)
    spec = {"install_policy": "ask", "python": {"packages": []}, "r": {"required": True, "packages": [{"name": "Seurat"}]}, "executables": []}
    report = env_manager.inspect_environment(spec, non_interactive=True)
    assert report["status"] == "blocked_dependencies_missing"


def test_missing_rscript_blocks_runtime(monkeypatch):
    monkeypatch.setenv("PAPER2SKILL_FORCE_MISSING_EXECUTABLES", "Rscript")
    spec = {"install_policy": "ask", "python": {"packages": []}, "r": {"required": True, "packages": []}, "executables": []}
    report = inspect_environment(spec, non_interactive=True)
    assert report["status"] == "blocked_runtime_missing"


def test_generated_env_manager_refuses_install_without_confirm(tmp_path: Path):
    out = tmp_path / "skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "env_manager.py"), "install", "--strategy", "current_env"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "confirm" in result.stderr.lower()


def test_version_command_runs_without_shell(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

        class Result:
            stdout = "tool 1.0\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(env_manager.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(env_manager.subprocess, "run", fake_run)
    monkeypatch.setattr(env_manager, "probe_python", lambda packages: {"packages": []})
    monkeypatch.setattr(env_manager, "probe_r", lambda packages, required=False: {"required": False, "rscript_available": False, "packages": []})
    report = env_manager.inspect_environment(
        {
            "install_policy": "ask",
            "python": {"packages": []},
            "r": {"required": False, "packages": []},
            "executables": [{"name": "tool", "version_command": ["tool", "--version"]}],
        },
        non_interactive=True,
    )
    assert report["executables"][0]["version"] == "tool 1.0"
    assert isinstance(calls[0][0], list)
    assert calls[0][1].get("shell") is None


def test_version_command_rejects_arbitrary_argv(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        raise AssertionError("unsafe command should not run")

    monkeypatch.setattr(env_manager.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(env_manager.subprocess, "run", fake_run)
    monkeypatch.setattr(env_manager, "probe_python", lambda packages: {"packages": []})
    monkeypatch.setattr(env_manager, "probe_r", lambda packages, required=False: {"required": False, "rscript_available": False, "packages": []})
    report = env_manager.inspect_environment(
        {
            "install_policy": "ask",
            "python": {"packages": []},
            "r": {"required": False, "packages": []},
            "executables": [{"name": "bash", "version_command": ["bash", "-c", "touch /tmp/paper2skill-bad"]}],
        },
        non_interactive=True,
    )
    assert report["executables"][0]["available"] is True
    assert report["executables"][0]["version"] is None
    assert calls == []


def test_builder_environment_output_redacts_executable_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        env_manager,
        "probe_python",
        lambda packages: {
            "executable": "/tmp/private-env/bin/python",
            "version": "3.11",
            "packages": [{"name": "localpkg @ file:///tmp/private-env/localpkg", "installed": False, "required": True}],
        },
    )
    monkeypatch.setattr(
        env_manager,
        "probe_r",
        lambda packages, required=False: {
            "required": True,
            "rscript_available": True,
            "rscript": "/tmp/private-env/bin/Rscript",
            "version": "R",
            "packages": [],
        },
    )
    monkeypatch.setattr(
        env_manager,
        "probe_executables",
        lambda executables=None: [
            {"name": "tool", "path": "/tmp/private-env/bin/tool", "available": True, "version": "1.0", "required": True}
        ],
    )
    report = env_manager.write_environment_outputs(
        {
            "install_policy": "ask",
            "environment_name": "/tmp/private-env/conda",
            "python": {"packages": [{"name": "localpkg @ file:///tmp/private-env/localpkg"}]},
            "r": {"required": True, "packages": []},
            "executables": [],
        },
        tmp_path / "out",
        non_interactive=True,
    )
    public_text = (tmp_path / "out" / "qc" / "environment_report.json").read_text(encoding="utf-8")
    install_plan_text = (tmp_path / "out" / "qc" / "install_plan.json").read_text(encoding="utf-8")
    install_plan_md = (tmp_path / "out" / "references" / "install_plan.md").read_text(encoding="utf-8")
    assert report["python"]["executable"] == "/tmp/private-env/bin/python"
    assert "/tmp/private-env" not in public_text
    assert "file:///tmp/private-env" not in public_text
    assert "/tmp/private-env" not in install_plan_text + install_plan_md
    assert "conda" in install_plan_text
    assert public_text.count("<redacted-local-path>") == 3


def test_builder_install_plan_conda_r_includes_r_base():
    report = {
        "python": {"packages": []},
        "r": {"packages": [{"name": "Seurat", "installed": False, "required": True}]},
        "executables": [],
        "install_policy": "ask",
        "effective_install_policy": "never",
    }
    plan = build_install_plan(report, {"environment_name": "demo-env"})
    conda = next(option for option in plan["options"] if option["strategy"] == "conda_env")
    assert conda["commands"][0] == "conda create -y -n demo-env python>=3.10 pip r-base"
    assert conda["commands"][1].startswith("conda run -n demo-env")
