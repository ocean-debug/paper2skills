from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = [
    "result.json",
    "qc/input_validation.json",
    "qc/environment_report.json",
    "qc/missing_dependencies.json",
    "workflow/plan.json",
    "workflow/plan.md",
    "parameters/resolved_parameters.json",
    "reproducibility/source_manifest.json",
]


def validate_result_dir(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    missing = [rel for rel in REQUIRED_OUTPUTS if not (root / rel).exists()]
    return {"status": "pass" if not missing else "fail", "missing": missing}
