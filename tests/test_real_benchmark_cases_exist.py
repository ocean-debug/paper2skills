from __future__ import annotations

from pathlib import Path


GOLD_FILES = {
    "source_collection.yaml",
    "dependency_contract.yaml",
    "tutorial_selection.yaml",
    "workflow_dag.yaml",
    "io_contract.yaml",
    "bio_contract.yaml",
    "adapter_behavior.yaml",
    "evidence_expectations.yaml",
    "metrics.yaml",
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
