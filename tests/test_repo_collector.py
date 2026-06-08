from __future__ import annotations

import shutil
import subprocess
import io
import json
import zipfile
from pathlib import Path

import pytest

from paper2skill.collectors import repo_collector
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


def test_collect_repo_falls_back_to_github_archive_when_git_missing(tmp_path: Path, monkeypatch):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("demo-main/README.md", "# Demo\n")
        archive.writestr("demo-main/docs/tutorial.md", "# Tutorial\n")
    zip_bytes = zip_buffer.getvalue()

    class FakeResponse:
        def __init__(self, payload: bytes):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

    def fake_urlopen(url: str, timeout: int):
        if url.endswith("/repos/acme/demo"):
            return FakeResponse(json.dumps({"default_branch": "main"}).encode())
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse(json.dumps({"object": {"sha": "abc1234"}}).encode())
        if url == "https://codeload.github.com/acme/demo/zip/main":
            return FakeResponse(zip_bytes)
        raise AssertionError(url)

    monkeypatch.setattr(repo_collector.shutil, "which", lambda _name: None)
    monkeypatch.setattr(repo_collector, "urlopen", fake_urlopen)

    result = collect_repo("https://github.com/acme/demo", ref=None, work_dir=tmp_path / "bundle")

    assert result["exists"] is True
    assert result["manifest"]["commit_sha"] == "abc1234"
    assert result["manifest"]["clone_status"] == "cloned"
    paths = {item["path"] for item in result["index"]["files"]}
    assert paths == {"README.md", "docs/tutorial.md"}
