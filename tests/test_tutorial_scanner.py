from __future__ import annotations

from pathlib import Path

from paper2skill.miners.tutorial_scanner import scan_tutorial_candidates


def test_tutorial_scanner_prioritizes_docs_notebook_and_excludes_tests(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "legacy").mkdir()
    (tmp_path / "docs" / "tutorial.ipynb").write_text('{"cells": []}', encoding="utf-8")
    (tmp_path / "tests" / "test_example.py").write_text("print('test')\n", encoding="utf-8")
    (tmp_path / "legacy" / "tutorial.ipynb").write_text('{"cells": []}', encoding="utf-8")
    result = scan_tutorial_candidates(tmp_path)
    included = [item.path for item in result["candidates"] if item.include_in_tools]
    excluded = [item.path for item in result["candidates"] if not item.include_in_tools]
    assert included == ["docs/tutorial.ipynb"]
    assert "tests/test_example.py" in excluded
    assert "legacy/tutorial.ipynb" in excluded


def test_tutorial_scanner_only_includes_python_when_no_richer_tutorial_exists(tmp_path: Path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "demo.py").write_text("input_path='x.csv'\nprint(input_path)\n", encoding="utf-8")
    result = scan_tutorial_candidates(tmp_path)
    assert [item.path for item in result["candidates"] if item.include_in_tools] == ["examples/demo.py"]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "tutorial.md").write_text("# Tutorial\n\n```python\nprint(1)\n```\n", encoding="utf-8")
    result = scan_tutorial_candidates(tmp_path)
    included = [item.path for item in result["candidates"] if item.include_in_tools]
    assert "docs/tutorial.md" in included
    assert "examples/demo.py" not in included
