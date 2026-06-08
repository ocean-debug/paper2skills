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
                                        "allowed_installers": ["pip", "BiocManager"],
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
    assert len(plan["commands"]) == 2
    assert plan["commands"][0]["command"][:4] == ["conda", "run", "-n", "paper2skill-l2-demo"]
    assert plan["commands"][1]["installer"] == "BiocManager"


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
