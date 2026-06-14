from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from paper2skill.build_validation import validator as build_validator
from paper2skill.generators import codex_skill_generator
from paper2skill.validators import adapter_review
from paper2skill.validators import skill_validator
from paper2skill.validators.adapter_review import adapter_review_mismatches, command_refinement_errors


def test_command_extension_is_prefix_compatible() -> None:
    spec = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "verified",
        "entrypoint": "omics",
        "command": "omics --input {manifest} --out {out}",
        "verification": {"status": "pass", "source": "run_trace", "output_validation": {"status": "pass"}},
        "expected_outputs": ["results/summary.json"],
        "evidence": ["run_trace"],
        "caveats": [],
    }

    assert adapter_review_mismatches(spec, review) == []
    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "verified"
    assert reviewed_spec["command"] == "omics --input {manifest} --out {out}"


def test_list_command_is_valid_verified_mapping() -> None:
    spec = {
        "adapter_type": "workflow_engine",
        "status": "dry_run_only",
        "entrypoint": "python-workflow",
        "command": ["python"],
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "workflow_engine",
        "status": "verified",
        "entrypoint": "python-workflow",
        "command": ["python", "-m", "workflow", "--manifest", "{manifest}", "--out", "{out}"],
        "verification": {"status": "pass", "source": "run_trace", "output_validation": {"status": "pass"}},
        "expected_outputs": ["results/summary.json"],
        "evidence": ["run_trace"],
        "caveats": [],
    }

    assert adapter_review.missing_explicit_adapter_mapping(spec, review) == []
    assert adapter_review_mismatches(spec, review) == []
    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "verified"
    assert reviewed_spec["command"] == review["command"]


def test_illegal_command_placeholder_is_rejected() -> None:
    errors = command_refinement_errors("omics", "omics --token {secret} --out {out}")

    assert "unsupported_placeholder:secret" in errors
    spec = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "verified",
        "entrypoint": "omics",
        "command": "omics --token {secret}",
        "verification": {"status": "pass", "output_validation": {"status": "pass"}},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }

    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "dry_run_only"


def test_illegal_command_replacement_is_rejected() -> None:
    errors = command_refinement_errors("omics", "python other.py")

    assert "not_prefix_compatible" in errors
    spec = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "verified",
        "entrypoint": "omics",
        "command": "python other.py",
        "verification": {"status": "pass", "output_validation": {"status": "pass"}},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }

    reviewed_spec, _review_data = codex_skill_generator.apply_adapter_review(spec, review)
    assert reviewed_spec["status"] == "dry_run_only"


def test_generator_and_skill_validator_share_adapter_review_helper() -> None:
    assert codex_skill_generator.adapter_review_matches is adapter_review.adapter_review_matches
    assert codex_skill_generator.missing_explicit_adapter_mapping is adapter_review.missing_explicit_adapter_mapping
    assert skill_validator.adapter_review_mismatches is adapter_review.adapter_review_mismatches
    assert skill_validator.missing_explicit_adapter_mapping is adapter_review.missing_explicit_adapter_mapping


def test_verified_review_accepts_nested_output_validation() -> None:
    spec = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "verified",
        "entrypoint": "omics",
        "command": "omics --input {manifest} --out {out}",
        "verification": {"status": "pass", "source": "run_trace", "output_validation": {"status": "pass"}},
        "expected_outputs": ["results/summary.json"],
        "evidence": ["run_trace"],
        "caveats": [],
    }

    reviewed_spec, review_data = codex_skill_generator.apply_adapter_review(spec, review)

    assert reviewed_spec["status"] == "verified"
    assert review_data["verification"]["output_validation"]["status"] == "pass"


def test_verified_review_requires_run_trace_evidence() -> None:
    spec = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "omics",
        "command": "omics",
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    review = {
        "adapter_type": "cli",
        "status": "verified",
        "entrypoint": "omics",
        "command": "omics --input {manifest} --out {out}",
        "verification": {"status": "pass", "output_validation": {"status": "pass"}},
        "expected_outputs": ["results/summary.json"],
        "evidence": [],
        "caveats": [],
    }

    reviewed_spec, review_data = codex_skill_generator.apply_adapter_review(spec, review)

    assert reviewed_spec["status"] == "dry_run_only"
    assert review_data["status"] == "dry_run_only"


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


def test_child_run_status_is_resolved_per_selected_example(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "example-gated-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)

    for source, target in {
        "scripts/run.py.j2": scripts / "run.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
    }.items():
        write_child_template(template_root, source, target)

    adapter_spec = {
        "adapter_type": "notebook",
        "status": "verified",
        "entrypoint": "scripts/adapters/notebook_adapter.py",
        "command": ["python", "scripts/adapters/notebook_adapter.py", "{manifest}", "{out}", "{example_id}"],
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    examples_catalog = {
        "default_example_id": "verified_demo",
        "examples": [
            {"example_id": "verified_demo", "adapter": {"status": "verified"}},
            {"example_id": "unverified_demo", "adapter": {"status": "dry_run_only"}},
        ],
    }
    (references / "adapter_spec.yaml").write_text(json.dumps(adapter_spec), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(json.dumps(examples_catalog), encoding="utf-8")

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_child_run_example_gate", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        run_module = import_module_from_path("_paper2skill_child_run_example_gate", scripts / "run.py")
        assert run_module.selected_example_adapter_status("verified_demo", adapter_spec) == "verified"
        assert run_module.selected_example_adapter_status("unverified_demo", adapter_spec) == "dry_run_only"
        assert run_module.selected_example_adapter_status("missing_demo", adapter_spec) == "dry_run_only"
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_child_run_example_gate", "env_manager"]:
            sys.modules.pop(module_name, None)


def test_one_verified_example_does_not_unlock_dry_run_only_example(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "example-run-gated-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    assets = skill_root / "assets"
    references.mkdir(parents=True)
    assets.mkdir()

    for source, target in {
        "scripts/run.py.j2": scripts / "run.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
    }.items():
        write_child_template(template_root, source, target)
    (scripts / "preflight.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'qc').mkdir(parents=True, exist_ok=True)\n"
        "for name in ['input_validation.json','environment_report.json','missing_dependencies.json']:\n"
        "    (out/'qc'/name).write_text('{}', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (scripts / "plan.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'workflow').mkdir(parents=True, exist_ok=True)\n"
        "(out/'workflow'/'plan.json').write_text('{\"evidence_used\": []}', encoding='utf-8')\n"
        "(out/'workflow'/'plan.md').write_text('# plan\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest_path = assets / "manifest.json"
    manifest_path.write_text(json.dumps({"inputs": {"algorithm": {"mode": "official_example_attempt"}}}), encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "workflow_engine", "status": "verified", "entrypoint": "x", "command": "x", "caveats": []}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "verified_demo",
                "examples": [
                    {"example_id": "verified_demo", "adapter": {"status": "verified"}},
                    {"example_id": "unverified_demo", "adapter": {"status": "dry_run_only"}},
                ],
            }
        ),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_child_run_main_gate", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        run_module = import_module_from_path("_paper2skill_child_run_main_gate", scripts / "run.py")
        rc = run_module.main(["--manifest", str(manifest_path), "--out", str(skill_root / "result"), "--example-id", "unverified_demo"])
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_child_run_main_gate", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert rc == 2
    adapter_report = json.loads((skill_root / "result" / "workflow" / "adapter_report.json").read_text(encoding="utf-8"))
    assert adapter_report["adapter_status"] == "dry_run_only"
    assert adapter_report["global_adapter_status"] == "verified"


def test_child_run_fails_unknown_explicit_example_even_during_verification(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "example-run-missing-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    assets = skill_root / "assets"
    references.mkdir(parents=True)
    assets.mkdir()

    for source, target in {
        "scripts/run.py.j2": scripts / "run.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
    }.items():
        write_child_template(template_root, source, target)
    (scripts / "preflight.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'qc').mkdir(parents=True, exist_ok=True)\n"
        "for name in ['input_validation.json','environment_report.json','missing_dependencies.json']:\n"
        "    (out/'qc'/name).write_text('{}', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (scripts / "plan.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'workflow').mkdir(parents=True, exist_ok=True)\n"
        "(out/'workflow'/'plan.json').write_text('{\"evidence_used\": []}', encoding='utf-8')\n"
        "(out/'workflow'/'plan.md').write_text('# plan\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest_path = assets / "manifest.json"
    manifest_path.write_text(json.dumps({"inputs": {"algorithm": {"mode": "official_example_attempt"}}}), encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "python_api", "status": "verified", "entrypoint": "global", "module": "missing_module", "function": "run", "caveats": []}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(
        json.dumps({"default_example_id": "known", "examples": [{"example_id": "known", "adapter": {"status": "verified"}}]}),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_child_run_missing_example", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        run_module = import_module_from_path("_paper2skill_child_run_missing_example", scripts / "run.py")
        rc = run_module.main(
            [
                "--manifest",
                str(manifest_path),
                "--out",
                str(skill_root / "result"),
                "--example-id",
                "missing",
                "--verification-run",
            ]
        )
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_child_run_missing_example", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert rc == 2
    adapter_report = json.loads((skill_root / "result" / "workflow" / "adapter_report.json").read_text(encoding="utf-8"))
    assert adapter_report["status"] == "fail"
    assert adapter_report["example_id"] == "missing"
    assert "missing from examples_catalog" in adapter_report["message"]


def test_child_run_fails_explicit_example_when_catalog_has_no_examples(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "example-run-empty-catalog-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    assets = skill_root / "assets"
    references.mkdir(parents=True)
    assets.mkdir()

    for source, target in {
        "scripts/run.py.j2": scripts / "run.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
    }.items():
        write_child_template(template_root, source, target)
    (scripts / "preflight.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'qc').mkdir(parents=True, exist_ok=True)\n"
        "for name in ['input_validation.json','environment_report.json','missing_dependencies.json']:\n"
        "    (out/'qc'/name).write_text('{}', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (scripts / "plan.py").write_text(
        "from pathlib import Path\nimport sys\nout=Path(sys.argv[sys.argv.index('--out')+1])\n"
        "(out/'workflow').mkdir(parents=True, exist_ok=True)\n"
        "(out/'workflow'/'plan.json').write_text('{\"evidence_used\": []}', encoding='utf-8')\n"
        "(out/'workflow'/'plan.md').write_text('# plan\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest_path = assets / "manifest.json"
    manifest_path.write_text(json.dumps({"inputs": {"algorithm": {"mode": "official_example_attempt"}}}), encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "workflow_engine", "status": "verified", "entrypoint": "global", "command": [sys.executable, "-c", "raise SystemExit(99)"], "caveats": []}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(json.dumps({"default_example_id": None, "examples": []}), encoding="utf-8")

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_child_run_empty_catalog", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        run_module = import_module_from_path("_paper2skill_child_run_empty_catalog", scripts / "run.py")
        rc = run_module.main(
            [
                "--manifest",
                str(manifest_path),
                "--out",
                str(skill_root / "result"),
                "--example-id",
                "missing",
                "--verification-run",
            ]
        )
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_child_run_empty_catalog", "env_manager"]:
            sys.modules.pop(module_name, None)

    adapter_report = json.loads((skill_root / "result" / "workflow" / "adapter_report.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert adapter_report["status"] == "fail"
    assert adapter_report["example_id"] == "missing"


def test_unknown_explicit_example_id_raises() -> None:
    catalog = {"examples": [{"example_id": "known", "adapter": {"status": "dry_run_only"}}]}

    with pytest.raises(ValueError, match="unknown_example_id:missing"):
        build_validator.select_example(catalog, "missing")


def test_validation_gate_resolves_default_example_for_custom_manifest(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    references = root / "references"
    assets = root / "assets"
    build_validation = root / "build_validation"
    references.mkdir(parents=True)
    assets.mkdir()
    build_validation.mkdir()
    (assets / "official_attempt_manifest.yaml").write_text("inputs: {}\n", encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(json.dumps({"adapter_type": "notebook", "status": "dry_run_only"}), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "default_demo",
                "examples": [{"example_id": "default_demo", "adapter": {"status": "dry_run_only"}}],
            }
        ),
        encoding="utf-8",
    )
    manifest = build_validation / "custom_validation.yaml"
    manifest.write_text(
        "validation_type: build_time_self_check\n"
        "validation_depth: data_smoke\n"
        "data_kind: minimal\n"
        "manifest_path: assets/official_attempt_manifest.yaml\n"
        "expected_outputs:\n"
        "  - results/summary.json\n",
        encoding="utf-8",
    )

    gate = build_validator.verification_execution_gate(root, depth="data_smoke", manifest=manifest)

    assert gate["passed"] is True
    assert gate["example_id"] == "default_demo"


def test_mark_verified_only_updates_selected_example(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    references = root / "references"
    references.mkdir(parents=True)
    (references / "adapter_spec.yaml").write_text(json.dumps({"adapter_type": "notebook", "status": "dry_run_only"}), encoding="utf-8")
    (references / "adapter_review.yaml").write_text(json.dumps({"adapter_type": "notebook", "status": "dry_run_only", "expected_outputs": []}), encoding="utf-8")
    (references / "algorithm_contract.yaml").write_text(json.dumps({"algorithm": {"adapter_status": "dry_run_only", "maturity_level": "L1"}}), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "demo_a",
                "examples": [
                    {"example_id": "demo_a", "adapter": {"status": "dry_run_only"}},
                    {"example_id": "demo_b", "adapter": {"status": "dry_run_only"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = root / "result"
    (result / "qc").mkdir(parents=True)
    (result / "qc" / "output_validation.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    build_validator.mark_verified(
        root,
        execution={"status": "pass", "result_dir": "result", "output_validation": {"status": "pass"}},
        gate={"example_id": "demo_b", "expected_outputs": ["results/summary.json"], "manifest_data": {"validation_depth": "data_smoke"}},
    )

    spec = yaml.safe_load((references / "adapter_spec.yaml").read_text(encoding="utf-8"))
    review = yaml.safe_load((references / "adapter_review.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((references / "examples_catalog.yaml").read_text(encoding="utf-8"))
    statuses = {item["example_id"]: item["adapter"]["status"] for item in catalog["examples"]}

    assert spec["status"] == "verified"
    assert review["status"] == "verified"
    assert statuses == {"demo_a": "dry_run_only", "demo_b": "verified"}
    assert [item for item in catalog["examples"] if item["example_id"] == "demo_b"][0]["verification"]["source"] == "run_trace"


def test_validate_outputs_uses_executed_example_contract(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "validate-contract-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    result = skill_root / "result"
    references.mkdir(parents=True)
    for source, target in {
        "scripts/validate_outputs.py.j2": scripts / "validate_outputs.py",
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
    }.items():
        write_child_template(template_root, source, target)
    (references / "adapter_review.yaml").write_text(json.dumps({"expected_outputs": []}), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "default_demo",
                "examples": [
                    {
                        "example_id": "default_demo",
                        "output_contract": {"required_files": ["results/default.json"], "json": {"results/default.json": {"required_keys": ["ok"]}}},
                    },
                    {
                        "example_id": "executed_demo",
                        "output_contract": {"required_files": ["results/executed.json"], "json": {"results/executed.json": {"required_keys": ["ok"]}}, "nonempty": ["results/executed.json"]},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    for rel in [
        "result.json",
        "qc/input_validation.json",
        "qc/environment_report.json",
        "qc/missing_dependencies.json",
        "qc/qc_summary.json",
        "workflow/plan.json",
        "workflow/executed_steps.json",
        "parameters/resolved_parameters.json",
        "parameters/parameter_sources.json",
        "results/summary.json",
        "reproducibility/source_manifest.json",
        "reproducibility/algorithm_contract.yaml",
        "reproducibility/bio_contract.yaml",
        "reproducibility/environment_spec.yaml",
    ]:
        path = result / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    (result / "workflow" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (result / "workflow" / "adapter_report.json").write_text(json.dumps({"example_id": "executed_demo"}), encoding="utf-8")
    (result / "results" / "executed.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_validate_outputs", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        validate_module = import_module_from_path("_paper2skill_validate_outputs", scripts / "validate_outputs.py")
        rc = validate_module.main(["--result", str(result)])
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_validate_outputs", "env_manager"]:
            sys.modules.pop(module_name, None)

    output = json.loads((result / "qc" / "output_validation.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert output["example_id"] == "executed_demo"
    assert output["expected_outputs"] == ["results/executed.json"]

    validation_manifest = skill_root / "build_validation_manifest.yaml"
    validation_manifest.write_text(
        "validation_type: build_time_self_check\n"
        "validation_depth: data_smoke\n"
        "data_kind: minimal\n"
        "manifest_path: assets/input_manifest.yaml\n",
        encoding="utf-8",
    )
    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_validate_outputs_manifest", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        validate_module = import_module_from_path("_paper2skill_validate_outputs_manifest", scripts / "validate_outputs.py")
        rc = validate_module.main(["--result", str(result), "--validation-manifest", str(validation_manifest)])
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_validate_outputs_manifest", "env_manager"]:
            sys.modules.pop(module_name, None)

    output = json.loads((result / "qc" / "output_validation.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert output["example_id"] == "executed_demo"
    assert output["expected_outputs"] == ["results/executed.json"]


def test_official_rscript_adapter_fails_when_inputs_are_missing(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "rscript-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    repo = skill_root / "sources" / "repo"
    references.mkdir(parents=True)
    repo.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/official_rscript_adapter.py.j2": scripts / "adapters" / "official_rscript_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    (repo / "run.R").write_text("print('ok')\n", encoding="utf-8")
    (references / "source_manifest.json").write_text(json.dumps({"repo": {"resolved_path": str(repo)}}), encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "r_script", "status": "dry_run_only", "official_command": "Rscript run.R missing_counts.txt"}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "r_demo",
                "examples": [
                    {"example_id": "r_demo", "adapter": {"official_command": "Rscript run.R missing_counts.txt", "status": "verified"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = skill_root / "manifest.json"
    manifest_path.write_text(json.dumps({"inputs": {"algorithm": {"example_id": "r_demo"}}}), encoding="utf-8")

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_official_rscript", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_official_rscript", scripts / "adapters" / "official_rscript_adapter.py")
        rc = adapter_module.main([str(manifest_path), str(skill_root / "result")])
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_official_rscript", "env_manager"]:
            sys.modules.pop(module_name, None)

    summary = json.loads((skill_root / "result" / "results" / "summary.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert summary["failure_code"] == "required_official_input_missing"
    assert summary["missing_args"] == ["missing_counts.txt"]


def test_official_rscript_adapter_does_not_substitute_unrelated_manifest_input(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "rscript-unrelated-input-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    repo = skill_root / "sources" / "repo"
    data_dir = skill_root / "assets" / "data"
    references.mkdir(parents=True)
    repo.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/official_rscript_adapter.py.j2": scripts / "adapters" / "official_rscript_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    (repo / "run.R").write_text("print('ok')\n", encoding="utf-8")
    (data_dir / "metadata.tsv").write_text("sample\tgroup\ns1\ta\n", encoding="utf-8")
    (references / "source_manifest.json").write_text(json.dumps({"repo": {"resolved_path": str(repo)}}), encoding="utf-8")
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "r_script", "status": "dry_run_only", "official_command": "Rscript run.R missing_counts.txt"}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "r_demo",
                "examples": [
                    {"example_id": "r_demo", "adapter": {"official_command": "Rscript run.R missing_counts.txt", "status": "verified"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = skill_root / "manifest.json"
    manifest_path.write_text(
        json.dumps({"inputs": {"primary_data": {"path": "assets/data/metadata.tsv"}, "algorithm": {"example_id": "r_demo"}}}),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_official_rscript_unrelated", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_official_rscript_unrelated", scripts / "adapters" / "official_rscript_adapter.py")
        rc = adapter_module.main([str(manifest_path), str(skill_root / "result")])
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_official_rscript_unrelated", "env_manager"]:
            sys.modules.pop(module_name, None)

    summary = json.loads((skill_root / "result" / "results" / "summary.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert summary["failure_code"] == "required_official_input_missing"
    assert summary["missing_args"] == ["missing_counts.txt"]
    assert not (skill_root / "result" / "adapter_work" / "official_rscript" / "repo" / "missing_counts.txt").exists()


def test_command_adapter_uses_selected_example_command_and_outputs(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "command-example-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/command_adapter.py.j2": scripts / "adapters" / "command_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    command_a = (
        "from pathlib import Path; import os; "
        "out = Path(os.environ['PAPER2SKILL_OUT']); "
        "(out/'results').mkdir(parents=True, exist_ok=True); "
        "(out/'results'/'a.txt').write_text('a', encoding='utf-8')"
    )
    command_b = (
        "from pathlib import Path; import os; "
        "out = Path(os.environ['PAPER2SKILL_OUT']); "
        "(out/'results').mkdir(parents=True, exist_ok=True); "
        "(out/'results'/'b.txt').write_text('b', encoding='utf-8')"
    )
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "workflow_engine", "status": "dry_run_only", "command": [sys.executable, "-c", command_a]}),
        encoding="utf-8",
    )
    (references / "adapter_review.yaml").write_text(json.dumps({"expected_outputs": ["results/a.txt"]}), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(
        json.dumps(
            {
                "default_example_id": "demo_a",
                "examples": [
                    {
                        "example_id": "demo_a",
                        "adapter": {"status": "verified", "command": [sys.executable, "-c", command_a], "entrypoint": "a"},
                        "output_contract": {"required_files": ["results/a.txt"]},
                    },
                    {
                        "example_id": "demo_b",
                        "adapter": {"status": "verified", "command": [sys.executable, "-c", command_b], "entrypoint": "b"},
                        "output_contract": {"required_files": ["results/b.txt"]},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_command_adapter", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_command_adapter", scripts / "adapters" / "command_adapter.py")
        out = skill_root / "result"
        report = adapter_module.run_reviewed_command("workflow_engine", {"inputs": {}}, out, example_id="demo_b")
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_command_adapter", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert report["status"] == "pass"
    assert report["entrypoint"] == "b"
    assert report["outputs"] == ["results/b.txt"]
    assert not (out / "results" / "a.txt").exists()
    assert (out / "results" / "b.txt").read_text(encoding="utf-8") == "b"


def test_command_adapter_fails_on_unknown_explicit_example_even_during_verification(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "command-missing-example-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/command_adapter.py.j2": scripts / "adapters" / "command_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    command = (
        "from pathlib import Path; import os; "
        "out = Path(os.environ['PAPER2SKILL_OUT']); "
        "(out/'results').mkdir(parents=True, exist_ok=True); "
        "(out/'results'/'global.txt').write_text('global', encoding='utf-8')"
    )
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "workflow_engine", "status": "verified", "command": [sys.executable, "-c", command]}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(
        json.dumps({"default_example_id": "known", "examples": [{"example_id": "known", "adapter": {"status": "verified"}}]}),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_command_adapter_missing", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_command_adapter_missing", scripts / "adapters" / "command_adapter.py")
        out = skill_root / "result"
        report = adapter_module.run_reviewed_command("workflow_engine", {"inputs": {}}, out, example_id="missing", verification_run=True)
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_command_adapter_missing", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert report["status"] == "fail"
    assert report["example_id"] == "missing"
    assert not (out / "results" / "global.txt").exists()


def test_command_adapter_fails_explicit_example_when_catalog_empty(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "command-empty-catalog-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/command_adapter.py.j2": scripts / "adapters" / "command_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    command = (
        "from pathlib import Path; import os; "
        "out = Path(os.environ['PAPER2SKILL_OUT']); "
        "(out/'results').mkdir(parents=True, exist_ok=True); "
        "(out/'results'/'global.txt').write_text('global', encoding='utf-8')"
    )
    (references / "adapter_spec.yaml").write_text(
        json.dumps({"adapter_type": "workflow_engine", "status": "verified", "command": [sys.executable, "-c", command]}),
        encoding="utf-8",
    )
    (references / "examples_catalog.yaml").write_text(json.dumps({"examples": []}), encoding="utf-8")

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_command_adapter_empty_catalog", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_command_adapter_empty_catalog", scripts / "adapters" / "command_adapter.py")
        out = skill_root / "result"
        report = adapter_module.run_reviewed_command("workflow_engine", {"inputs": {}}, out, example_id="missing", verification_run=True)
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_command_adapter_empty_catalog", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert report["status"] == "fail"
    assert report["example_id"] == "missing"
    assert not (out / "results" / "global.txt").exists()


def test_notebook_adapter_fails_on_unknown_explicit_example(tmp_path: Path) -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    skill_root = tmp_path / "notebook-example-skill"
    scripts = skill_root / "scripts"
    references = skill_root / "references"
    references.mkdir(parents=True)
    for source, target in {
        "scripts/env_manager.py.j2": scripts / "env_manager.py",
        "scripts/adapters/notebook_adapter.py.j2": scripts / "adapters" / "notebook_adapter.py",
    }.items():
        write_child_template(template_root, source, target)
    (references / "adapter_spec.yaml").write_text(json.dumps({"adapter_type": "notebook", "status": "dry_run_only"}), encoding="utf-8")
    (references / "examples_catalog.yaml").write_text(
        json.dumps({"default_example_id": "known", "examples": [{"example_id": "known", "source": "demo.ipynb", "adapter": {"status": "verified"}}]}),
        encoding="utf-8",
    )

    original_sys_path = list(sys.path)
    for module_name in ["_paper2skill_notebook_adapter", "env_manager"]:
        sys.modules.pop(module_name, None)
    try:
        adapter_module = import_module_from_path("_paper2skill_notebook_adapter", scripts / "adapters" / "notebook_adapter.py")
        report = adapter_module.run({"inputs": {}}, skill_root / "result", example_id="missing")
    finally:
        sys.path[:] = original_sys_path
        for module_name in ["_paper2skill_notebook_adapter", "env_manager"]:
            sys.modules.pop(module_name, None)

    assert report["status"] == "fail"
    assert report["example_id"] == "missing"
    assert "selected example is missing" in report["message"]


def test_workflow_engine_routes_to_verified_command_adapter(tmp_path: Path) -> None:
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
        "status": "dry_run_only",
        "entrypoint": "python-workflow",
        "command": [sys.executable, "-c", command_script],
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    adapter_review = {
        **adapter_spec,
        "verification": {"status": "not_run"},
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

        blocked = run_module.run_adapter("workflow_engine", {"inputs": {}}, out, manifest_path)
        report = run_module.run_adapter("workflow_engine", {"inputs": {}}, out, manifest_path, verification_run=True)
    finally:
        sys.path[:] = original_sys_path
        for module_name in imported_modules:
            sys.modules.pop(module_name, None)

    assert blocked["status"] == "blocked"
    assert report["status"] == "pass"
    assert report["adapter_type"] == "workflow_engine"
    assert report["outputs"] == ["results/workflow.txt"]
    assert (out / "results" / "workflow.txt").read_text(encoding="utf-8") == "workflow ok"
    assert (out / "logs" / "workflow_engine_adapter.stdout.log").exists()
