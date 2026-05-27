from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def forced_missing_packages() -> set[str]:
    raw = os.environ.get("PAPER2SKILL_FORCE_MISSING_PACKAGES", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def forced_missing_executables() -> set[str]:
    raw = os.environ.get("PAPER2SKILL_FORCE_MISSING_EXECUTABLES", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def rscript_path() -> str | None:
    if "Rscript" in forced_missing_executables():
        return None
    return shutil.which("Rscript")


def probe_r_package(name: str, source: str = "CRAN_or_unknown", required: bool = True) -> dict[str, Any]:
    executable = rscript_path()
    forced = forced_missing_packages()
    installed = False
    if executable and name not in forced:
        command = [executable, "-e", f"quit(status = ifelse(requireNamespace('{name}', quietly=TRUE), 0, 1))"]
        installed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    return {"name": name, "installed": installed, "source": source, "required": required}


def probe_r(packages: list[dict[str, Any] | str] | None = None, require_rscript: bool = False) -> dict[str, Any]:
    executable = rscript_path()
    version = None
    if executable:
        try:
            proc = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
            version = (proc.stdout or proc.stderr).strip().splitlines()[0]
        except Exception:
            version = None
    records = []
    for item in packages or []:
        if isinstance(item, str):
            records.append(probe_r_package(item))
        else:
            records.append(probe_r_package(item["name"], item.get("source", "CRAN_or_unknown"), item.get("required", True)))
    return {
        "rscript_available": executable is not None,
        "rscript": executable,
        "version": version,
        "required": require_rscript or bool(records),
        "packages": records,
    }
