from __future__ import annotations

from pathlib import Path


def required_skill_sections() -> list[str]:
    return [
        "What this skill does",
        "When to use",
        "When not to use",
        "Required inputs",
        "Input state requirements",
        "Environment policy",
        "Preflight workflow",
        "Planning workflow",
        "Execution workflow",
        "Output contract",
        "Validation workflow",
        "Interpretation boundary",
        "Failure modes",
        "Evidence sources",
    ]
