from __future__ import annotations

from typing import Any


ALGORITHM_ARCHETYPES = {
    "python_api_package",
    "r_bioconductor_package",
    "cli_tool",
    "workflow_engine",
    "notebook_tutorial",
    "script_tutorial",
    "containerized_method",
    "library_plus_agent_wrapper",
}

ADAPTER_INTERFACE_KEYS = [
    "adapter_type",
    "entrypoint",
    "install_contract",
    "input_binding",
    "run_command_or_api",
    "expected_outputs",
    "verification",
    "status",
]


def infer_algorithm_archetype(
    repo_evidence: dict[str, Any],
    tutorial_trace: dict[str, Any],
    classification: dict[str, Any],
    adapter_type: str,
) -> dict[str, Any]:
    """Classify the execution shape without naming a specific algorithm."""
    language = str(classification.get("language") or "unknown").lower()
    package_type = str(repo_evidence.get("package_type") or "").lower()
    tutorials = tutorial_trace.get("tutorials") if isinstance(tutorial_trace.get("tutorials"), list) else []
    tutorial_paths = [str(item.get("path") or "").lower() for item in tutorials if isinstance(item, dict)]
    all_text = "\n".join(_flatten_strings({"repo": repo_evidence, "tutorials": tutorials})).lower()

    evidence: list[str] = []
    if repo_evidence.get("workflow_engines") or adapter_type == "workflow_engine":
        archetype = "workflow_engine"
        evidence.append("repo.workflow_engines")
    elif _has_container_signal(all_text, tutorial_paths):
        archetype = "containerized_method"
        evidence.append("tutorial_or_repo.container_signal")
    elif adapter_type == "cli" or repo_evidence.get("entrypoints") or repo_evidence.get("cli_commands"):
        archetype = "cli_tool"
        evidence.append("repo.cli_or_entrypoint")
    elif adapter_type == "notebook" or any(path.endswith((".ipynb", ".rmd", ".qmd")) for path in tutorial_paths):
        archetype = "notebook_tutorial"
        evidence.append("tutorial.notebook")
    elif adapter_type == "r_script" or package_type == "r_package" or language == "r":
        archetype = "r_bioconductor_package" if _has_bioconductor_signal(all_text) else "script_tutorial"
        evidence.append("repo_or_tutorial.r_signal")
    elif adapter_type == "python_api" and package_type.startswith("python_"):
        archetype = "python_api_package" if repo_evidence.get("api_functions") else "library_plus_agent_wrapper"
        evidence.append("repo.python_package")
    elif any(path.endswith((".py", ".r", ".sh")) for path in tutorial_paths):
        archetype = "script_tutorial"
        evidence.append("tutorial.script")
    else:
        archetype = "library_plus_agent_wrapper"
        evidence.append("fallback.no_direct_runner")

    return {
        "archetype": archetype,
        "adapter_type": adapter_type,
        "confidence": "medium" if evidence else "low",
        "evidence": evidence,
        "interface": default_adapter_interface(adapter_type, archetype),
        "supported_archetypes": sorted(ALGORITHM_ARCHETYPES),
    }


def default_adapter_interface(adapter_type: str, archetype: str) -> dict[str, Any]:
    return {
        "adapter_type": adapter_type,
        "archetype": archetype,
        "entrypoint": None,
        "install_contract": {"install_policy": "ask", "auto_install_requires_confirmation": True},
        "input_binding": {"status": "not_confirmed", "manifest_required": True},
        "run_command_or_api": None,
        "expected_outputs": [],
        "verification": {"status": "not_run", "source": "static_inference"},
        "status": "dry_run_only",
    }


def _has_container_signal(text: str, paths: list[str]) -> bool:
    if any(path.endswith(("dockerfile", "singularity.def")) or "dockerfile" in path for path in paths):
        return True
    return any(token in text for token in ["docker run", "singularity exec", "apptainer exec", "container image"])


def _has_bioconductor_signal(text: str) -> bool:
    return "biocmanager::install" in text or "bioconductor" in text or "biocviews" in text


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    if value is None:
        return []
    return [str(value)]
