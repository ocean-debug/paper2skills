from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_local_path


def collect_repo(repo: str | None = None, ref: str = "main", base_dir: str | Path | None = None) -> dict[str, Any]:
    if not repo:
        return {"url": None, "local_path": None, "ref": ref, "exists": False}
    if repo.startswith(("http://", "https://", "git@")):
        return {"url": repo, "local_path": None, "ref": ref, "exists": False}
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    path = Path(repo).resolve()
    return {"url": None, "local_path": public_local_path(path, base), "ref": ref, "exists": path.exists()}
