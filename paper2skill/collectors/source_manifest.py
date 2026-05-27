from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.paper_collector import collect_paper
from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH
from paper2skill.collectors.repo_collector import collect_repo
from paper2skill.collectors.tutorial_collector import collect_tutorials


def build_source_manifest(
    paper: str | None = None,
    repo: str | None = None,
    tutorials: list[str] | None = None,
    paper_url: str | None = None,
    paper_title: str | None = None,
    repo_ref: str = "main",
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    return {
        "base_dir": REDACTED_LOCAL_PATH,
        "paper": collect_paper(paper, paper_url, paper_title, base),
        "repo": collect_repo(repo, repo_ref, base),
        "tutorial": collect_tutorials(tutorials, base_dir=base),
        "options": {
            "target": "codex_skill",
            "allow_network": False,
            "install_policy": "ask",
            "maturity_target": "L1",
        },
    }
