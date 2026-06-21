#!/usr/bin/env python
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "assets" / "paper2skill_runtime"
REQUIRED_MODULES = {
    "jinja2": "Jinja2>=3.1",
    "packaging": "packaging>=23",
    "yaml": "PyYAML>=6.0",
}


def missing_requirements() -> list[str]:
    missing: list[str] = []
    for module, requirement in REQUIRED_MODULES.items():
        try:
            __import__(module)
        except ModuleNotFoundError:
            missing.append(requirement)
    return missing


def print_install_plan(requirements: list[str]) -> None:
    joined = " ".join(f'"{requirement}"' for requirement in requirements)
    print("Paper2Skill bundled runtime dependencies are missing.", file=sys.stderr)
    print("Install plan:", file=sys.stderr)
    print(f"  python -m pip install {joined}", file=sys.stderr)
    print("No packages were installed automatically.", file=sys.stderr)


def main() -> int:
    if not (RUNTIME / "paper2skill" / "cli.py").is_file():
        print(f"Paper2Skill bundled runtime is missing: {RUNTIME}", file=sys.stderr)
        return 2
    missing = missing_requirements()
    if missing:
        print_install_plan(missing)
        return 2
    sys.path.insert(0, str(RUNTIME))
    sys.argv = [sys.argv[0], *sys.argv[1:]]
    try:
        runpy.run_module("paper2skill.cli", run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
