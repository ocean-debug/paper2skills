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
    if repo_evidence.get("workflow_engines"):
        execution_mode = "workflow_engine"
    elif repo_evidence.get("entrypoints") or repo_evidence.get("cli_commands"):
        execution_mode = "cli"
    elif language == "python":
        execution_mode = "python_api"
    elif language == "r":
        execution_mode = "r_script"
    else:
        execution_mode = "unknown"
    return {
        "domain": "bioinformatics",
        "language": language or "unknown",
        "execution_mode": execution_mode,
    }
