from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.runtime.env_manager import inspect_environment, load_environment_spec


def validate_environment_spec(path: str | Path) -> dict[str, Any]:
    spec = load_environment_spec(path)
    return inspect_environment(spec)
