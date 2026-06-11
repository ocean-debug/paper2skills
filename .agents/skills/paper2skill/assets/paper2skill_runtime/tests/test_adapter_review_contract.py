from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from paper2skill.generators import codex_skill_generator
from paper2skill.validators import adapter_review
from paper2skill.validators import skill_validator
from paper2skill.validators.adapter_review import adapter_review_mismatches, command_refinement_errors


def test_command_extension_is_prefix_compatible() -> None:
    spec = {
        "adapter_type": "cli",
        "status": "candidate",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "reviewed",
        "entrypoint": "omics",
        "command": "omics --input {manifest} --out {out}",
        "human_approved": True,
        "dry_run": {"status": "pass"},
        "expected_outputs": ["results/summary.json"],
        "evidence": [],
        "caveats": [],
    }

    assert adapter_review_mismatches(spec, review) == []
    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "reviewed"
    assert reviewed_spec["command"] == "omics --input {manifest} --out {out}"


def test_list_command_is_valid_reviewed_mapping() -> None:
    spec = {
        "adapter_type": "workflow_engine",
        "status": "candidate",
        "entrypoint": "python-workflow",
        "command": ["python"],
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "workflow_engine",
        "status": "reviewed",
        "entrypoint": "python-workflow",
        "command": ["python", "-m", "workflow", "--manifest", "{manifest}", "--out", "{out}"],
        "human_approved": True,
        "dry_run": {"status": "pass"},
        "expected_outputs": ["results/summary.json"],
        "evidence": [],
        "caveats": [],
    }

    assert adapter_review.missing_explicit_adapter_mapping(spec, review) == []
    assert adapter_review_mismatches(spec, review) == []
    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "reviewed"
    assert reviewed_spec["command"] == review["command"]


def test_illegal_command_placeholder_is_rejected() -> None:
    errors = command_refinement_errors("omics", "omics --token {secret} --out {out}")

    assert "unsupported_placeholder:secret" in errors
    spec = {
        "adapter_type": "cli",
        "status": "candidate",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "reviewed",
        "entrypoint": "omics",
        "command": "omics --token {secret}",
        "human_approved": True,
        "dry_run": {"status": "pass"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }

    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "blocked"


def test_illegal_command_replacement_is_rejected() -> None:
    errors = command_refinement_errors("omics", "python other.py")

    assert "not_prefix_compatible" in errors
    spec = {
        "adapter_type": "cli",
        "status": "candidate",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "reviewed",
        "entrypoint": "omics",
        "command": "python other.py",
        "human_approved": True,
        "dry_run": {"status": "pass"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }

    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "blocked"


def test_generator_and_skill_validator_share_adapter_review_helper() -> None:
    assert codex_skill_generator.adapter_review_matches is adapter_review.adapter_review_matches
    assert codex_skill_generator.missing_explicit_adapter_mapping is adapter_review.missing_explicit_adapter_mapping
    assert skill_validator.adapter_review_mismatches is adapter_review.adapter_review_mismatches
    assert skill_validator.missing_explicit_adapter_mapping is adapter_review.missing_explicit_adapter_mapping


def write_child_template(template_root: Path, source: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((template_root / source).read_text(encoding="utf-8"), encoding="utf-8")


def import_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_workflow_engine_routes_to_reviewed_command_adapter(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "workflow-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)

    for source, target in {
        "scripts/run.py.j2": scripts / "run.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/__init__.py.j2": scripts / "adapters" / "__init__.py",
        "scripts/adapters/command_adapter.py.j2": scripts / "adapters" / "command_adapter.py",
        "scripts/adapters/workflow_engine_adapter.py.j2": scripts / "adapters" / "workflow_engine_adapter.py",
    }.items():
        write_child_template(template_root, source, target)

    command_script = (
        "from pathlib import Path; "
        "import os; "
        "out = Path(os.environ['PAPER2SKILL_OUT']); "
        "(out / 'results').mkdir(parents=True, exist_ok=True); "
        "(out / 'results' / 'workflow.txt').write_text('workflow ok', encoding='utf-8')"
    )
    adapter_spec = {
        "adapter_type": "workflow_engine",
        "status": "reviewed",
        "entrypoint": "python-workflow",
        "command": [sys.executable, "-c", command_script],
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    adapter_review = {
        **adapter_spec,
        "human_approved": True,
        "dry_run": {"status": "pass"},
        "expected_outputs": ["results/workflow.txt"],
    }
    (references / "adapter_spec.yaml").write_text(json.dumps(adapter_spec), encoding="utf-8")
    (references / "adapter_review.yaml").write_text(json.dumps(adapter_review), encoding="utf-8")

    original_sys_path = list(sys.path)
    imported_modules = [
        "_paper2skill_child_run",
        "env_manager",
        "adapters",
        "adapters.command_adapter",
        "adapters.workflow_engine_adapter",
    ]
    for module_name in imported_modules:
        sys.modules.pop(module_name, None)
    try:
        run_module = import_module_from_path("_paper2skill_child_run", scripts / "run.py")
        out = skill_root / "result"
        manifest_path = skill_root / "manifest.json"
        manifest_path.write_text(json.dumps({"inputs": {}}), encoding="utf-8")

        report = run_module.run_adapter("workflow_engine", {"inputs": {}}, out, manifest_path)
    finally:
        sys.path[:] = original_sys_path
        for module_name in imported_modules:
            sys.modules.pop(module_name, None)

    assert report["status"] == "pass"
    assert report["adapter_type"] == "workflow_engine"
    assert report["outputs"] == ["results/workflow.txt"]
    assert (out / "results" / "workflow.txt").read_text(encoding="utf-8") == "workflow ok"
    assert (out / "logs" / "workflow_engine_adapter.stdout.log").exists()
