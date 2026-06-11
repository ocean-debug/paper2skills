from __future__ import annotations

import json
from pathlib import Path

import yaml

from paper2skill.build_validation import validate_build


def write_minimal_skill(root: Path) -> Path:
    (root / "scripts" / "adapters").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    (root / "assets" / "env").mkdir(parents=True)
    for path in ["SKILL.md", "scripts/preflight.py", "scripts/env_manager.py", "scripts/run_in_env.sh", "scripts/qsub_template.sh", "scripts/plan.py", "scripts/run.py", "scripts/validate_outputs.py"]:
        (root / path).write_text("ok\n", encoding="utf-8")
    for path in ["io_contract.yaml", "bio_contract.yaml", "adapter_spec.yaml", "adapter_review.yaml", "evidence_graph.json"]:
        target = root / "references" / path
        if target.suffix == ".json":
            target.write_text("{}", encoding="utf-8")
        else:
            target.write_text(yaml.safe_dump({"status": "candidate"}), encoding="utf-8")
    (root / "references" / "workflow_dag.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (root / "references" / "notebook_execution_policy.json").write_text(json.dumps({"execute_unknown_notebooks": False}), encoding="utf-8")
    (root / "assets" / "environment_spec.yaml").write_text("auto_install_requires_confirmation: true\n", encoding="utf-8")
    (root / "assets" / "env" / "paper2skill.environment.yml").write_text("name: skill-env\nchannels:\n- conda-forge\n", encoding="utf-8")
    (root / "assets" / "env" / "normalization_report.json").write_text(json.dumps({"channel_priority": "strict"}), encoding="utf-8")
    return root


def test_build_validation_dry_run_is_diagnostic_not_benchmark_score(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")

    result = validate_build(skill)

    assert result["validation_depth"] == "dry_run"
    assert result["passed"] is True
    assert result["benchmark_score"] is None
    assert result["diagnostic_only"] is True


def test_build_validation_data_smoke_does_not_create_benchmark_score(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")

    result = validate_build(skill, validation_depth="data_smoke")

    assert result["validation_depth"] == "data_smoke"
    assert result["passed"] is False
    assert result["status"] == "unsupported"
    assert result["self_check_status"] == "unsupported"
    assert "validation_depth_unsupported" in result["errors"]
    assert result["benchmark_score"] is None
    assert any("no benchmark score" in warning for warning in result["warnings"])


def test_build_validation_live_execute_unsupported_is_not_passed(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")

    result = validate_build(skill, validation_depth="live_execute")

    assert result["passed"] is False
    assert result["status"] == "unsupported"
    assert "validation_depth_unsupported" in result["errors"]
