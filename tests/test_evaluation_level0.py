from __future__ import annotations

import json
from pathlib import Path

import yaml

from paper2skill.evaluation.validate_skill_package import validate_skill_package


def write_minimal_skill(root: Path, *, adapter_status: str = "candidate") -> Path:
    (root / "scripts" / "adapters").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    (root / "assets").mkdir(parents=True)
    for path in ["SKILL.md", "scripts/preflight.py", "scripts/plan.py", "scripts/run.py", "scripts/validate_outputs.py"]:
        (root / path).write_text("ok\n", encoding="utf-8")
    for path in ["io_contract.yaml", "bio_contract.yaml", "adapter_spec.yaml", "adapter_review.yaml", "evidence_graph.json"]:
        target = root / "references" / path
        if target.suffix == ".json":
            target.write_text("{}", encoding="utf-8")
        else:
            target.write_text(yaml.safe_dump({"status": adapter_status}), encoding="utf-8")
    (root / "references" / "workflow_dag.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (root / "references" / "notebook_execution_policy.json").write_text(json.dumps({"execute_unknown_notebooks": False}), encoding="utf-8")
    (root / "assets" / "environment_spec.yaml").write_text("auto_install_requires_confirmation: true\n", encoding="utf-8")
    return root


def test_level0_validates_required_skill_package_files(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")

    result = validate_skill_package(skill)

    assert result["passed"] is True
    assert result["level"] == "L0"
    assert result["score"] == 100.0


def test_level0_missing_file_fails_gracefully(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")
    (skill / "scripts" / "run.py").unlink()

    result = validate_skill_package(skill)

    assert result["passed"] is False
    assert "scripts/run.py" in result["missing_files"]


def test_level0_detects_path_leakage(tmp_path: Path):
    skill = write_minimal_skill(tmp_path / "skill")
    (skill / "SKILL.md").write_text("local path C:\\Users\\wang\\secret\n", encoding="utf-8")

    result = validate_skill_package(skill)

    assert result["passed"] is False
    assert result["path_leakage"] == ["SKILL.md"]
