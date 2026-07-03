"""Static environment and dependency mining from indexed sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


DEPENDENCY_FILE_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "conda.yaml",
}

GPU_TERMS = {"cuda", "cudnn", "gpu", "torch", "tensorflow", "jax", "cupy"}


def dependency_name(value: str) -> str:
    text = value.strip().strip('"').strip("'")
    text = re.split(r"[<>=!~;\[\]\s]", text, maxsplit=1)[0]
    return text.strip()


def parse_requirements(text: str) -> list[str]:
    deps = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        name = dependency_name(stripped)
        if name:
            deps.append(name)
    return sorted(set(deps))


def parse_pyproject(text: str) -> dict[str, Any]:
    python_requires = None
    match = re.search(r"requires-python\s*=\s*['\"]([^'\"]+)['\"]", text)
    if match:
        python_requires = match.group(1)
    deps = []
    for block_match in re.finditer(r"dependencies\s*=\s*\[(.*?)\]", text, flags=re.S):
        deps.extend(re.findall(r"['\"]([^'\"]+)['\"]", block_match.group(1)))
    return {
        "python_requires": python_requires,
        "dependencies": sorted({dependency_name(dep) for dep in deps if dependency_name(dep)}),
    }


def parse_environment_yaml(text: str) -> list[str]:
    deps = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies:"):
            in_deps = True
            continue
        if not in_deps or not stripped.startswith("- "):
            continue
        value = stripped[2:].strip()
        if value.startswith("pip:"):
            continue
        name = dependency_name(value)
        if name:
            deps.append(name)
    return sorted(set(deps))


def parse_dependency_file(path: Path) -> dict[str, Any]:
    text = read_text(path)
    name = path.name.lower()
    if name.startswith("requirements"):
        return {"dependencies": parse_requirements(text), "python_requires": None}
    if name == "pyproject.toml":
        return parse_pyproject(text)
    if name in {"environment.yml", "environment.yaml", "conda.yml", "conda.yaml"}:
        return {"dependencies": parse_environment_yaml(text), "python_requires": None}
    if name in {"setup.py", "setup.cfg"}:
        deps = []
        for block in re.findall(r"install_requires\s*=\s*\[(.*?)\]", text, flags=re.S):
            deps.extend(re.findall(r"['\"]([^'\"]+)['\"]", block))
        return {"dependencies": sorted({dependency_name(dep) for dep in deps if dependency_name(dep)}), "python_requires": None}
    return {"dependencies": [], "python_requires": None}


def imported_modules(source_index: dict[str, Any]) -> list[str]:
    modules = []
    for record in source_index.get("files", []):
        for module in record.get("imports", []):
            root = str(module).split(".")[0]
            if root and not root.startswith("_"):
                modules.append(root)
    return sorted(set(modules))


def dependency_records(source_index: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for record in source_index.get("files", []):
        path = Path(str(record.get("path") or ""))
        if not path.exists() or not path.is_file():
            continue
        if path.name.lower() not in DEPENDENCY_FILE_NAMES:
            continue
        parsed = parse_dependency_file(path)
        records.append(
            {
                "source_path": record.get("relative_path"),
                "source_evidence_id": record.get("evidence_id"),
                "file_name": path.name,
                "dependencies": parsed["dependencies"],
                "python_requires": parsed.get("python_requires"),
            }
        )
    return records


def build_environment_spec(
    request: dict[str, Any],
    source_index: dict[str, Any],
    backend_contract: dict[str, Any],
) -> dict[str, Any]:
    dep_records = dependency_records(source_index)
    declared_deps = sorted({dep for record in dep_records for dep in record.get("dependencies", [])})
    imports = imported_modules(source_index)
    all_terms = {value.lower() for value in declared_deps + imports}
    gpu_hints = sorted(term for term in GPU_TERMS if any(term in value for value in all_terms))
    python_requires = sorted({record["python_requires"] for record in dep_records if record.get("python_requires")})
    findings = []
    if not dep_records:
        findings.append(
            {
                "severity": "warning",
                "code": "no_dependency_file_found",
                "message": "No dependency manifest was found in indexed sources.",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "backend_status": backend_contract.get("status"),
        "dependency_sources": dep_records,
        "declared_dependencies": declared_deps,
        "imported_modules": imports,
        "python_requires": python_requires,
        "gpu_hints": gpu_hints,
        "install_policy": "Do not install dependencies silently; ask before creating or modifying environments.",
        "findings": findings,
    }
