from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_help_available():
    result = subprocess.run([sys.executable, "-m", "paper2skill.cli", "--help"], text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert "plan" in result.stdout
    assert "build" in result.stdout


def test_cli_build_toy_python(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    result = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "SKILL.md").exists()
    assert (out / "scripts" / "preflight.py").exists()
