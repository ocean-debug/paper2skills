from __future__ import annotations

import importlib.util
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from typing import Any


SPEC_SPLIT_RE = re.compile(r"\s*(?:[<>=!~]=?|;)")


def import_name_from_spec(spec: str, explicit_import: str | None = None) -> str:
    if explicit_import:
        return explicit_import
    base = re.split(r"\s+@\s+", spec.strip(), maxsplit=1)[0]
    base = SPEC_SPLIT_RE.split(base, maxsplit=1)[0]
    base = base.split("[", 1)[0]
    return base.replace("-", "_").strip()


def forced_missing_packages() -> set[str]:
    raw = os.environ.get("PAPER2SKILL_FORCE_MISSING_PACKAGES", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def probe_python_package(spec: str, import_name: str | None = None, required: bool = True) -> dict[str, Any]:
    probe_name = import_name_from_spec(spec, import_name)
    forced = forced_missing_packages()
    installed = probe_name not in forced and spec not in forced and _distribution_or_import_available(probe_name)
    return {"name": spec, "import_name": probe_name, "installed": installed, "required": required}


def _distribution_or_import_available(name: str) -> bool:
    try:
        importlib.metadata.version(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        pass
    return importlib.util.find_spec(name) is not None


def probe_python(packages: list[dict[str, Any] | str] | None = None) -> dict[str, Any]:
    pip_available = False
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pip_available = True
    except Exception:
        pip_available = False
    records = []
    for item in packages or []:
        if isinstance(item, str):
            records.append(probe_python_package(item))
        else:
            records.append(probe_python_package(item["spec"], item.get("import_name"), item.get("required", True)))
    return {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "pip_available": pip_available,
        "on_path": shutil.which("python") is not None or shutil.which("python3") is not None,
        "packages": records,
    }
