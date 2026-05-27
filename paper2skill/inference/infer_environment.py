from __future__ import annotations

from typing import Any


def infer_environment_spec(dependencies: dict[str, Any], language: str = "unknown") -> dict[str, Any]:
    r_packages = [{"name": item, "source": "CRAN_or_unknown", "required": True} for item in dependencies.get("r", [])]
    return {
        "install_policy": "ask",
        "python": {
            "packages": [{"spec": item, "required": True} for item in dependencies.get("python", [])],
        },
        "r": {
            "required": language == "r" or bool(r_packages),
            "packages": r_packages,
        },
        "executables": dependencies.get("executables", []),
        "optional": {
            "cuda": "record_only",
            "system_libraries": "record_only",
            "external_databases": "record_only",
        },
    }
