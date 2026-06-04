from __future__ import annotations

from typing import Any


def infer_environment_spec(dependencies: dict[str, Any], language: str = "unknown") -> dict[str, Any]:
    python_records = dependencies.get("python_records") or [{"spec": item, "required": True, "category": "runtime", "source": "legacy"} for item in dependencies.get("python", [])]
    r_packages = dependencies.get("r_records") or [{"name": item, "source": "CRAN_or_unknown", "required": True, "category": "runtime"} for item in dependencies.get("r", [])]
    return {
        "install_policy": "ask",
        "python": {
            "packages": [item for item in python_records if item.get("required", True)],
        },
        "r": {
            "required": language == "r" or bool(r_packages),
            "packages": r_packages,
        },
        "executables": dependencies.get("executables", []),
        "conda": {
            "packages": dependencies.get("conda_records", []),
        },
        "system_requirements": dependencies.get("system_requirements", []),
        "external_resources": dependencies.get("external_resources", []),
        "optional_dependencies": dependencies.get("optional", {"python": {}, "r": {}}),
        "ignored_dependencies": dependencies.get("ignored", []),
        "optional": {
            "cuda": "record_only",
            "system_libraries": "record_only",
            "external_databases": "record_only",
        },
    }
