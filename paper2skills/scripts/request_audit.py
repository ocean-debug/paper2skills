"""Audit normalized build request contracts and execution boundaries."""

from __future__ import annotations

from typing import Any

from common import as_list, now_utc
from constants import SCHEMA_VERSION


LIST_FIELDS = {
    "tutorial_links",
    "doc_links",
    "paper_links",
    "paper_dois",
    "api_names",
    "source_material_paths",
    "existing_skills_dirs",
    "requested_task_types",
    "execution_traces",
    "execution_replay_results",
    "eval_results",
    "agent_rollout_results",
    "agent_review_proposals",
    "smoke_test_results",
    "e2e_acceptance_results",
}
POSITIVE_INT_FIELDS = {"max_fetch_bytes", "max_index_files", "max_index_bytes", "review_iterations"}
REMOTE_REQUIRED_FIELDS = {"host", "working_directory", "environment_name", "node", "cores"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    field: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if field:
        item["field"] = field
    findings.append(item)


def is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(item for item in value)


def remote_environment_required(environment: dict[str, Any]) -> bool:
    return environment.get("mode") == "remote" or bool(environment.get("remote_only"))


def build_request_audit(request: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    if not request.get("package_name") and not request.get("method_name"):
        add_finding(findings, "error", "missing_package_or_method", "Build request needs package_name or method_name.", "package_name")
    if not request.get("repo_url"):
        add_finding(findings, "error", "missing_repo_url", "Build request needs repo_url for source/API grounding.", "repo_url")
    if request.get("target_agent") != "codex":
        add_finding(findings, "error", "target_agent_not_codex", "paper2skills currently targets Codex child skills.", "target_agent")

    source_support_fields = ["tutorial_links", "doc_links", "paper_links", "source_material_paths"]
    has_supporting_sources = any(is_non_empty_list(request.get(field)) for field in source_support_fields)
    if not has_supporting_sources:
        add_finding(
            findings,
            "warning",
            "repo_only_source_grounding",
            "Request has no tutorial, docs, paper, or local source material beyond repo_url; generated contracts may be weaker.",
        )

    for field in sorted(LIST_FIELDS):
        if not isinstance(request.get(field), list):
            add_finding(findings, "error", "request_field_not_list", "Request field must be a list after normalization.", field)

    for field in sorted(POSITIVE_INT_FIELDS):
        try:
            value = int(request.get(field))
        except (TypeError, ValueError):
            add_finding(findings, "error", "request_field_not_integer", "Request field must be an integer.", field)
            continue
        if value <= 0:
            add_finding(findings, "error", "request_field_not_positive", "Request field must be positive.", field)

    try:
        ratio = float(request.get("review_min_score_ratio"))
    except (TypeError, ValueError):
        add_finding(findings, "error", "review_min_score_ratio_not_number", "review_min_score_ratio must be numeric.", "review_min_score_ratio")
    else:
        if ratio <= 0 or ratio > 1:
            add_finding(findings, "error", "review_min_score_ratio_out_of_range", "review_min_score_ratio must be in (0, 1].", "review_min_score_ratio")

    environment = request.get("execution_environment") if isinstance(request.get("execution_environment"), dict) else {}
    if request.get("execution_grounded") and not as_list(request.get("execution_traces")):
        add_finding(
            findings,
            "warning",
            "execution_grounded_without_supplied_traces",
            "execution_grounded is true but no execution_traces were supplied; no task_type can be marked execution_verified.",
            "execution_traces",
        )
    if remote_environment_required(environment):
        missing = sorted(field for field in REMOTE_REQUIRED_FIELDS if not environment.get(field))
        for field in missing:
            add_finding(
                findings,
                "error",
                "missing_remote_execution_field",
                "Remote execution requests must provide host, working_directory, environment_name, node, and cores.",
                f"execution_environment.{field}",
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "target_agent": request.get("target_agent"),
        "language_backend": request.get("language_backend"),
        "source_support_fields": source_support_fields,
        "has_supporting_sources": has_supporting_sources,
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "remote_environment_required": remote_environment_required(environment),
        "findings": findings,
        "policy": [
            "Build request audit is static and non-executing.",
            "Repo-only grounding is allowed but weaker than tutorial/docs/local source grounding.",
            "Remote-only execution requests must provide explicit environment fields before replay planning.",
        ],
    }
