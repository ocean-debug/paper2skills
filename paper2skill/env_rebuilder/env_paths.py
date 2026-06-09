from __future__ import annotations

import sys
from pathlib import Path


def resolve_env_path(env: str, base_dir: str | Path | None = None) -> str:
    value = str(env or "").strip()
    if not value:
        raise ValueError("environment name/path is required")
    path = Path(value)
    if path.is_absolute() or "/" in value or "\\" in value:
        return str(path)
    if base_dir is None:
        return value
    return str(Path(base_dir) / ".benchmark" / "envs" / value)


def is_path_env(env: str | Path) -> bool:
    value = str(env)
    return Path(value).is_absolute() or "/" in value or "\\" in value


def uv_python_executable(env_path: str | Path) -> str:
    root = Path(env_path)
    if sys.platform.startswith("win"):
        return str(root / "Scripts" / "python")
    return str(root / "bin" / "python")


def conda_env_args(env: str) -> list[str]:
    if is_path_env(env):
        return ["-p", env]
    return ["-n", env]
