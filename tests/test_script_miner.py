from __future__ import annotations

from paper2skill.miners.script_miner import mine_script


def test_python_script_trace_extracts_imports_calls_and_paths():
    trace = mine_script("tests/fixtures/toy_script.py")
    assert trace["language"] == "python"
    assert "csv" in trace["imports"]
    assert "data/demo_input.csv" in trace["parameters"].values()
    assert trace["workflow_steps"]


def test_r_script_trace_extracts_library_and_io():
    trace = mine_script("tests/fixtures/toy_script.R")
    assert trace["language"] == "r"
    assert "stats" in trace["imports"]
    assert "data/demo_input.csv" in trace["file_reads"]
    assert "results/summary.csv" in trace["file_writes"]
