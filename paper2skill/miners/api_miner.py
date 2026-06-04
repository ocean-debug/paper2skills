from __future__ import annotations

import re
import tomllib
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
    entrypoints = pyproject_entrypoints(root) + setup_entrypoints(root)
    cli_commands = []
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        mined = mine_python_source(source)
        cli_commands.extend(python_cli_commands(source, path, root))
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
    r_exports = r_namespace_exports(root)
    language = "python" if api_functions or classes else ("r" if r_functions else "unknown")
    return {
        "language": language,
        "package_type": _package_type(root),
        "install_files": public_local_paths([p for p in [root / "pyproject.toml", root / "setup.py", root / "DESCRIPTION"] if p.exists()], root),
        "dependency_files": public_local_paths([p for p in [root / "requirements.txt", root / "renv.lock"] if p.exists()], root),
        "entrypoints": entrypoints,
        "cli_commands": cli_commands,
        "api_functions": api_functions or r_functions,
        "r_exports": r_exports,
        "classes": classes,
        "workflow_engines": workflow_engines(root),
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


def pyproject_entrypoints(root: Path) -> list[dict[str, Any]]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except tomllib.TOMLDecodeError:
        return []
    scripts = data.get("project", {}).get("scripts", {}) or {}
    return [{"name": name, "target": target, "source": "pyproject.toml", "type": "console_script"} for name, target in scripts.items()]


def setup_entrypoints(root: Path) -> list[dict[str, Any]]:
    path = root / "setup.py"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"['\"]([A-Za-z0-9_.-]+)\s*=\s*([A-Za-z0-9_.:]+)['\"]", text)
    return [{"name": name, "target": target, "source": "setup.py", "type": "console_script"} for name, target in matches]


def python_cli_commands(source: str, path: Path, root: Path) -> list[dict[str, Any]]:
    commands = []
    public_path = public_local_path(path, root)
    if "argparse.ArgumentParser" in source or "ArgumentParser(" in source:
        commands.append({"framework": "argparse", "path": public_path, "name": path.stem})
    if "@click.command" in source or "@click.group" in source:
        commands.append({"framework": "click", "path": public_path, "name": path.stem})
    if "typer.Typer" in source or "Typer(" in source:
        commands.append({"framework": "typer", "path": public_path, "name": path.stem})
    if "fire.Fire" in source:
        commands.append({"framework": "fire", "path": public_path, "name": path.stem})
    return commands


def r_namespace_exports(root: Path) -> list[dict[str, Any]]:
    namespace = root / "NAMESPACE"
    if not namespace.exists():
        return []
    text = namespace.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"export\(([^)]+)\)", text)
    exports = []
    for group in names:
        for name in group.split(","):
            clean = name.strip().strip("'\"")
            if clean:
                exports.append({"name": clean, "source": "NAMESPACE"})
    return exports


def workflow_engines(root: Path) -> list[dict[str, Any]]:
    engines = []
    checks = [
        ("snakemake", ["Snakefile", "*.smk"]),
        ("nextflow", ["nextflow.config", "main.nf"]),
        ("wdl", ["*.wdl"]),
        ("cwl", ["*.cwl"]),
    ]
    for engine, patterns in checks:
        paths = []
        for pattern in patterns:
            paths.extend(root.glob(pattern))
            paths.extend(root.rglob(pattern) if "*" in pattern else [])
        public = sorted({public_local_path(path, root) for path in paths if path.is_file()})
        if public:
            engines.append({"engine": engine, "files": public})
    if (root / "workflow").exists():
        engines.append({"engine": "workflow_directory", "files": ["workflow/"]})
    return engines
