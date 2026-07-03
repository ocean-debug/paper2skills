"""Audit task_type partition quality and anti-patterns."""

from __future__ import annotations

import re
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


TUTORIAL_SPLIT_TERMS = {
    "tutorial",
    "example",
    "demo",
    "notebook",
    "vignette",
    "quickstart",
    "walkthrough",
    "lesson",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        item["task_type"] = task_type
    findings.append(item)


def terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9]+", value.lower().replace("_", " ")))


def task_types(task_catalog: dict[str, Any]) -> list[str]:
    return [str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")]


def build_task_partition_audit(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    task_conflict_matrix: dict[str, Any],
    tutorial_catalog: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tasks = task_catalog.get("tasks", [])
    names = task_types(task_catalog)
    tutorial_count = int(tutorial_catalog.get("tutorial_count") or 0)

    if not task_catalog.get("one_package_one_skill"):
        add_finding(findings, "error", "one_package_one_skill_false", "Task partition must keep one package as one child skill.")
    if not names:
        add_finding(findings, "error", "missing_task_types", "Task partition produced no task_type entries.")
    if len(names) != len(set(names)):
        add_finding(findings, "error", "duplicate_task_type", "Task partition contains duplicate task_type entries.")

    for task in tasks:
        task_type = str(task.get("task_type"))
        task_terms = terms(task_type)
        if task_terms.intersection(TUTORIAL_SPLIT_TERMS):
            add_finding(
                findings,
                "error",
                "tutorial_granularity_task_type",
                "Task_type names must describe package capabilities, not tutorial/demo/notebook artifacts.",
                task_type,
            )
        if task.get("skill_scope") != "same_child_skill":
            add_finding(
                findings,
                "error",
                "task_scope_not_same_child_skill",
                "Capabilities must stay inside one child skill as task_type entries.",
                task_type,
            )
        if not task.get("routing_cues"):
            add_finding(findings, "error", "task_missing_routing_cues", "Task_type has no routing cues.", task_type)
        if not (task.get("input_contract") or {}).get("required_from_user"):
            add_finding(findings, "error", "task_missing_input_contract", "Task_type has no required input contract.", task_type)
        if not (task.get("output_contract") or {}).get("expected_outputs"):
            add_finding(findings, "error", "task_missing_output_contract", "Task_type has no expected output contract.", task_type)
        if not task.get("refusal_boundaries"):
            add_finding(findings, "error", "task_missing_refusal_boundaries", "Task_type has no refusal boundaries.", task_type)

    route_tasks = {str(route.get("task_type")) for route in router.get("routes", []) if route.get("task_type")}
    for task_type in sorted(set(names).difference(route_tasks)):
        add_finding(findings, "error", "task_missing_router_entry", "Task_type is missing from the router.", task_type)

    if tutorial_count > 1 and len(names) == tutorial_count:
        add_finding(
            findings,
            "warning",
            "task_count_matches_tutorial_count",
            "Task count matches tutorial count; verify capabilities were not split one tutorial at a time.",
        )
    high_ambiguity_pairs = [
        pair for pair in task_conflict_matrix.get("pairs", [])
        if pair.get("conflict_level") in {"high_ambiguity", "medium_ambiguity"}
    ]
    if high_ambiguity_pairs:
        add_finding(
            findings,
            "warning",
            "ambiguous_task_partition",
            "Some task_type pairs are ambiguous; review whether they should be merged or need stronger routing rules.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "task_count": len(names),
        "tutorial_count": tutorial_count,
        "task_types": names,
        "checked_anti_patterns": sorted(TUTORIAL_SPLIT_TERMS),
        "ambiguous_pair_count": len(high_ambiguity_pairs),
        "findings": findings,
        "policy": [
            "Task partition must represent capabilities as task_type entries inside one child skill.",
            "Task_type entries must not be split one tutorial, notebook, example, or demo at a time.",
            "Ambiguous task_type pairs should ask clarifying questions or be merged during review.",
        ],
    }
