from __future__ import annotations

from pathlib import Path
import sys

import yaml


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from paper2skill.build_validation.validator import generated_validation_manifest
from paper2skill.cli import resolve_run_example_paths
from paper2skill.compiler import build_tutorial_catalog, evaluate_maturity, promote_from_run_trace, run_trace_passed


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
    }

    result = promote_from_run_trace(adapter_spec=adapter_spec, adapter_review=adapter_review, tutorial_catalog=catalog, run_trace=trace)

    selected = result["tutorial_catalog"]["examples"][0]
    assert result["promoted"]
    assert selected["adapter"]["status"] == "verified"
    assert selected["outputs"] == ["results/custom.json"]
    assert selected["expected_outputs"] == ["results/custom.json"]
    assert selected["output_contract"]["required_files"] == ["results/custom.json"]
    assert selected["output_contract"]["nonempty"] == ["results/custom.json"]


def test_verified_adapter_without_run_trace_stays_l1() -> None:
    maturity = evaluate_maturity(
        {"adapter_type": "cli", "status": "verified"},
        {"default_example_id": "demo", "examples": [{"example_id": "demo", "adapter": {"status": "verified"}}]},
        run_trace=None,
    )

    assert maturity["level"] == "L1"
    assert maturity["status"] == "verified_adapter_requires_attached_run_trace"
    assert maturity["verified_examples"] == []
