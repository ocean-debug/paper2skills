from __future__ import annotations

from typing import Any


def infer_io_contract(tutorial_trace: dict[str, Any]) -> dict[str, Any]:
    inputs = []
    outputs = []
    for step in tutorial_trace.get("workflow_steps", []):
        inputs.extend(step.get("inputs", []))
        outputs.extend(step.get("outputs", []))
    return {
        "input_contract": {
            "required": [
                {"name": "input_manifest", "type": "yaml", "state": "required"},
                {"name": "primary_data", "type": "file", "state": "not_confirmed" if not inputs else "tutorial_confirmed"},
            ]
        },
        "output_contract": {
            "required": ["qc/environment_report.json", "qc/input_validation.json", "workflow/plan.json", "result.json", "results/"],
            "tutorial_outputs": sorted(dict.fromkeys(outputs)),
        },
    }
