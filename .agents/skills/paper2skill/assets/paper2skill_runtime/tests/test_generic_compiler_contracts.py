from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from paper2skill.build_validation.validator import generated_validation_manifest
from paper2skill.cli import resolve_run_example_paths
from paper2skill.compiler import (
    build_tutorial_catalog,
    evaluate_maturity,
    promote_from_run_trace,
    run_trace_passed,
    run_trace_promotion_ready,
    run_trace_promotion_rejections,
    update_algorithm_contract_after_promotion,
)
from paper2skill.build_validation.skill_package import REQUIRED_SKILL_FILES
from paper2skill.evaluation.run_benchmark import DEFAULT_EVIDENCE_FILES, validate_algorithm_routing_contract
from paper2skill.generators.codex_skill_generator import build_applicability_contract, build_context, build_recommended_execution
from paper2skill.miners.tutorial_scanner import scan_tutorial_candidates
from paper2skill.reproduction.agentic import ReproduceConfig, apply_agentic_repair, classify_agentic_failure
from paper2skill.validators.skill_validator import REQUIRED_FILES


def test_run_example_paths_are_resolved_before_cwd_switch(tmp_path: Path, monkeypatch) -> None:
    caller = tmp_path / "caller"
    skill = tmp_path / "algorithm-skill"
    manifest = caller / "manifests" / "demo.yaml"
    caller.mkdir()
    skill.mkdir()
    manifest.parent.mkdir()
    manifest.write_text("inputs: {}\n", encoding="utf-8")
    monkeypatch.chdir(caller)

    paths = resolve_run_example_paths("../algorithm-skill", "paper2skill_run", "manifests/demo.yaml")

    assert paths["skill"] == skill.resolve()
    assert paths["out"] == (caller / "paper2skill_run").resolve()
    assert paths["result_dir"] == (caller / "paper2skill_run" / "result").resolve()
    assert paths["manifest"] == manifest.resolve()


def test_tutorial_catalog_is_the_required_catalog_artifact() -> None:
    assert "references/tutorial_catalog.yaml" in REQUIRED_FILES
    assert "references/tutorial_catalog.yaml" in REQUIRED_SKILL_FILES
    assert "references/examples_catalog.yaml" not in REQUIRED_FILES
    assert "references/examples_catalog.yaml" not in REQUIRED_SKILL_FILES


def test_official_attempt_manifest_is_the_default_child_skill_entrypoint() -> None:
    template_root = RUNTIME_ROOT / "paper2skill" / "templates" / "codex_skill"
    for relative in ["scripts/preflight.py.j2", "scripts/plan.py.j2", "scripts/run.py.j2", "scripts/run_in_env.sh.j2"]:
        text = (template_root / relative).read_text(encoding="utf-8")
        assert "official_attempt_manifest.yaml" in text
        assert "demo_input_manifest.yaml" not in text
    assert "assets/official_attempt_manifest.yaml" in REQUIRED_FILES
    assert "assets/official_attempt_manifest.yaml" in REQUIRED_SKILL_FILES
    assert "assets/demo_input_manifest.yaml" not in REQUIRED_FILES
    assert "assets/demo_input_manifest.yaml" not in REQUIRED_SKILL_FILES


def test_algorithm_contract_exposes_applicability_and_recommended_execution() -> None:
    adapter_spec = {
        "adapter_type": "python_api",
        "status": "dry_run_only",
        "entrypoint": "pkg.api:run",
        "module": "pkg.api",
        "function": "run",
    }
    tutorial_catalog = {
        "default_example_id": "official_minimal",
        "examples": [{"example_id": "official_minimal", "source": "docs/tutorial.py"}],
    }
    bio_contract = {
        "bio_contract": {
            "modality": {
                "primary": {
                    "value": "scRNA-seq",
                    "confidence": "high",
                    "evidence_id": "tutorial:docs/tutorial.py",
                    "source_type": "official_tutorial",
                    "claim_type": "official_tutorial",
                }
            }
        }
    }
    maturity = {"level": "L1", "status": "contract_only"}

    applicability = build_applicability_contract(
        task="single_cell_integration",
        classification={"domain": "bioinformatics", "language": "python"},
        algorithm_archetype={"archetype": "python_api_package"},
        adapter_spec=adapter_spec,
        tutorial_catalog=tutorial_catalog,
        bio_contract=bio_contract,
        maturity=maturity,
    )
    recommended = build_recommended_execution(adapter_spec, tutorial_catalog, maturity)

    assert applicability["supported_task"] == "single_cell_integration"
    assert applicability["modality"] == "scRNA-seq"
    assert applicability["real_execution_allowed"] is False
    assert "verified_run" not in applicability["allowed_execution_modes"]
    assert {rule["code"] for rule in applicability["refusal_rules"]} >= {
        "unsupported_task",
        "adapter_not_verified",
        "bio_contract_mismatch",
    }
    assert recommended["default_manifest"] == "assets/official_attempt_manifest.yaml"
    assert recommended["core_api"] == {
        "adapter_type": "python_api",
        "entrypoint": "pkg.api:run",
        "module": "pkg.api",
        "function": "run",
    }
    assert recommended["can_execute_real_data"] is False


def test_promotion_updates_algorithm_contract_routing_fields() -> None:
    updated = update_algorithm_contract_after_promotion(
        {
            "algorithm": {"adapter_status": "dry_run_only", "maturity_level": "L1"},
            "applicability": {"allowed_execution_modes": ["preflight", "plan", "dry_run"]},
            "recommended_execution": {},
        },
        {"adapter_type": "cli", "status": "verified", "entrypoint": "tool", "command": "tool --in {manifest}"},
        {"level": "L2", "status": "official_or_minimal_example_verified"},
    )

    assert updated["algorithm"]["adapter_status"] == "verified"
    assert updated["algorithm"]["maturity_level"] == "L2"
    assert updated["applicability"]["real_execution_allowed"] is True
    assert "verified_run" in updated["applicability"]["allowed_execution_modes"]
    assert updated["recommended_execution"]["default_manifest"] == "assets/official_attempt_manifest.yaml"
    assert updated["recommended_execution"]["core_api"]["command"] == "tool --in {manifest}"
    assert updated["recommended_execution"]["can_execute_real_data"] is True


def test_benchmark_l1_requires_algorithm_routing_contract(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    contract_dir = skill / "references" / "contracts"
    contract_dir.mkdir(parents=True)
    contract = {
        "algorithm": {
            "task": "single_cell_integration",
            "domain": "bioinformatics",
            "modality": "not_confirmed",
            "adapter_status": "dry_run_only",
            "maturity_level": "L1",
        },
        "applicability": {
            "supported_task": "single_cell_integration",
            "domain": "bioinformatics",
            "modality": "not_confirmed",
            "allowed_execution_modes": ["preflight", "plan", "dry_run"],
            "real_execution_allowed": False,
            "refusal_rules": [
                {"code": "unsupported_task"},
                {"code": "adapter_not_verified"},
                {"code": "bio_contract_mismatch"},
            ],
        },
        "recommended_execution": {
            "default_manifest": "assets/official_attempt_manifest.yaml",
            "entrypoints": {
                "preflight": "python scripts/preflight.py --manifest assets/official_attempt_manifest.yaml",
                "plan": "python scripts/plan.py --manifest assets/official_attempt_manifest.yaml",
                "run": "python scripts/run.py --manifest assets/official_attempt_manifest.yaml",
                "validate_outputs": "python scripts/validate_outputs.py --result result",
            },
            "real_execution_requires": ["adapter_status=verified", "non_demo_run_trace"],
            "can_execute_real_data": False,
        },
    }
    (contract_dir / "algorithm_contract.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    report = validate_algorithm_routing_contract(skill)
    assert report["passed"]
    assert "references/tutorial_catalog.yaml" in DEFAULT_EVIDENCE_FILES
    assert "references/contracts/algorithm_contract.yaml" in DEFAULT_EVIDENCE_FILES

    contract["recommended_execution"].pop("default_manifest")
    (contract_dir / "algorithm_contract.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    report = validate_algorithm_routing_contract(skill)
    assert not report["passed"]
    assert "recommended_execution.default_manifest" in report["missing"]


def test_tutorial_catalog_filters_documentation_urls_from_data_sources() -> None:
    catalog = build_tutorial_catalog(
        {
            "tutorials": [
                {
                    "path": "docs/tutorial.md",
                    "cells": [
                        "Read https://project.readthedocs.io/en/latest/index.html",
                        "Install notes: https://pytorch.org/get-started/locally",
                        "Data: https://example.org/data/demo.h5ad",
                    ],
                }
            ]
        },
        {"adapter_type": "notebook", "status": "dry_run_only", "expected_outputs": []},
        {},
        {"language": "python"},
        {"archetype": "notebook_tutorial", "adapter_type": "notebook", "interface": {}},
        user_data_urls=[
            "https://docs.example.org/data.**",
            "https://drive.google.com/uc?id=official-example",
            "https://example.org/data/user_demo.h5ad",
        ],
    )

    urls = [source["url"] for source in catalog["examples"][0]["inputs"]["data_sources"]]
    compat_urls = [source["url"] for source in catalog["examples"][0]["data_sources"]]

    assert "https://example.org/data/demo.h5ad" in urls
    assert "https://drive.google.com/uc?id=official-example" in urls
    assert "https://example.org/data/user_demo.h5ad" in urls
    assert compat_urls == urls
    assert all("readthedocs" not in url for url in urls)
    assert all("pytorch.org/get-started" not in url for url in urls)
    assert all(not url.endswith(".**") for url in urls)


def test_tutorial_catalog_matches_user_data_urls_per_tutorial() -> None:
    catalog = build_tutorial_catalog(
        {
            "tutorials": [
                {"path": "docs/batch.ipynb", "cells": ["train = sc.read('.pancreas.h5ad')"]},
                {"path": "docs/perturb.ipynb", "cells": ["train = sc.read('.train_kang.h5ad')"]},
            ]
        },
        {"adapter_type": "notebook", "status": "dry_run_only", "expected_outputs": []},
        {},
        {"language": "python"},
        {"archetype": "notebook_tutorial", "adapter_type": "notebook", "interface": {}},
        user_data_urls=[
            "https://example.org/data/train_kang.h5ad?download=1",
            "https://www.dropbox.com/s/qj1jlm9w10wmt0u/pancreas.h5ad?dl=1",
            "https://example.org/data/unrelated.h5ad",
        ],
    )

    sources = {item["example_id"]: [source["filename"] for source in item["data_sources"]] for item in catalog["examples"]}

    assert sources["batch"] == ["pancreas.h5ad"]
    assert sources["perturb"] == ["train_kang.h5ad"]
    assert [source["filename"] for source in catalog["unmatched_data_urls"]] == ["unrelated.h5ad"]


def test_catalog_all_tutorials_keeps_indexed_scgen_tutorials_with_explicit_default(tmp_path: Path) -> None:
    repo = tmp_path / "scgen"
    docs = repo / "docs" / "tutorials"
    docs.mkdir(parents=True)
    (repo / "README.md").write_text("# scGen\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'scgen-fixture'\n", encoding="utf-8")
    (docs / "index.rst").write_text(
        "\n".join(
            [
                "Tutorials",
                "=========",
                "",
                ".. toctree::",
                "   :maxdepth: 1",
                "",
                "   Perturbation prediction <scgen_perturbation_prediction>",
                "   Batch removal <scgen_batch_removal>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_notebook(docs / "scgen_perturbation_prediction.ipynb", "scGen perturbation prediction", "import scgen\nadata = sc.read('train.h5ad')\n")
    write_notebook(docs / "scgen_batch_removal.ipynb", "scGen batch removal", "import scgen\nadata = sc.read('pancreas.h5ad')\n")
    paper = tmp_path / "paper.md"
    paper.write_text("# scGen predicts single-cell perturbation responses\n", encoding="utf-8")

    context = build_context(
        skill_name="scgen-skill",
        algorithm_name="scGen",
        task="single_cell_perturbation_prediction",
        paper=str(paper),
        repo=str(repo),
        tutorials=["docs/tutorials/scgen_perturbation_prediction.ipynb"],
        catalog_all_tutorials=True,
        collection_dir=tmp_path / ".collection",
    )

    example_ids = {item["example_id"] for item in context["tutorial_catalog"]["examples"]}
    assert {"scgen_perturbation_prediction", "scgen_batch_removal"} <= example_ids
    assert context["tutorial_catalog"]["default_example_id"] == "scgen_perturbation_prediction"
    assert not context["tutorial_trace"]["tutorial_scanner_report"]["missing_indexed_tutorials"]

    filter_context = build_context(
        skill_name="scgen-skill-filter",
        algorithm_name="scGen",
        task="single_cell_perturbation_prediction",
        paper=str(paper),
        repo=str(repo),
        tutorials=[],
        tutorial_filter="perturbation",
        catalog_all_tutorials=True,
        collection_dir=tmp_path / ".collection-filter",
    )
    filter_example_ids = {item["example_id"] for item in filter_context["tutorial_catalog"]["examples"]}
    assert {"scgen_perturbation_prediction", "scgen_batch_removal"} <= filter_example_ids
    assert filter_context["tutorial_catalog"]["default_example_id"] == "scgen_perturbation_prediction"


def test_indexed_tutorial_gaps_are_reported(tmp_path: Path) -> None:
    repo = tmp_path / "scgen"
    docs = repo / "docs" / "tutorials"
    docs.mkdir(parents=True)
    (docs / "index.rst").write_text(
        "\n".join(
            [
                ".. toctree::",
                "",
                "   scgen_perturbation_prediction",
                "   scgen_batch_removal",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_notebook(docs / "scgen_perturbation_prediction.ipynb", "scGen perturbation prediction", "import scgen\n")

    scan = scan_tutorial_candidates(repo)
    missing = scan["report"]["missing_indexed_tutorials"]

    assert {"index": "docs/tutorials/index.rst", "target": "docs/tutorials/scgen_batch_removal.ipynb", "reason": "indexed_tutorial_missing"} in missing


def test_agentic_repair_classifier_covers_common_failure_modes() -> None:
    assert classify_agentic_failure({"execution": {"commands": [{"stderr_tail": "ResolutionImpossible: Cannot install ml-dtypes on Python 3.12"}]}})["code"] == "dependency_conflict_legacy_python"
    assert classify_agentic_failure({"execution": {"commands": [{"stderr_tail": "ModuleNotFoundError: No module named 'scgen'"}]}})["code"] == "dependencies_missing"
    assert classify_agentic_failure({"execution": {"commands": [{"stderr_tail": "FileNotFoundError: train.h5ad"}]}})["code"] == "data_path_missing"
    assert classify_agentic_failure({"execution": {"commands": [{"stderr_tail": "AttributeError: SCGEN object has no attribute get_latent"}]}})["code"] == "api_signature_drift"
    assert classify_agentic_failure({"errors": ["expected_outputs_missing"]})["code"] == "output_missing"


def test_legacy_dependency_repair_relaxes_generated_requirement_pins(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    (skill / "assets").mkdir(parents=True)
    (skill / "references").mkdir()
    requirements = skill / "assets" / "requirements.txt"
    requirements.write_text("numpy==1.23.0\ncustom-package==0.1.0\n", encoding="utf-8")

    repair = apply_agentic_repair(
        skill,
        {"code": "dependency_conflict_legacy_python", "summary": "Python 3.12 legacy pin conflict"},
        attempt=1,
        config=ReproduceConfig(),
    )

    assert repair["status"] == "applied"
    assert "numpy>=1.23.0" in requirements.read_text(encoding="utf-8")
    assert "custom-package==0.1.0" in requirements.read_text(encoding="utf-8")
    assert (skill / "assets" / "requirements.txt.before_agentic_repair").is_file()


def write_notebook(path: Path, title: str, code: str) -> None:
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n"]},
                    {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [code]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )


def test_generated_validation_manifest_uses_catalog_data_kind_and_nested_sources(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    (root / "assets").mkdir(parents=True)
    (root / "references").mkdir()
    (root / "assets" / "input_manifest_template.yaml").write_text("inputs: {}\n", encoding="utf-8")
    catalog = {
        "default_example_id": "large_demo",
        "examples": [
            {
                "example_id": "large_demo",
                "source": "docs/large.ipynb",
                "scenario": "notebook_demo",
                "data_kind": "large",
                "inputs": {"data_sources": [{"type": "url", "url": "https://example.org/data/large.h5ad", "filename": "large.h5ad"}]},
                "output_contract": {"required_files": ["results/custom.json"]},
            }
        ],
    }
    (root / "references" / "tutorial_catalog.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    manifest_path = generated_validation_manifest(root, depth="data_smoke", example_id=None)

    assert manifest_path is not None
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data_kind"] == "large"
    assert manifest["expected_outputs"] == ["results/custom.json"]
    assert manifest["official_example"]["data_sources"] == [{"type": "url", "url": "https://example.org/data/large.h5ad", "filename": "large.h5ad"}]


def test_run_trace_requires_output_validation_pass() -> None:
    assert not run_trace_passed(
        {
            "status": "pass",
            "produced_files": [{"path": "results/summary.json", "size_bytes": 10}],
            "output_validation": {"status": "not_run"},
        }
    )
    assert not run_trace_passed({"status": "fail", "produced_files": [], "output_validation": {"status": "pass"}})
    assert not run_trace_passed({"status": "error", "produced_files": [], "output_validation": {"status": "pass"}})
    assert run_trace_passed({"status": "pass", "produced_files": [], "output_validation": {"status": "pass"}})
    assert not run_trace_promotion_ready({"status": "pass", "produced_files": [], "output_validation": {"status": "pass"}})
    assert "adapter_report_missing" in run_trace_promotion_rejections({"status": "pass", "produced_files": [], "output_validation": {"status": "pass"}})


def test_promotion_refuses_trace_without_output_validation() -> None:
    adapter_spec = {"adapter_type": "cli", "status": "dry_run_only", "expected_outputs": []}
    adapter_review = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "tool",
        "command": "tool",
        "verification": {"status": "not_run"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }
    catalog = {
        "default_example_id": "demo",
        "examples": [{"example_id": "demo", "adapter": {"status": "dry_run_only"}, "verification": {"status": "not_run"}, "maturity": "L1"}],
    }
    trace = {
        "status": "pass",
        "example_id": "demo",
        "produced_files": [{"path": "results/summary.json", "size_bytes": 10}],
        "output_validation": {"status": "not_run"},
    }

    result = promote_from_run_trace(adapter_spec=adapter_spec, adapter_review=adapter_review, tutorial_catalog=catalog, run_trace=trace)

    assert not result["promoted"]
    assert result["reason"] == "run_trace_output_validation_not_passed"
    assert result["adapter_spec"]["status"] == "dry_run_only"


def test_promotion_refuses_demo_trace_without_adapter_execution() -> None:
    adapter_spec = {"adapter_type": "cli", "status": "dry_run_only", "expected_outputs": []}
    adapter_review = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "tool",
        "command": "tool",
        "verification": {"status": "not_run"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }
    catalog = {
        "default_example_id": "demo",
        "examples": [{"example_id": "demo", "adapter": {"status": "dry_run_only"}, "verification": {"status": "not_run"}, "maturity": "L1"}],
    }
    trace = {
        "status": "pass",
        "example_id": "demo",
        "produced_files": [{"path": "results/summary.json", "size_bytes": 10}],
        "output_validation": {"status": "pass", "expected_outputs": ["results/summary.json"]},
        "adapter_report": {"status": "dry_run_only", "example_id": "demo", "demo_mode": True},
        "input_bindings": {"manifest": {"inputs": {"algorithm": {"mode": "demo"}}}},
        "result_json": {"status": "pass"},
    }

    result = promote_from_run_trace(adapter_spec=adapter_spec, adapter_review=adapter_review, tutorial_catalog=catalog, run_trace=trace)

    assert not result["promoted"]
    assert result["reason"] == "demo_trace_not_promotable"
    assert "adapter_execution_not_passed" in result["promotion_rejections"]
    assert result["adapter_spec"]["status"] == "dry_run_only"
    assert result["maturity"]["level"] == "L1"


def test_promotion_refuses_unknown_catalog_example() -> None:
    adapter_spec = {"adapter_type": "cli", "status": "dry_run_only", "expected_outputs": []}
    adapter_review = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "tool",
        "command": "tool",
        "verification": {"status": "not_run"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }
    catalog = {
        "default_example_id": "demo",
        "examples": [{"example_id": "demo", "adapter": {"status": "dry_run_only"}, "verification": {"status": "not_run"}, "maturity": "L1"}],
    }
    trace = {
        "status": "pass",
        "example_id": "missing",
        "produced_files": [{"path": "results/custom.json", "size_bytes": 10}],
        "output_validation": {"status": "pass", "expected_outputs": ["results/custom.json"]},
        "adapter_report": {"status": "pass", "example_id": "missing", "adapter_type": "cli"},
        "input_bindings": {"manifest": {"inputs": {"algorithm": {"mode": "official_example_attempt"}}}},
        "result_json": {"status": "pass"},
    }

    result = promote_from_run_trace(adapter_spec=adapter_spec, adapter_review=adapter_review, tutorial_catalog=catalog, run_trace=trace)

    assert not result["promoted"]
    assert result["reason"] == "run_trace_example_not_in_catalog"
    assert result["example_id"] == "missing"
    assert result["adapter_spec"]["status"] == "dry_run_only"
    assert result["maturity"]["level"] == "L1"


def test_promotion_updates_catalog_output_contract() -> None:
    adapter_spec = {"adapter_type": "cli", "status": "dry_run_only", "expected_outputs": []}
    adapter_review = {
        "adapter_type": "cli",
        "status": "dry_run_only",
        "entrypoint": "tool",
        "command": "tool",
        "verification": {"status": "not_run"},
        "expected_outputs": [],
        "evidence": [],
        "caveats": [],
    }
    catalog = {
        "default_example_id": "demo",
        "examples": [
            {
                "example_id": "demo",
                "adapter": {"status": "dry_run_only"},
                "verification": {"status": "not_run"},
                "output_contract": {"required_files": ["results/summary.json"]},
                "maturity": "L1",
            }
        ],
    }
    trace = {
        "status": "pass",
        "example_id": "demo",
        "produced_files": [{"path": "results/custom.json", "size_bytes": 10}],
        "output_validation": {"status": "pass", "expected_outputs": ["results/custom.json"]},
        "adapter_report": {"status": "pass", "example_id": "demo", "adapter_type": "cli"},
        "input_bindings": {"manifest": {"inputs": {"algorithm": {"mode": "official_example_attempt"}}}},
        "result_json": {"status": "pass"},
    }

    result = promote_from_run_trace(adapter_spec=adapter_spec, adapter_review=adapter_review, tutorial_catalog=catalog, run_trace=trace)

    selected = result["tutorial_catalog"]["examples"][0]
    assert result["promoted"]
    assert selected["adapter"]["status"] == "verified"
    assert selected["outputs"] == ["results/custom.json"]
    assert selected["expected_outputs"] == ["results/custom.json"]
    assert selected["output_contract"]["required_files"] == ["results/custom.json"]
    assert selected["output_contract"]["nonempty"] == ["results/custom.json"]
    assert result["maturity"]["level"] == "L2"


def test_verified_adapter_without_run_trace_stays_l1() -> None:
    maturity = evaluate_maturity(
        {"adapter_type": "cli", "status": "verified"},
        {"default_example_id": "demo", "examples": [{"example_id": "demo", "adapter": {"status": "verified"}}]},
        run_trace=None,
    )

    assert maturity["level"] == "L1"
    assert maturity["status"] == "verified_adapter_requires_attached_run_trace"
    assert maturity["verified_examples"] == []
