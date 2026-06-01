from __future__ import annotations

import json
import re
import tomllib
import sys
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from paper2skill.collectors.path_sanitizer import public_local_path
from paper2skill.miners.script_miner import R_LIBRARY_RE

R_BASE_PACKAGES = {"base", "compiler", "datasets", "graphics", "grDevices", "grid", "methods", "parallel", "splines", "stats", "tools", "utils"}


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
    if _is_local_path_requirement(line):
        return None
    return line


def _is_local_path_requirement(value: str) -> bool:
    return value.startswith(("./", "../", "/", ".\\")) or re.match(r"^[A-Za-z]:[\\/]", value) is not None


def _python_record(spec: str, source: str, evidence: str, required: bool = True, category: str = "runtime") -> dict[str, Any] | None:
    try:
        requirement = Requirement(spec)
    except InvalidRequirement:
        return None
    if requirement.name in sys.stdlib_module_names:
        return None
    return {
        "spec": spec,
        "name": requirement.name,
        "import_name": requirement.name.replace("-", "_"),
        "required": required,
        "category": category,
        "source": source,
        "evidence": evidence,
    }


def parse_requirements_records(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records = []
    ignored = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        clean = line.split(" #", 1)[0].strip()
        if not clean:
            continue
        if clean.startswith(("-r", "--requirement", "-c", "--constraint", "-e", "--editable")) or _is_local_path_requirement(clean):
            ignored.append({"value": clean, "source": "requirements.txt", "reason": "not_runtime_requirement"})
            continue
        record = _python_record(clean, "requirements.txt", path.name)
        if record:
            records.append(record)
        else:
            ignored.append({"value": clean, "source": "requirements.txt", "reason": "invalid_or_unsupported_requirement"})
    return records, ignored


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


def parse_pyproject_records(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[dict[str, str]]]:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    records = []
    ignored = []
    optional: dict[str, list[str]] = {}
    for spec in data.get("project", {}).get("dependencies", []) or []:
        record = _python_record(spec, "pyproject.toml", "project.dependencies")
        if record:
            records.append(record)
        else:
            ignored.append({"value": str(spec), "source": "pyproject.toml", "reason": "invalid_or_unsupported_requirement"})
    for group, deps in (data.get("project", {}).get("optional-dependencies", {}) or {}).items():
        optional[f"project:{group}"] = [Requirement(dep).name if _is_valid_requirement(dep) else str(dep) for dep in deps or []]
    poetry = data.get("tool", {}).get("poetry", {}) or {}
    for name, spec in (poetry.get("dependencies", {}) or {}).items():
        if name.lower() == "python":
            continue
        records.append({"spec": name, "name": name, "import_name": name.replace("-", "_"), "required": True, "category": "runtime", "source": "pyproject.toml", "evidence": "tool.poetry.dependencies"})
    for group_name, group in (poetry.get("group", {}) or {}).items():
        deps = (group or {}).get("dependencies", {}) or {}
        optional[f"poetry:{group_name}"] = [name for name in deps if name.lower() != "python"]
    return records, optional, ignored


def _is_valid_requirement(value: str) -> bool:
    try:
        Requirement(value)
        return True
    except InvalidRequirement:
        return False


def parse_description(path: Path) -> list[str]:
    required, _optional = parse_description_fields(path)
    return required


def parse_description_fields(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fields: dict[str, list[str]] = {"Imports": [], "Depends": [], "Suggests": [], "Enhances": []}
    capture: str | None = None
    for line in text.splitlines():
        match = re.match(r"^(Imports|Depends|Suggests|Enhances):", line)
        if match:
            capture = match.group(1)
            line = line.split(":", 1)[1]
        elif capture and line and not line.startswith((" ", "\t")):
            capture = None
        if capture:
            for item in line.split(","):
                name = re.sub(r"\(.+?\)", "", item).strip()
                if name and name not in {"R"} and name not in R_BASE_PACKAGES:
                    fields[capture].append(name)
    required = sorted(dict.fromkeys(fields["Imports"] + fields["Depends"]))
    optional = {
        "DESCRIPTION:Suggests": sorted(dict.fromkeys(fields["Suggests"])),
        "DESCRIPTION:Enhances": sorted(dict.fromkeys(fields["Enhances"])),
    }
    return required, {key: value for key, value in optional.items() if value}


def parse_renv_lock(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    return sorted((data.get("Packages") or {}).keys())


def mine_dependencies(repo_path: str | Path | None, tutorial_paths: list[str | Path] | None = None) -> dict[str, Any]:
    python_packages: list[str] = []
    python_records: list[dict[str, Any]] = []
    r_packages: list[str] = []
    r_records: list[dict[str, Any]] = []
    dependency_files = []
    optional: dict[str, dict[str, list[str]]] = {"python": {}, "r": {}}
    ignored: list[dict[str, str]] = []
    root = Path(repo_path).resolve() if repo_path else None
    if root and root.exists():
        for file_name in ["requirements.txt"]:
            path = root / file_name
            if path.exists():
                dependency_files.append(public_local_path(path, root))
                records, skipped = parse_requirements_records(path)
                python_records.extend(records)
                python_packages.extend(item["spec"] for item in records)
                ignored.extend(skipped)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            dependency_files.append(public_local_path(pyproject, root))
            records, optional_python, skipped = parse_pyproject_records(pyproject)
            python_records.extend(records)
            python_packages.extend(item["spec"] for item in records)
            optional["python"].update(optional_python)
            ignored.extend(skipped)
        description = root / "DESCRIPTION"
        if description.exists():
            dependency_files.append(public_local_path(description, root))
            required_r, optional_r = parse_description_fields(description)
            r_packages.extend(required_r)
            r_records.extend({"name": name, "source": "DESCRIPTION", "evidence": "Imports/Depends", "required": True, "category": "runtime"} for name in required_r)
            optional["r"].update(optional_r)
        renv = root / "renv.lock"
        if renv.exists():
            dependency_files.append(public_local_path(renv, root))
            optional["r"]["renv.lock"] = [name for name in parse_renv_lock(renv) if name not in R_BASE_PACKAGES]
    for value in tutorial_paths or []:
        path = Path(value)
        if not path.exists() or path.suffix.lower() not in {".r", ".rmd"}:
            continue
        for name in R_LIBRARY_RE.findall(path.read_text(encoding="utf-8", errors="replace")):
            if name in R_BASE_PACKAGES:
                continue
            r_packages.append(name)
            r_records.append({"name": name, "source": "tutorial", "evidence": public_local_path(path, root or Path.cwd()), "required": True, "category": "tutorial_runtime"})
    python_records = _dedupe_records(python_records, "spec")
    r_records = _dedupe_records(r_records, "name")
    return {
        "dependency_files": dependency_files,
        "python": sorted(dict.fromkeys(python_packages)),
        "python_records": sorted(python_records, key=lambda item: item["spec"]),
        "python_optional": {key.removeprefix("project:"): value for key, value in optional["python"].items() if key.startswith("project:")},
        "r": sorted(dict.fromkeys(r_packages)),
        "r_records": sorted(r_records, key=lambda item: item["name"]),
        "optional": optional,
        "ignored": ignored,
        "executables": [],
    }


def _dedupe_records(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        deduped.setdefault(str(record[key]), record)
    return list(deduped.values())
