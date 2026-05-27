from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_local_path
from paper2skill.miners.script_miner import R_LIBRARY_RE


def parse_requirements(path: Path) -> list[str]:
    packages = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        requirement = parse_requirement_line(line)
        if requirement:
            packages.append(requirement)
    return packages


def parse_requirement_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    line = line.split(" #", 1)[0].strip()
    if not line:
        return None
    return line


def parse_pyproject(path: Path) -> list[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    packages = []
    project = data.get("project", {})
    packages.extend(project.get("dependencies", []) or [])
    poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
    for name, spec in poetry.items():
        if name.lower() == "python":
            continue
        packages.append(name if isinstance(spec, str) else name)
    return packages


def parse_optional_pyproject_dependencies(path: Path) -> dict[str, list[str]]:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    optional = data.get("project", {}).get("optional-dependencies", {}) or {}
    return {name: list(deps or []) for name, deps in optional.items()}


def parse_description(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    packages = []
    capture = False
    for line in text.splitlines():
        if re.match(r"^(Imports|Depends|Suggests):", line):
            capture = True
            line = line.split(":", 1)[1]
        elif capture and line and not line.startswith((" ", "\t")):
            capture = False
        if capture:
            for item in line.split(","):
                name = re.sub(r"\(.+?\)", "", item).strip()
                if name and name not in {"R"}:
                    packages.append(name)
    return packages


def parse_renv_lock(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    return sorted((data.get("Packages") or {}).keys())


def mine_dependencies(repo_path: str | Path | None, tutorial_paths: list[str | Path] | None = None) -> dict[str, Any]:
    python_packages: list[str] = []
    r_packages: list[str] = []
    dependency_files = []
    optional_python: dict[str, list[str]] = {}
    root = Path(repo_path).resolve() if repo_path else None
    if root and root.exists():
        for file_name in ["requirements.txt"]:
            path = root / file_name
            if path.exists():
                dependency_files.append(public_local_path(path, root))
                python_packages.extend(parse_requirements(path))
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            dependency_files.append(public_local_path(pyproject, root))
            python_packages.extend(parse_pyproject(pyproject))
            optional_python.update(parse_optional_pyproject_dependencies(pyproject))
        description = root / "DESCRIPTION"
        if description.exists():
            dependency_files.append(public_local_path(description, root))
            r_packages.extend(parse_description(description))
        renv = root / "renv.lock"
        if renv.exists():
            dependency_files.append(public_local_path(renv, root))
            r_packages.extend(parse_renv_lock(renv))
    for value in tutorial_paths or []:
        path = Path(value)
        if not path.exists() or path.suffix.lower() not in {".r", ".rmd"}:
            continue
        r_packages.extend(R_LIBRARY_RE.findall(path.read_text(encoding="utf-8", errors="replace")))
    return {
        "dependency_files": dependency_files,
        "python": sorted(dict.fromkeys(python_packages)),
        "python_optional": optional_python,
        "r": sorted(dict.fromkeys(r_packages)),
        "executables": [],
    }
