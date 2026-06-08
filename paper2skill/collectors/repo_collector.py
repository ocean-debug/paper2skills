from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import zipfile
from urllib.parse import urlparse, unquote
from urllib.request import urlopen
import json

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
        return {
            "url": None,
            "local_path": None,
            "resolved_path": None,
            "ref": ref,
            "exists": False,
            "manifest": None,
            "index": {"files": []},
        }
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    is_remote = is_remote_repo(repo)
    clone_status = "local"
    if is_remote and skip_clone:
        path: Path | None = None
        clone_status = "skipped"
    elif is_remote and work_dir:
        path = clone_repo(repo, Path(work_dir), ref)
        clone_status = "cloned"
    else:
        path = local_repo_path(repo)
        clone_status = "remote_unresolved" if is_remote else "local"
    exists = bool(path and path.exists())
    manifest = build_repo_manifest(repo, path, ref, is_remote, clone_status)
    index = index_repo(path) if exists else {"files": []}
    if work_dir:
        references = Path(work_dir) / "references"
        write_json(references / "repo_manifest.json", manifest)
        write_json(references / "repo_index.json", index)
    return {
        "url": repo if is_remote else None,
        "local_path": public_local_path(path, base) if path else None,
        "resolved_path": str(path) if path else None,
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
    repo_root = work_dir / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    repo_name = repo_name_from_url(repo)
    dest = repo_root / repo_name
    if dest.exists():
        shutil.rmtree(dest)
    if shutil.which("git") is None:
        if github_parts(repo):
            return download_github_archive(repo, dest, ref)
        raise RuntimeError("git is required to clone remote repositories")
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


def github_parts(repo: str) -> tuple[str, str] | None:
    parsed = urlparse(repo)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    owner, name = parts[0], parts[1]
    if name.endswith(".git"):
        name = name[:-4]
    return owner, name


def download_github_archive(repo: str, dest: Path, ref: str | None = None) -> Path:
    parts = github_parts(repo)
    if not parts:
        raise RuntimeError("git is required to clone non-GitHub remote repositories")
    owner, name = parts
    branch = ref or github_default_branch(owner, name)
    archive_url = f"https://codeload.github.com/{owner}/{name}/zip/{branch}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_zip = dest.parent / f"{dest.name}.zip"
    with urlopen(archive_url, timeout=120) as response:
        tmp_zip.write_bytes(response.read())
    with zipfile.ZipFile(tmp_zip) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        roots = {member.filename.split("/", 1)[0] for member in members if "/" in member.filename}
        if len(roots) != 1:
            raise RuntimeError("GitHub archive has unexpected layout")
        root_prefix = next(iter(roots)) + "/"
        dest.mkdir(parents=True, exist_ok=True)
        for member in members:
            if not member.filename.startswith(root_prefix):
                continue
            rel = member.filename[len(root_prefix) :]
            if not rel or unsafe_archive_path(rel):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source:
                target.write_bytes(source.read())
    tmp_zip.unlink(missing_ok=True)
    sha = github_ref_sha(owner, name, branch)
    if sha:
        (dest / ".paper2skill_commit_sha").write_text(sha + "\n", encoding="utf-8")
    return dest


def unsafe_archive_path(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() or ".." in path.parts


def github_default_branch(owner: str, name: str) -> str:
    with urlopen(f"https://api.github.com/repos/{owner}/{name}", timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    branch = data.get("default_branch")
    if not branch:
        raise RuntimeError("GitHub repository metadata did not include default_branch")
    return str(branch)


def github_ref_sha(owner: str, name: str, branch: str) -> str | None:
    try:
        with urlopen(f"https://api.github.com/repos/{owner}/{name}/git/ref/heads/{branch}", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    obj = data.get("object") or {}
    return obj.get("sha")


def build_repo_manifest(repo: str, path: Path | None, ref: str | None, is_remote: bool, clone_status: str = "local") -> dict[str, Any]:
    return {
        "repo_url": repo if is_remote else None,
        "repo_name": path.name if path else repo_name_from_url(repo),
        "local_path": str(path) if path else None,
        "commit_sha": git_rev_parse(path) if path else None,
        "ref": ref,
        "requested_ref": ref,
        "clone_status": clone_status,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "is_remote": is_remote,
    }


def git_rev_parse(path: Path) -> str | None:
    if not path.exists():
        return None
    archive_sha = path / ".paper2skill_commit_sha"
    if archive_sha.exists():
        return archive_sha.read_text(encoding="utf-8").strip() or None
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
    for item in sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts and p.name != ".paper2skill_commit_sha"):
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
