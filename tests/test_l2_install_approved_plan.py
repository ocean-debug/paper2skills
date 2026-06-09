from __future__ import annotations

import json
from pathlib import Path

from paper2skill.evaluation.execution.install_approved_plan import build_install_plan, main


def evaluation_with_install_request() -> dict:
    return {
        "case_id": "case",
        "level_results": {
            "L2": {
                "evaluators": {
                    "official_example_execution": {
                        "examples": [
                            {
                                "actual_status": "install_approval_required",
                                "execution": {
                                    "install_request": {
                                        "status": "approval_required",
                                        "target_environment": "paper2skill-l2-demo",
                                        "allowed_installers": ["conda", "pip", "BiocManager"],
                                        "conda_packages": ["numpy"],
                                        "missing_python_packages": ["anndata"],
                                        "missing_r_packages": ["DESeq2"],
                                        "missing_executables": [],
                                        "required_packages": ["anndata", "DESeq2"],
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        },
    }


def test_build_install_plan_requires_matching_user_environment():
    plan = build_install_plan(evaluation_with_install_request(), install_env="paper2skill-l2-demo")

    assert plan["status"] == "ready"
    assert plan["dry_run"] is True
    assert plan["auto_install_performed"] is False
    assert len(plan["commands"]) == 3
    assert plan["commands"][0]["kind"] == "conda_packages"
    assert plan["commands"][1]["command"][:4] == ["conda", "run", "-n", "paper2skill-l2-demo"]
    assert plan["commands"][2]["installer"] == "BiocManager"


def test_build_install_plan_can_create_conda_env():
    plan = build_install_plan(evaluation_with_install_request(), install_env="paper2skill-l2-demo", create_conda_env=True, python_version="3.11")

    assert plan["status"] == "ready"
    assert plan["commands"][0]["kind"] == "conda_env_create"
    assert plan["commands"][0]["command"] == ["conda", "create", "-y", "-n", "paper2skill-l2-demo", "python=3.11", "pip", "r-base"]
    assert not any(command["kind"] == "conda_packages" and "r-base" in command["packages"] for command in plan["commands"])


def test_build_install_plan_accepts_r_github_packages():
    evaluation = evaluation_with_install_request()
    request = evaluation["level_results"]["L2"]["evaluators"]["official_example_execution"]["examples"][0]["execution"]["install_request"]
    request["allowed_installers"].append("remotes")
    request["r_github_packages"] = ["neurorestore/Augur"]

    plan = build_install_plan(evaluation, install_env="paper2skill-l2-demo")

    assert plan["status"] == "ready"
    github_commands = [command for command in plan["commands"] if command["kind"] == "r_github_packages"]
    assert github_commands
    assert github_commands[0]["packages"] == ["neurorestore/Augur"]


def test_build_install_plan_supports_conda_channels():
    evaluation = evaluation_with_install_request()
    request = evaluation["level_results"]["L2"]["evaluators"]["official_example_execution"]["examples"][0]["execution"]["install_request"]
    request["conda_channels"] = ["conda-forge", "bioconda"]

    plan = build_install_plan(evaluation, install_env="paper2skill-l2-demo", create_conda_env=True)

    assert plan["status"] == "ready"
    assert plan["conda_channels"] == ["conda-forge", "bioconda"]
    assert "-c" in plan["commands"][0]["command"]
    assert "conda-forge" in plan["commands"][0]["command"]
    assert "bioconda" in plan["commands"][1]["command"]


def test_build_install_plan_rejects_shared_env_by_default():
    try:
        build_install_plan(evaluation_with_install_request(), install_env="skill")
    except ValueError as exc:
        assert "shared environment" in str(exc)
    else:
        raise AssertionError("expected shared environment rejection")


def test_build_install_plan_rejects_request_env_mismatch():
    plan = build_install_plan(evaluation_with_install_request(), install_env="paper2skill-l2-other")

    assert plan["status"] == "invalid"
    assert "does not match" in plan["errors"][0]
    assert plan["commands"] == []


def test_install_approved_plan_cli_writes_dry_run_plan(tmp_path: Path):
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(json.dumps(evaluation_with_install_request()), encoding="utf-8")
    out = tmp_path / "install_plan.json"

    exit_code = main(["--evaluation", str(evaluation), "--install-env", "paper2skill-l2-demo", "--out", str(out)])

    assert exit_code == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["status"] == "ready"
    assert plan["dry_run"] is True
    assert plan["auto_install_performed"] is False


def test_install_approved_plan_cli_requires_yes_for_execute(tmp_path: Path):
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(json.dumps(evaluation_with_install_request()), encoding="utf-8")
    out = tmp_path / "install_plan.json"

    exit_code = main(["--evaluation", str(evaluation), "--install-env", "paper2skill-l2-demo", "--out", str(out), "--execute"])

    assert exit_code == 2
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["status"] == "invalid"
    assert "--yes is required" in plan["errors"][0]
