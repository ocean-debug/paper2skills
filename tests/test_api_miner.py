from __future__ import annotations

from pathlib import Path

from paper2skill.miners.api_miner import mine_api


def test_api_miner_detects_python_cli_entrypoints_and_workflows(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "cli-demo"
version = "0.1.0"

[project.scripts]
demo-tool = "demo.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "cli.py").write_text(
        """
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Snakefile").write_text("rule all:\n  input: []\n", encoding="utf-8")
    evidence = mine_api(tmp_path)
    assert evidence["entrypoints"] == [{"name": "demo-tool", "target": "demo.cli:main", "source": "pyproject.toml", "type": "console_script"}]
    assert evidence["cli_commands"][0]["framework"] == "argparse"
    assert evidence["workflow_engines"][0]["engine"] == "snakemake"


def test_api_miner_detects_r_namespace_exports(tmp_path: Path):
    (tmp_path / "DESCRIPTION").write_text("Package: demo\n", encoding="utf-8")
    (tmp_path / "NAMESPACE").write_text("export(run_demo, summarize)\n", encoding="utf-8")
    (tmp_path / "R").mkdir()
    (tmp_path / "R" / "demo.R").write_text("run_demo <- function(x) x\n", encoding="utf-8")
    evidence = mine_api(tmp_path)
    assert [item["name"] for item in evidence["r_exports"]] == ["run_demo", "summarize"]
