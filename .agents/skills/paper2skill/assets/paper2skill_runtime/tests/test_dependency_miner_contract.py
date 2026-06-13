from __future__ import annotations

from pathlib import Path
import sys


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from paper2skill.miners.dependency_miner import constrain_legacy_scvi_tools
from paper2skill.env_rebuilder.routes import route_python_packages
from paper2skill.build_validation.skill_package import path_leakage
from paper2skill.build_validation.validator import stage_example_data_cache
from paper2skill.generators.codex_skill_generator import build_examples_catalog


def test_legacy_scvi_constraints_bound_transitive_stack() -> None:
    records = [
        {
            "spec": "scvi-tools>=0.14.5",
            "name": "scvi-tools",
            "import_name": "scvi",
            "required": True,
            "category": "runtime",
            "source": "requirements.txt",
            "evidence": "requirements.txt",
        }
    ]

    constrained = {record["name"]: record["spec"] for record in constrain_legacy_scvi_tools(records)}

    assert constrained["scvi-tools"] == "scvi-tools>=0.14.5,<1.0"
    assert constrained["jax"] == "jax<0.4.24,>=0.4.18"
    assert constrained["jaxlib"] == "jaxlib<0.4.24,>=0.4.18"
    assert constrained["flax"] == "flax<0.7.1,>=0.6.11"
    assert constrained["ml-dtypes"] == "ml-dtypes<0.3,>=0.2.0"
    assert constrained["optax"] == "optax<0.2"
    assert constrained["chex"] == "chex<0.1.8"
    assert constrained["numpyro"] == "numpyro<0.13"
    assert constrained["scipy"] == "scipy<1.13"
    assert constrained["pandas"] == "pandas<2"


def test_legacy_scvi_pip_first_route_uses_compatible_constraints() -> None:
    routed = route_python_packages(["scvi-tools>=0.20.0,<1.0"])
    uv = set(routed["uv"])

    assert "scvi-tools<1.0,>=0.20.0" in uv
    assert "jax<0.4.24,>=0.4.18" in uv
    assert "jaxlib<0.4.24,>=0.4.18" in uv
    assert "flax<0.7.1,>=0.6.11" in uv
    assert "pandas<2" in uv
    assert "flax<0.6" not in uv


def test_stage_example_data_cache_copies_declared_example_files(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "demo.h5ad").write_bytes(b"demo")
    manifest = {"official_example": {"data_sources": [{"filename": "demo.h5ad"}]}}

    records = stage_example_data_cache(root, manifest, cache)

    assert records[0]["status"] == "staged"
    assert (root / "assets" / "data" / "demo.h5ad").read_bytes() == b"demo"


def test_path_leakage_skips_staged_example_data(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    data_dir = root / "assets" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "demo.h5ad").write_bytes(b"C:\\Users\\someone\\raw-data")

    assert path_leakage(root) == []


def test_multiple_user_data_urls_are_matched_to_relevant_tutorials() -> None:
    catalog = build_examples_catalog(
        {
            "tutorials": [
                {"path": "docs/batch.ipynb", "cells": ["train = sc.read('.pancreas.h5ad')"]},
                {"path": "docs/perturb.ipynb", "cells": ["train = sc.read('.train_kang.h5ad')"]},
            ]
        },
        {"adapter_type": "notebook", "status": "dry_run_only", "entrypoint": "adapter.py", "command": ["python"]},
        {},
        {"language": "python"},
        user_data_urls=[
            "https://drive.google.com/uc?id=1r87vhoLLq6PXAYdmyyd89zG90eJOFYLk",
            "https://www.dropbox.com/s/qj1jlm9w10wmt0u/pancreas.h5ad?dl=1",
        ],
    )

    sources = {item["example_id"]: [source["filename"] for source in item["data_sources"]] for item in catalog["examples"]}

    assert sources["batch"] == ["pancreas.h5ad"]
    assert sources["perturb"] == ["train_kang.h5ad"]
