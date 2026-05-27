from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from paper2skill.collectors.path_sanitizer import public_local_path, public_local_paths
from paper2skill.miners.python_ast import mine_python_source
from paper2skill.miners.script_miner import mine_r_source


def mine_api(repo_path: str | Path | None) -> dict[str, Any]:
    root = Path(repo_path).resolve() if repo_path else None
    if not root or not root.exists():
        return {"language": "unknown", "api_functions": [], "classes": [], "entrypoints": [], "cli_commands": []}
    api_functions = []
    classes = []
    r_functions = []
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        mined = mine_python_source(path.read_text(encoding="utf-8", errors="replace"))
        for item in mined.get("functions", []):
            item = dict(item)
            item["path"] = public_local_path(path, root)
            api_functions.append(item)
        for item in mined.get("classes", []):
            item = dict(item)
            item["path"] = public_local_path(path, root)
            classes.append(item)
    for path in root.rglob("*.R"):
        mined = mine_r_source(path.read_text(encoding="utf-8", errors="replace"))
        for item in mined.get("function_calls", []):
            item = dict(item)
            item["path"] = public_local_path(path, root)
            r_functions.append(item)
    language = "python" if api_functions or classes else ("r" if r_functions else "unknown")
    return {
        "language": language,
        "package_type": _package_type(root),
        "install_files": public_local_paths([p for p in [root / "pyproject.toml", root / "setup.py", root / "DESCRIPTION"] if p.exists()], root),
        "dependency_files": public_local_paths([p for p in [root / "requirements.txt", root / "renv.lock"] if p.exists()], root),
        "entrypoints": [],
        "cli_commands": [],
        "api_functions": api_functions or r_functions,
        "classes": classes,
        "tutorials": public_local_paths([p for p in root.rglob("*") if p.suffix.lower() in {".ipynb", ".py", ".r", ".rmd"}], root),
        "notebooks": public_local_paths(root.rglob("*.ipynb"), root),
        "examples": _public_matching_paths(root, lambda value: "example" in value.lower() or "demo" in value.lower()),
        "docs": public_local_paths([p for p in root.rglob("*") if p.suffix.lower() in {".md", ".rst"}], root),
    }


def _public_matching_paths(root: Path, predicate: Callable[[str], bool]) -> list[str]:
    matches = []
    for path in root.rglob("*"):
        public_path = public_local_path(path, root)
        if public_path and predicate(public_path):
            matches.append(public_path)
    return matches


def _package_type(root: Path) -> str:
    if (root / "pyproject.toml").exists():
        return "python_pyproject"
    if (root / "setup.py").exists():
        return "python_setup"
    if (root / "DESCRIPTION").exists():
        return "r_package"
    return "unknown"
