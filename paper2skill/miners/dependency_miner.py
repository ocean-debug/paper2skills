from __future__ import annotations

import json
import re
import tomllib
import sys
import configparser
import ast
from pathlib import Path
from typing import Any

import yaml
from packaging.requirements import InvalidRequirement, Requirement

from paper2skill.collectors.path_sanitizer import public_local_path
from paper2skill.miners.script_miner import R_LIBRARY_RE

R_BASE_PACKAGES = {"base", "compiler", "datasets", "graphics", "grDevices", "grid", "methods", "parallel", "splines", "stats", "tools", "utils"}
BIOCONDUCTOR_HINTS = {
    "apeglm",
    "DESeq2",
    "edgeR",
    "limma",
    "clusterProfiler",
    "SingleCellExperiment",
    "SummarizedExperiment",
    "AnnotationDbi",
    "BiocGenerics",
    "BiocStyle",
    "scran",
    "scater",
    "ComplexHeatmap",
}
PYTHON_IMPORT_PACKAGE_ALIASES = {
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "PIL": "Pillow",
    "cv2": "opencv-python",
}
PYTHON_DOCUMENTATION_HINTS = {
    "pytorch": "torch",
    "torch": "torch",
    "faiss-gpu": "faiss-gpu",
    "faiss-cpu": "faiss-cpu",
    "faiss": "faiss-cpu",
    "anndata": "anndata",
}


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


def parse_pyproject_project_name(path: Path) -> str | None:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    name = (data.get("project") or {}).get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    poetry_name = (((data.get("tool") or {}).get("poetry") or {}).get("name"))
    return poetry_name.strip() if isinstance(poetry_name, str) and poetry_name.strip() else None


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
    records, optional_records = parse_description_field_records(path)
    required = sorted(dict.fromkeys(record["name"] for record in records))
    optional = {
        key: sorted(dict.fromkeys(record["name"] for record in value))
        for key, value in optional_records.items()
        if value
    }
    return required, optional


def parse_description_field_records(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fields: dict[str, list[dict[str, Any]]] = {"Imports": [], "Depends": [], "LinkingTo": [], "Suggests": [], "Enhances": []}
    capture: str | None = None
    for line in text.splitlines():
        match = re.match(r"^(Imports|Depends|LinkingTo|Suggests|Enhances):", line)
        if match:
            capture = match.group(1)
            line = line.split(":", 1)[1]
        elif capture and line and not line.startswith((" ", "\t")):
            capture = None
        if capture:
            for item in line.split(","):
                record = _parse_r_package_item(item, capture)
                if record:
                    fields[capture].append(record)
    required = _dedupe_records(fields["Imports"] + fields["Depends"] + fields["LinkingTo"], "name")
    optional = {
        "DESCRIPTION:Suggests": _dedupe_records(fields["Suggests"], "name"),
        "DESCRIPTION:Enhances": _dedupe_records(fields["Enhances"], "name"),
    }
    return required, {key: value for key, value in optional.items() if value}


def _parse_r_package_item(item: str, field: str) -> dict[str, Any] | None:
    item = item.strip()
    if not item:
        return None
    match = re.match(r"^([A-Za-z][A-Za-z0-9_.]*)(?:\s*\(([^)]+)\))?$", item)
    if not match:
        return None
    name, version = match.groups()
    if name in {"R"} or name in R_BASE_PACKAGES:
        return None
    record = {"name": name, "field": field}
    if version:
        record["version_spec"] = version.strip()
    return record


def parse_description_metadata(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fields: dict[str, list[str]] = {"SystemRequirements": [], "Remotes": [], "biocViews": []}
    capture: str | None = None
    for line in text.splitlines():
        match = re.match(r"^(SystemRequirements|Remotes|biocViews):", line)
        if match:
            capture = match.group(1)
            line = line.split(":", 1)[1]
        elif capture and line and not line.startswith((" ", "\t")):
            capture = None
        if capture:
            fields[capture].extend([item.strip() for item in line.split(",") if item.strip()])
    return {key: value for key, value in fields.items() if value}


def parse_environment_yml(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except yaml.YAMLError:
        return [], []
    python_records = []
    conda_records = []
    for dep in data.get("dependencies", []) or []:
        if isinstance(dep, str):
            name = dep.split("=", 1)[0].strip()
            if name and name not in {"python", "pip", "r-base"}:
                conda_records.append({"package": dep, "name": name, "source": path.name, "required": True, "category": "runtime"})
        elif isinstance(dep, dict):
            for key, values in dep.items():
                if key == "pip":
                    for spec in values or []:
                        record = _python_record(str(spec), path.name, "dependencies.pip")
                        if record:
                            python_records.append(record)
                else:
                    conda_records.append({"package": key, "source": path.name, "required": True, "category": "runtime"})
    return python_records, conda_records


def parse_setup_cfg(path: Path) -> list[dict[str, Any]]:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    specs = []
    if parser.has_option("options", "install_requires"):
        specs = [line.strip() for line in parser.get("options", "install_requires").splitlines() if line.strip()]
    return [record for spec in specs if (record := _python_record(spec, "setup.cfg", "options.install_requires"))]


def parse_setup_cfg_project_name(path: Path) -> str | None:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    if parser.has_option("metadata", "name"):
        name = parser.get("metadata", "name").strip()
        return name or None
    return None


def parse_setup_py(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"install_requires\s*=\s*\[([^\]]*)\]", text, re.S)
    if not match:
        return []
    specs = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    return [record for spec in specs if (record := _python_record(spec, "setup.py", "install_requires"))]


def parse_setup_py_project_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1).strip() if match else None


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
    conda_records: list[dict[str, Any]] = []
    system_requirements: list[dict[str, Any]] = []
    external_resources: list[dict[str, Any]] = []
    optional: dict[str, dict[str, list[str]]] = {"python": {}, "r": {}}
    ignored: list[dict[str, str]] = []
    root = Path(repo_path).resolve() if repo_path else None
    if root and root.exists():
        requirement_paths = [root / "requirements.txt"]
        requirements_dir = root / "requirements"
        if requirements_dir.exists():
            requirement_paths.extend(sorted(requirements_dir.glob("*.txt")))
        for path in requirement_paths:
            if path.exists() and path.is_file():
                dependency_files.append(public_local_path(path, root))
                records, skipped = parse_requirements_records(path)
                python_records.extend(records)
                python_packages.extend(item["spec"] for item in records)
                ignored.extend(skipped)
        for file_name in ["environment.yml", "environment.yaml", "conda.yml"]:
            path = root / file_name
            if path.exists():
                dependency_files.append(public_local_path(path, root))
                records, conda = parse_environment_yml(path)
                python_records.extend(records)
                python_packages.extend(item["spec"] for item in records)
                conda_records.extend(conda)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            dependency_files.append(public_local_path(pyproject, root))
            if project_name := parse_pyproject_project_name(pyproject):
                record = _python_record(project_name, "pyproject.toml", "project.name", required=False, category="self_package")
                if record:
                    python_records.append(record)
                    python_packages.append(record["spec"])
            records, optional_python, skipped = parse_pyproject_records(pyproject)
            python_records.extend(records)
            python_packages.extend(item["spec"] for item in records)
            optional["python"].update(optional_python)
            ignored.extend(skipped)
        setup_cfg = root / "setup.cfg"
        if setup_cfg.exists():
            dependency_files.append(public_local_path(setup_cfg, root))
            if project_name := parse_setup_cfg_project_name(setup_cfg):
                record = _python_record(project_name, "setup.cfg", "metadata.name", required=False, category="self_package")
                if record:
                    python_records.append(record)
                    python_packages.append(record["spec"])
            records = parse_setup_cfg(setup_cfg)
            python_records.extend(records)
            python_packages.extend(item["spec"] for item in records)
        setup_py = root / "setup.py"
        if setup_py.exists():
            dependency_files.append(public_local_path(setup_py, root))
            if project_name := parse_setup_py_project_name(setup_py):
                record = _python_record(project_name, "setup.py", "name", required=False, category="self_package")
                if record:
                    python_records.append(record)
                    python_packages.append(record["spec"])
            records = parse_setup_py(setup_py)
            python_records.extend(records)
            python_packages.extend(item["spec"] for item in records)
        description = root / "DESCRIPTION"
        if description.exists():
            dependency_files.append(public_local_path(description, root))
            required_r_records, optional_r_records = parse_description_field_records(description)
            required_r = [record["name"] for record in required_r_records]
            r_packages.extend(required_r)
            for record in required_r_records:
                item = {
                    "name": record["name"],
                    "source": "Bioconductor_or_unknown" if record["name"] in BIOCONDUCTOR_HINTS else "DESCRIPTION",
                    "evidence": f"DESCRIPTION:{record['field']}",
                    "required": True,
                    "category": "runtime",
                }
                if "version_spec" in record:
                    item["version_spec"] = record["version_spec"]
                r_records.append(item)
            optional["r"].update({key: sorted(record["name"] for record in value) for key, value in optional_r_records.items()})
            metadata = parse_description_metadata(description)
            system_requirements.extend({"value": item, "source": "DESCRIPTION", "required": True, "install": "plan_only"} for item in metadata.get("SystemRequirements", []))
            external_resources.extend({"name": item, "type": "r_remote", "source": "DESCRIPTION:Remotes", "required": False, "downloadable": False} for item in metadata.get("Remotes", []))
            bioconductor = {"biocViews": metadata.get("biocViews", []), "hinted_packages": sorted(name for name in required_r if name in BIOCONDUCTOR_HINTS)}
        namespace = root / "NAMESPACE"
        if namespace.exists():
            dependency_files.append(public_local_path(namespace, root))
            namespace_records = parse_namespace_dependency_records(namespace)
            r_packages.extend(record["name"] for record in namespace_records)
            r_records.extend(namespace_records)
        renv = root / "renv.lock"
        if renv.exists():
            dependency_files.append(public_local_path(renv, root))
            optional["r"]["renv.lock"] = [name for name in parse_renv_lock(renv) if name not in R_BASE_PACKAGES]
        import_records = python_import_dependency_records(root)
        python_records.extend(import_records)
        python_packages.extend(item["spec"] for item in import_records)
        markdown_r_records = markdown_r_dependency_records(root)
        r_packages.extend(record["name"] for record in markdown_r_records)
        r_records.extend(markdown_r_records)
        install_records = install_command_dependency_records(root)
        python_records.extend(install_records["python_records"])
        python_packages.extend(item["spec"] for item in install_records["python_records"])
        r_packages.extend(record["name"] for record in install_records["r_records"])
        r_records.extend(install_records["r_records"])
        doc_records = python_documentation_hint_records(root)
        python_records.extend(doc_records)
        python_packages.extend(item["spec"] for item in doc_records)
        r_script_records = r_script_dependency_records(root)
        r_packages.extend(record["name"] for record in r_script_records)
        r_records.extend(r_script_records)
        executables = rscript_executables(root)
    else:
        executables = []
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
        "conda_records": sorted(conda_records, key=lambda item: item.get("package", item.get("name", ""))),
        "system_requirements": system_requirements,
        "external_resources": external_resources,
        "bioconductor": bioconductor if "bioconductor" in locals() else {"biocViews": [], "hinted_packages": []},
        "executables": executables,
    }


def python_import_dependency_records(root: Path) -> list[dict[str, Any]]:
    records = []
    local_modules = local_python_modules(root)
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names.extend(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.append(node.module.split(".", 1)[0])
            for name in names:
                record = import_dependency_record(name, public_local_path(path, root), local_modules)
                if record:
                    records.append(record)
    return _dedupe_records(records, "name")


def local_python_modules(root: Path) -> set[str]:
    modules = set()
    for path in root.iterdir():
        if path.is_dir() and (path / "__init__.py").exists():
            modules.add(path.name)
    src = root / "src"
    if src.exists():
        for path in src.iterdir():
            if path.is_dir() and (path / "__init__.py").exists():
                modules.add(path.name)
    for path in root.glob("*.py"):
        modules.add(path.stem)
    return modules


def import_dependency_record(name: str, evidence: str | None, local_modules: set[str]) -> dict[str, Any] | None:
    if not name or name in local_modules or name in sys.stdlib_module_names:
        return None
    package = PYTHON_IMPORT_PACKAGE_ALIASES.get(name, name)
    record = _python_record(package, "import_fallback", evidence or "python_import", required=True, category="runtime")
    if record:
        record["import_name"] = name
    return record


def markdown_r_dependency_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".md", ".rmd", ".rst"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        packages = set(R_LIBRARY_RE.findall(text))
        packages.update(re.findall(r"\b([A-Za-z][A-Za-z0-9_.]*):::{0,1}[A-Za-z][A-Za-z0-9_.]*\s*\(", text))
        for name in packages:
            if name in R_BASE_PACKAGES:
                continue
            records.append(
                {
                    "name": name,
                    "source": "README_or_Rmd",
                    "evidence": public_local_path(path, root),
                    "required": True,
                    "category": "tutorial_runtime",
                }
            )
    return _dedupe_records(records, "name")


def r_script_dependency_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for path in root.rglob("*.R"):
        text = path.read_text(encoding="utf-8", errors="replace")
        packages = set(R_LIBRARY_RE.findall(text))
        packages.update(r_package_qualified_calls(text))
        if re.search(r"\bapeglm\b", text, flags=re.I):
            packages.add("apeglm")
        for name in packages:
            if name in R_BASE_PACKAGES:
                continue
            records.append(
                {
                    "name": name,
                    "source": "Bioconductor_or_unknown" if name in BIOCONDUCTOR_HINTS else "R_script",
                    "evidence": public_local_path(path, root),
                    "required": True,
                    "category": "runtime",
                }
            )
    return _dedupe_records(records, "name")


def r_package_qualified_calls(text: str) -> set[str]:
    return set(re.findall(r"\b([A-Za-z][A-Za-z0-9_.]*):::{0,1}[A-Za-z][A-Za-z0-9_.]*\s*\(", text))


def install_command_dependency_records(root: Path) -> dict[str, list[dict[str, Any]]]:
    python_records: list[dict[str, Any]] = []
    r_records: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".rst", ".rmd", ".py", ".r", ".sh", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        public = public_local_path(path, root)
        for spec in pip_install_specs(text):
            record = _python_record(spec, "install_command", public or path.name, required=False, category="install_hint")
            if record:
                python_records.append(record)
        for name in r_install_packages(text):
            if name in R_BASE_PACKAGES:
                continue
            r_records.append(
                {
                    "name": name,
                    "source": "Bioconductor_or_unknown" if name in BIOCONDUCTOR_HINTS else "install_command",
                    "evidence": public or path.name,
                    "required": False,
                    "category": "install_hint",
                }
            )
    return {
        "python_records": _dedupe_records(python_records, "name"),
        "r_records": _dedupe_records(r_records, "name"),
    }


def python_documentation_hint_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".rst", ".rmd", ".ipynb"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        public = public_local_path(path, root) or path.name
        for needle, package in PYTHON_DOCUMENTATION_HINTS.items():
            if re.search(rf"(?<![a-z0-9_-]){re.escape(needle)}(?![a-z0-9_-])", text):
                record = _python_record(package, "documentation_hint", public, required=False, category="install_hint")
                if record:
                    records.append(record)
    return _dedupe_records(records, "name")


def pip_install_specs(text: str) -> list[str]:
    specs = []
    for match in re.finditer(r"\b(?:python\s+-m\s+)?pip\s+install\s+([^\n`;&|]+)", text, flags=re.I):
        for token in re.split(r"\s+", match.group(1).strip()):
            clean = token.strip().strip("'\"")
            if not clean or clean.startswith("-"):
                continue
            if clean in {"install", "quiet", "upgrade"}:
                continue
            if "://" in clean and "#egg=" in clean:
                clean = clean.split("#egg=", 1)[1]
            specs.append(clean)
    return specs


def r_install_packages(text: str) -> list[str]:
    packages = []
    for match in re.finditer(r"\b(?:BiocManager::install|install\.packages)\s*\(([^)]*)\)", text, flags=re.S):
        inner = match.group(1)
        packages.extend(re.findall(r"['\"]([A-Za-z][A-Za-z0-9_.]*)['\"]", inner))
    return packages


def rscript_executables(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in root.rglob("*.R"):
        source = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bcommandArgs\s*\(", source) or re.search(r"\blibrary\s*\(\s*(optparse|argparse|docopt)\s*\)", source) or re.search(r"\b(optparse|argparse|docopt)::", source):
            result.append({"name": "Rscript", "source": public_local_path(path, root), "required": True, "category": "runtime"})
    return _dedupe_records(result, "name")


def parse_namespace_dependency_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    records = []
    for group in re.findall(r"\bimport\(([^)]+)\)", text):
        for package in split_r_namespace_group(group):
            records.append(_namespace_record(package, "NAMESPACE:import"))
    for group in re.findall(r"\bimportFrom\(([^)]+)\)", text):
        parts = split_r_namespace_group(group)
        if parts:
            records.append(_namespace_record(parts[0], "NAMESPACE:importFrom"))
    return _dedupe_records([record for record in records if record], "name")


def split_r_namespace_group(group: str) -> list[str]:
    return [item.strip().strip("'\"") for item in group.split(",") if item.strip()]


def _namespace_record(package: str, evidence: str) -> dict[str, Any] | None:
    if not package or package in R_BASE_PACKAGES:
        return None
    return {
        "name": package,
        "source": "Bioconductor_or_unknown" if package in BIOCONDUCTOR_HINTS else "NAMESPACE",
        "evidence": evidence,
        "required": True,
        "category": "runtime",
    }


def _dedupe_records(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        deduped.setdefault(str(record[key]), record)
    return list(deduped.values())
