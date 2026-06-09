from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_expected_outputs(outputs: list[dict[str, Any]] | None, run_dir: str | Path | None = None) -> dict[str, Any]:
    outputs = outputs or []
    base = Path(run_dir) if run_dir else None
    missing: list[str] = []
    checked: list[str] = []
    for item in outputs:
        if not item.get("required", True):
            continue
        name = str(item.get("path") or item.get("name") or "")
        if not name:
            continue
        checked.append(name)
        if base and not (base / name).exists():
            missing.append(name)
    return {"passed": not missing, "checked": checked, "missing": missing}

