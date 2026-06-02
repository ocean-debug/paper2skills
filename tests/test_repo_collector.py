from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from paper2skill.collectors.repo_collector import collect_repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True)


def test_collect_repo_indexes_local_directory_without_git(tmp_path: Path):
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "tutorial.md").write_text("# Tutorial\n\n```python\nprint('x')\n```\n", encoding="utf-8")
    result = collect_repo(str(repo), work_dir=tmp_path / "bundle")
    assert result["exists"] is True
    assert result["manifest"]["commit_sha"] is None
    assert (tmp_path / "bundle" / "references" / "repo_manifest.json").exists()
    tutorial_paths = {item["path"] for item in result["index"]["files"] if item["category"] == "tutorial_candidate"}
    assert "docs/tutorial.md" in tutorial_paths


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for commit SHA probing")
def test_collect_repo_records_local_git_commit(tmp_path: Path):
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, text=True, capture_output=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    result = collect_repo(str(repo), work_dir=tmp_path / "bundle")
    assert result["manifest"]["commit_sha"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for clone/pin testing")
def test_collect_repo_can_clone_local_remote_and_pin_sha(tmp_path: Path):
    source = tmp_path / "remote-source"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, text=True, capture_output=True)
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Test User")
    (source / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "initial")
    sha = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
    result = collect_repo(source.as_uri(), work_dir=tmp_path / "bundle", ref=sha)
    assert result["manifest"]["is_remote"] is True
    assert result["manifest"]["commit_sha"] == sha
