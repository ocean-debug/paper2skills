from __future__ import annotations

from pathlib import Path

from paper2skill.evaluation.load_gold import GOLD_FILES, load_gold
from paper2skill.evaluation.validate_gold import validate_gold


REAL_BENCHMARK_ROOT = Path("benchmarks/real")


def test_real_benchmark_gold_cases_load():
    cases = sorted(path for path in REAL_BENCHMARK_ROOT.iterdir() if path.is_dir())
    assert [path.name for path in cases] == [
        "case_01_concord",
        "case_02_scgen",
        "case_03_gears",
        "case_04_augur",
        "case_05_deltate",
    ]
    for case in cases:
        loaded = load_gold(case)
        assert loaded["case_md_present"] is True
        assert loaded["missing_files"] == []
        assert set(loaded["gold"]) == set(GOLD_FILES)
        assert all(loaded["gold"][key] for key in GOLD_FILES)


def test_real_benchmark_gold_supports_multi_tutorial_and_pipeline_modes():
    scgen = load_gold(REAL_BENCHMARK_ROOT / "case_02_scgen")["gold"]
    gears = load_gold(REAL_BENCHMARK_ROOT / "case_03_gears")["gold"]

    assert scgen["case_metadata"]["tutorial_urls"]
    assert scgen["tutorial_selection"]["selection_mode"] == "multi_tutorial_multi_workflow"
    assert scgen["workflow_dag"]["workflow_mode"] == "multi_workflow"
    assert gears["tutorial_selection"]["selection_mode"] == "multi_tutorial_pipeline_stages"
    assert gears["workflow_dag"]["workflow_mode"] == "pipeline_workflow"
    assert gears["workflow_dag"]["workflows"][0]["stages"]


def test_real_benchmark_gold_validator_accepts_all_cases():
    for case in sorted(path for path in REAL_BENCHMARK_ROOT.iterdir() if path.is_dir()):
        result = validate_gold(case)
        assert result["passed"], result


def test_missing_generated_files_fail_gracefully(tmp_path):
    from paper2skill.evaluation.evaluate_case import evaluate_case

    result = evaluate_case(REAL_BENCHMARK_ROOT / "case_01_concord", tmp_path / "missing" / "references")

    assert result["passed"] is False
    assert result["missing_generated_files"]
    assert result["score"] < 85
    assert any("missing generated file" in warning for warning in result["warnings"])
