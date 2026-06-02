from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

from paper2skill.collectors.path_sanitizer import public_local_path
from paper2skill.common import write_json


TUTORIAL_SUFFIXES = {".ipynb", ".md", ".rst", ".rmd", ".r", ".py"}
DEPENDENCY_FILES = {"environment.yml", "environment.yaml", "DESCRIPTION", "renv.lock", "requirements.txt", "pyproject.toml"}


def collect_repo(
    repo: str | None = None,
    ref: str | None = "main",
    base_dir: str | Path | None = None,
    work_dir: str | Path | None = None,
    skip_clone: bool = False,
) -> dict[str, Any]:
    if not repo:
        return {"url": None, "local_path": None, "ref": ref, "exists": False, "manifest": None, "index": {"files": []}}
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    is_remote = is_remote_repo(repo)
    if is_remote and not skip_clone and work_dir:
        path = clone_repo(repo, Path(work_dir), ref)
    else:
        path = local_repo_path(repo)
    exists = path.exists()
    manifest = build_repo_manifest(repo, path, ref, is_remote)
    index = index_repo(path) if exists else {"files": []}
    if work_dir:
        references = Path(work_dir) / "references"
        write_json(references / "repo_manifest.json", manifest)
        write_json(references / "repo_index.json", index)
    return {
        "url": repo if is_remote else None,
        "local_path": public_local_path(path, base),
        "ref": ref,
        "exists": exists,
        "manifest": manifest,
        "index": index,
    }


def is_remote_repo(repo: str) -> bool:
    return repo.startswith(("http://", "https://", "git@", "file://"))


def local_repo_path(repo: str) -> Path:
    if repo.startswith("file://"):
        parsed = urlparse(repo)
        return Path(unquote(parsed.path)).resolve()
    return Path(repo).resolve()


def clone_repo(repo: str, work_dir: Path, ref: str | None = None) -> Path:
    if shutil.which("git") is None:
        raise RuntimeError("git is required to clone remote repositories")
    repo_root = work_dir / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    repo_name = repo_name_from_url(repo)
    dest = repo_root / repo_name
    if dest.exists():
        shutil.rmtree(dest)
    command = ["git", "clone", "--depth", "1"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([repo, str(dest)])
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0 and ref:
        subprocess.run(["git", "clone", repo, str(dest)], text=True, capture_output=True, check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", ref], text=True, capture_output=True, check=True)
    elif result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return dest


def repo_name_from_url(repo: str) -> str:
    value = repo.rstrip("/").rsplit("/", 1)[-1]
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("file:"):
        value = Path(unquote(urlparse(repo).path)).name
    return value or "repo"


def build_repo_manifest(repo: str, path: Path, ref: str | None, is_remote: bool) -> dict[str, Any]:
    return {
        "repo_url": repo if is_remote else None,
        "repo_name": path.name,
        "local_path": str(path),
        "commit_sha": git_rev_parse(path),
        "ref": ref,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "is_remote": is_remote,
    }


def git_rev_parse(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def index_repo(path: Path) -> dict[str, Any]:
    files = []
    if not path.exists():
        return {"files": files}
    for item in sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts):
        rel = item.relative_to(path).as_posix()
        files.append({"path": rel, "suffix": item.suffix.lower(), "size_bytes": item.stat().st_size, "category": categorize_file(rel, item.name)})
    return {"files": files}


def categorize_file(rel_path: str, name: str) -> str:
    lower = rel_path.lower()
    if name in DEPENDENCY_FILES:
        return "dependency"
    if Path(rel_path).suffix.lower() in TUTORIAL_SUFFIXES and any(part in lower for part in ["docs/", "vignettes/", "tutorial", "examples/", "notebooks/", "readme"]):
        return "tutorial_candidate"
    return "source"
