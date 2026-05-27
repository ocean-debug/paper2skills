from __future__ import annotations

from typing import Any


def classify_algorithm(repo_evidence: dict[str, Any], tutorial_trace: dict[str, Any]) -> dict[str, str]:
    language = repo_evidence.get("language")
    if language == "unknown":
        languages = {trace.get("language") for trace in tutorial_trace.get("tutorials", [])}
        if "python" in languages:
            language = "python"
        elif "r" in languages:
            language = "r"
    return {
        "domain": "bioinformatics",
        "language": language or "unknown",
        "execution_mode": "python_api" if language == "python" else ("r_script" if language == "r" else "unknown"),
    }
