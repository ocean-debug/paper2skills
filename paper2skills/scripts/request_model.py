"""Build request normalization and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import BuildError
from constants import SCHEMA_VERSION


def normalize_request(raw: dict[str, Any], out: Path) -> dict[str, Any]:
    request = dict(raw)
    request.setdefault("schema_version", SCHEMA_VERSION)
    request.setdefault("target_agent", "codex")
    request.setdefault("language_backend", "python")
    request.setdefault("execution_grounded", False)
    request.setdefault("execution_traces", [])
    request.setdefault("execution_replay_results", [])
    request.setdefault("eval_results", [])
    request.setdefault("agent_rollout_results", [])
    request.setdefault("agent_skillopt_proposals", [])
    request.setdefault("smoke_test_results", [])
    request.setdefault("require_smoke_test", False)
    request.setdefault("e2e_acceptance_results", [])
    request.setdefault("require_e2e_acceptance", False)
    request.setdefault("execution_environment", {})
    request.setdefault("tutorial_links", [])
    request.setdefault("doc_links", [])
    request.setdefault("paper_links", [])
    request.setdefault("paper_dois", [])
    request.setdefault("api_names", [])
    request.setdefault("source_material_paths", [])
    request.setdefault("existing_skills_dirs", [])
    request.setdefault("requested_task_types", [])
    request.setdefault("fetch_sources", False)
    request.setdefault("max_fetch_bytes", 5_000_000)
    request.setdefault("max_index_files", 500)
    request.setdefault("max_index_bytes", 250_000)
    request.setdefault("review_iterations", 3)
    request.setdefault("review_min_score_ratio", 0.875)
    request.setdefault("output_dir", str(out))
    if not request.get("package_name") and not request.get("method_name"):
        raise BuildError("build request needs package_name or method_name")
    if not request.get("repo_url"):
        raise BuildError("build request needs repo_url")
    if request.get("target_agent") != "codex":
        raise BuildError("Papert2Skills currently targets target_agent: codex")
    return request
