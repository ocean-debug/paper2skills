from __future__ import annotations

from pathlib import Path

import yaml


GOLD_FILES = {
    "case_metadata.yaml",
    "source_collection.yaml",
    "dependency_contract.yaml",
    "tutorial_selection.yaml",
    "workflow_dag.yaml",
    "io_contract.yaml",
    "bio_contract.yaml",
    "adapter_behavior.yaml",
    "evidence_expectations.yaml",
    "metrics.yaml",
    "level0_skill_package.yaml",
    "level2_official_examples.yaml",
    "level3_new_data.yaml",
    "level4_agentic_tasks.yaml",
}


def test_real_benchmark_case_structure_is_complete():
    root = Path("benchmarks/real")
    cases = sorted(path for path in root.iterdir() if path.is_dir())
    assert len(cases) == 5
    for case in cases:
        assert (case / "case.md").is_file()
        gold = case / "gold"
        assert gold.is_dir()
        present = {path.name for path in gold.glob("*.yaml")}
        assert GOLD_FILES <= present


def test_real_benchmark_l2_declared_files_exist():
    root = Path("benchmarks/real")
    for case in sorted(path for path in root.iterdir() if path.is_dir()):
        spec = yaml.safe_load((case / "gold" / "level2_official_examples.yaml").read_text(encoding="utf-8")) or {}
        for example in spec.get("official_examples") or []:
            declared = list(example.get("fixture_files") or [])
            reviewed = example.get("reviewed_adapter") if isinstance(example.get("reviewed_adapter"), dict) else {}
            declared.extend(reviewed.get("files") or [])
            for item in declared:
                source = item.get("source")
                if source:
                    assert (case / source).is_file(), f"{case.name}: missing L2 declared file {source}"
