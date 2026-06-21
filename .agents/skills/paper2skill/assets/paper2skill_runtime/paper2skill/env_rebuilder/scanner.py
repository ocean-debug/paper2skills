from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from paper2skill.common import relpath_or_value

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only used on older Python runtimes.
    tomllib = None  # type: ignore[assignment]


ENVIRONMENT_FILES: tuple[str, ...] = (
    "environment.yml",
    "environment.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "requirements-gpu.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "conda-lock.yml",
    "conda-lock.yaml",
    "Dockerfile",
    "DESCRIPTION",
    "NAMESPACE",
    "renv.lock",
    "install.R",
)

LOCKFILE_NAMES = {"conda-lock.yml", "conda-lock.yaml", "uv.lock", "poetry.lock", "renv.lock"}
OFFICIAL_SPEC_NAMES = {"environment.yml", "environment.yaml", "requirements.txt", "DESCRIPTION", "install.R"}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
README_INSTALL_RE = re.compile(r"\b(?:uv\s+pip|python\s+-m\s+pip|pip|conda|mamba)\s+install\s+[^\n`]+")
DOCKER_INSTALL_RE = re.compile(r"(?m)^\s*RUN\s+(?P<command>.*\b(?:uv\s+pip|python\s+-m\s+pip|pip|conda|mamba)\s+install\b[^\n]+)")
PYTHON_REQUIRES_RE = re.compile(r"requires-python\s*=\s*['\"](?P<spec>[^'\"]+)['\"]")
PROJECT_NAME_RE = re.compile(r"(?m)^name\s*=\s*['\"](?P<name>[^'\"]+)['\"]")


def scan_repo(repo: str | Path) -> dict[str, Any]:
    root = Path(repo)
    files = discover_environment_files(root)
    doc_commands = discover_install_commands(root)
    return {
        "schema_version": 1,
        "status": "scanned",
        "repo": str(root),
        "environment_files": [file_record(path, root) for path in files],
        "lockfiles": [file_record(path, root) for path in files if path.name in LOCKFILE_NAMES],
        "official_specs": [file_record(path, root) for path in files if path.name in OFFICIAL_SPEC_NAMES],
        "install_commands": doc_commands,
        "python": infer_python_metadata(root, files, doc_commands),
        "r": infer_r_metadata(root, files),
        "gpu": infer_gpu_metadata(root, files, doc_commands),
        "workflow_engines": infer_workflow_engines(root, files),
        "signals": infer_stack_signals(files, doc_commands),
    }


def discover_environment_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    names = set(ENVIRONMENT_FILES)
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if path.name in names:
            found.append(path)
    return sorted(found, key=lambda item: relpath_or_value(item, root) or str(item))


def should_skip(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"} for part in parts)


def discover_install_commands(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    commands: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path, root):
            continue
        if path.name == "Dockerfile":
            text = safe_read(path)
            for match in DOCKER_INSTALL_RE.finditer(text):
                command = normalize_docker_run(match.group("command"))
                commands.append({"command": command, "source": relpath_or_value(path, root), "kind": classify_install_command(command)})
            continue
        if path.suffix.lower() not in DOC_EXTENSIONS and path.name.lower() not in {"readme", "install"}:
            continue
        text = safe_read(path)
        for match in README_INSTALL_RE.finditer(text):
            command = match.group(0).strip()
            commands.append({"command": command, "source": relpath_or_value(path, root), "kind": classify_install_command(command)})
    return commands


def normalize_docker_run(command: str) -> str:
    value = command.strip()
    for prefix in ["micromamba ", "mamba ", "conda ", "python -m pip ", "pip ", "uv pip "]:
        index = value.find(prefix)
        if index >= 0:
            return value[index:].strip()
    return value


def classify_install_command(command: str) -> str:
    lowered = command.lower()
    if "conda install" in lowered or "mamba install" in lowered:
        return "conda"
    if "uv pip install" in lowered:
        return "uv_pip"
    if "pip install" in lowered:
        return "pip"
    return "unknown"


def file_record(path: Path, root: Path) -> dict[str, Any]:
    record = {
        "path": relpath_or_value(path, root),
        "name": path.name,
        "kind": file_kind(path.name),
        "priority": file_priority(path.name),
    }
    if path.name.startswith("conda-lock"):
        record.update(conda_lock_metadata(path))
    return record


def conda_lock_metadata(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except (OSError, yaml.YAMLError):
        return {"platforms": [], "channels": [], "lock_parse_status": "failed"}
    if not isinstance(data, dict):
        return {"platforms": [], "channels": [], "lock_parse_status": "failed"}
    platforms = set()
    channels = []
    for package in data.get("package") or []:
        if isinstance(package, dict):
            if package.get("platform"):
                platforms.add(str(package["platform"]))
            if package.get("manager") == "conda" and package.get("url"):
                channel = conda_channel_from_url(str(package["url"]))
                if channel:
                    channels.append(channel)
    metadata = data.get("metadata") or {}
    for platform in metadata.get("platforms") or []:
        if isinstance(platform, str):
            platforms.add(platform)
    for channel in metadata.get("channels") or []:
        if isinstance(channel, str):
            channels.append(channel.rsplit("/", 1)[-1])
        elif isinstance(channel, dict) and channel.get("url"):
            channels.append(str(channel["url"]).rsplit("/", 1)[-1])
    return {"platforms": sorted(platforms), "channels": sorted(dict.fromkeys(channels)), "lock_parse_status": "parsed"}


def conda_channel_from_url(value: str) -> str | None:
    lowered = value.lower()
    for channel in ["conda-forge", "bioconda", "defaults", "pytorch"]:
        if f"/{channel}/" in lowered or lowered.rstrip("/").endswith(f"/{channel}"):
            return channel
    return None


def file_kind(name: str) -> str:
    if name in LOCKFILE_NAMES:
        return "lockfile"
    if name in {"environment.yml", "environment.yaml"}:
        return "conda_environment"
    if name.startswith("requirements"):
        return "pip_requirements"
    if name in {"DESCRIPTION", "NAMESPACE", "install.R", "renv.lock"}:
        return "r"
    if name in {"pyproject.toml", "setup.py", "setup.cfg", "Pipfile"}:
        return "python_project"
    if name == "Dockerfile":
        return "container"
    return "environment_hint"


def file_priority(name: str) -> int:
    if name in LOCKFILE_NAMES:
        return 1
    if name in OFFICIAL_SPEC_NAMES:
        return 2
    if name in {"pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "Dockerfile", "NAMESPACE"}:
        return 3
    return 4


def infer_python_metadata(root: Path, files: list[Path], commands: list[dict[str, Any]]) -> dict[str, Any]:
    pyproject = next((path for path in files if path.name == "pyproject.toml"), None)
    setup_cfg = next((path for path in files if path.name == "setup.cfg"), None)
    project_name = None
    python_constraint = None
    if pyproject:
        pyproject_data = parse_pyproject(pyproject)
        project = pyproject_data.get("project") if isinstance(pyproject_data, dict) else {}
        project_name = project.get("name") if isinstance(project, dict) else None
        python_constraint = project.get("requires-python") if isinstance(project, dict) else None
        if not project_name or not python_constraint:
            text = safe_read(pyproject)
            name_match = PROJECT_NAME_RE.search(text)
            constraint_match = PYTHON_REQUIRES_RE.search(text)
            project_name = project_name or (name_match.group("name") if name_match else None)
            python_constraint = python_constraint or (constraint_match.group("spec") if constraint_match else None)
    setup_cfg_data = parse_setup_cfg(setup_cfg) if setup_cfg else {}
    project_name = project_name or setup_cfg_data.get("project_name")
    python_constraint = python_constraint or setup_cfg_data.get("python_constraint")
    pip_commands = [command for command in commands if command.get("kind") in {"pip", "uv_pip"}]
    requirements = parse_requirements_files(root, files)
    return {
        "project_name": project_name,
        "python_constraint": python_constraint,
        "selected_python": select_python_version(python_constraint),
        "has_requirements": any(path.name.startswith("requirements") for path in files),
        "has_pyproject": pyproject is not None,
        "has_setup_cfg": setup_cfg is not None,
        "requirements": requirements,
        "setup_cfg_install_requires": setup_cfg_data.get("install_requires") or [],
        "setup_cfg_extras": setup_cfg_data.get("extras_require") or {},
        "readme_pip_installs": pip_commands,
    }


def parse_pyproject(path: Path) -> dict[str, Any]:
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def parse_setup_cfg(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return {}
    install_requires: list[str] = []
    extras: dict[str, list[str]] = {}
    if parser.has_option("options", "install_requires"):
        install_requires = clean_requirement_block(parser.get("options", "install_requires"))
    if parser.has_section("options.extras_require"):
        for key, value in parser.items("options.extras_require"):
            extras[key] = clean_requirement_block(value)
    return {
        "project_name": parser.get("metadata", "name", fallback=None),
        "python_constraint": parser.get("options", "python_requires", fallback=None),
        "install_requires": install_requires,
        "extras_require": extras,
    }


def clean_requirement_block(value: str) -> list[str]:
    packages = []
    for line in value.splitlines():
        cleaned = line.strip().strip(",")
        if not cleaned or cleaned.startswith("#"):
            continue
        packages.append(cleaned)
    return packages


def parse_requirements_files(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in files:
        if not path.name.startswith("requirements"):
            continue
        packages = []
        for line in safe_read(path).splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#") or cleaned.startswith("-"):
                continue
            packages.append(cleaned)
        records.append({"source": relpath_or_value(path, root), "name": path.name, "packages": packages})
    return records


def select_python_version(constraint: str | None) -> str:
    if not constraint:
        return "3.10"
    cleaned = constraint.strip()
    candidates = ["3.10", "3.11", "3.12", "3.13"]
    try:
        specifier = SpecifierSet(cleaned)
    except InvalidSpecifier:
        specifier = None
    if specifier:
        for candidate in candidates:
            if Version(candidate) in specifier:
                return candidate
        return "3.10"
    versions = [tuple(int(part) for part in match.split(".")[:2]) for match in re.findall(r"\d+\.\d+", cleaned)]
    minimum = (3, 10)
    if "==" in cleaned and versions:
        selected = max(versions[0], minimum)
        return f"{selected[0]}.{selected[1]}"
    if versions and any(token in cleaned for token in [">=", "~=", ">"]):
        selected = max(min(versions), minimum)
        return f"{selected[0]}.{selected[1]}"
    if versions and "<" in cleaned:
        upper = min(versions)
        selected = (3, 10) if upper > minimum else minimum
        return f"{selected[0]}.{selected[1]}"
    return "3.10"


def infer_r_metadata(root: Path, files: list[Path]) -> dict[str, Any]:
    description = next((path for path in files if path.name == "DESCRIPTION"), None)
    namespace = next((path for path in files if path.name == "NAMESPACE"), None)
    install_r = next((path for path in files if path.name == "install.R"), None)
    packages: list[str] = []
    suggests: list[str] = []
    if description:
        description_fields = extract_r_description_packages(safe_read(description))
        packages.extend(description_fields.get("required", []))
        suggests.extend(description_fields.get("suggests", []))
    namespace_packages = extract_r_namespace_packages(safe_read(namespace)) if namespace else []
    install_packages = extract_r_install_packages(safe_read(install_r)) if install_r else {}
    return {
        "has_r": any(path.name in {"DESCRIPTION", "NAMESPACE", "install.R", "renv.lock"} for path in files),
        "has_renv_lock": any(path.name == "renv.lock" for path in files),
        "description_packages": sorted(dict.fromkeys(packages)),
        "description_suggests": sorted(dict.fromkeys(suggests)),
        "namespace_packages": namespace_packages,
        "install_r_packages": install_packages.get("packages", []),
        "install_r_github": install_packages.get("github", []),
    }


def extract_r_description_packages(text: str) -> dict[str, list[str]]:
    required: list[str] = []
    suggests: list[str] = []
    for field in ["Imports", "Depends", "Suggests"]:
        match = re.search(rf"(?ms)^{field}:\s*(.*?)(?=^[A-Za-z][A-Za-z0-9.]*:|\Z)", text)
        if not match:
            continue
        for token in re.split(r",|\n", match.group(1)):
            cleaned = re.sub(r"\([^)]*\)", "", token).strip()
            if cleaned and cleaned != "R":
                if field == "Suggests":
                    suggests.append(cleaned)
                else:
                    required.append(cleaned)
    return {"required": required, "suggests": suggests}


def extract_r_namespace_packages(text: str) -> list[str]:
    packages: list[str] = []
    for match in re.finditer(r"(?m)^\s*import(?:From)?\(([^,\)]+)", text):
        package = match.group(1).strip().strip("'\"")
        if package:
            packages.append(package)
    return sorted(dict.fromkeys(packages))


def extract_r_install_packages(text: str) -> dict[str, list[str]]:
    packages: list[str] = []
    github: list[str] = []
    for match in re.finditer(r"(?:install\.packages|BiocManager::install)\((?P<args>[^)]*)\)", text, flags=re.S):
        packages.extend(extract_r_string_literals(match.group("args")))
    for match in re.finditer(r"(?:remotes|devtools)::install_github\((?P<args>[^)]*)\)", text, flags=re.S):
        github.extend(extract_r_string_literals(match.group("args")))
    return {"packages": sorted(dict.fromkeys(packages)), "github": sorted(dict.fromkeys(github))}


def extract_r_string_literals(text: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"['\"]([^'\"]+)['\"]", text)]


def infer_gpu_metadata(root: Path, files: list[Path], commands: list[dict[str, Any]]) -> dict[str, Any]:
    haystack = "\n".join([safe_read(path)[:20000] for path in files if path.name in {"requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml"}])
    haystack += "\n" + "\n".join(str(command.get("command") or "") for command in commands)
    lowered = haystack.lower()
    torch = any(token in lowered for token in ["torch", "pytorch"])
    cuda = any(token in lowered for token in ["cuda", "cu118", "cu121", "cu124", "cu126", "cu128", "cudatoolkit"])
    return {
        "uses_torch": torch,
        "cuda_signal": cuda,
        "uv_torch_supported": torch,
        "recommended_torch_backend": "auto" if torch and cuda else ("cpu" if torch else None),
    }


def infer_workflow_engines(root: Path, files: list[Path]) -> list[dict[str, str]]:
    engines: list[dict[str, str]] = []
    paths = root.rglob("*") if root.exists() else []
    for path in paths:
        if not path.is_file() or should_skip(path, root):
            continue
        name = path.name
        if name == "Snakefile" or path.suffix == ".smk":
            engines.append({"engine": "snakemake", "source": relpath_or_value(path, root) or str(path)})
        elif name.lower().endswith(".nf") or name == "nextflow.config":
            engines.append({"engine": "nextflow", "source": relpath_or_value(path, root) or str(path)})
        elif path.suffix.lower() in {".cwl", ".wdl"}:
            engines.append({"engine": path.suffix.lower().strip("."), "source": relpath_or_value(path, root) or str(path)})
    return engines


def infer_stack_signals(files: list[Path], commands: list[dict[str, Any]]) -> dict[str, bool]:
    names = {path.name for path in files}
    command_text = "\n".join(str(command.get("command") or "") for command in commands).lower()
    return {
        "has_lockfile": bool(names & LOCKFILE_NAMES),
        "has_official_environment": bool(names & OFFICIAL_SPEC_NAMES),
        "has_python": bool(names & {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "uv.lock", "poetry.lock"}),
        "has_r_or_bioc": bool(names & {"DESCRIPTION", "NAMESPACE", "renv.lock", "install.R"}),
        "has_conda_spec": bool(names & {"environment.yml", "environment.yaml", "conda-lock.yml", "conda-lock.yaml"}) or "conda install" in command_text,
        "has_github_install": "github" in command_text or "git+" in command_text,
    }


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def load_scan(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text) or {}
    import json

    return json.loads(text)
