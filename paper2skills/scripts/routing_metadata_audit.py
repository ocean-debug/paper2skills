"""Audit task_type routing metadata and rendered child-skill routing guidance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
    path: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        finding["task_type"] = task_type
    if path:
        finding["path"] = path
    findings.append(finding)


def text_map(skill_dir: Path) -> dict[str, str]:
    files = ["SKILL.md", "references/task-types.md", "references/limitations-and-refusal.md"]
    return {rel: read_text(skill_dir / rel) if (skill_dir / rel).exists() else "" for rel in files}


def route_task_types(router: dict[str, Any]) -> set[str]:
    return {str(route.get("task_type")) for route in router.get("routes", []) if route.get("task_type")}


def catalog_task_types(task_catalog: dict[str, Any]) -> set[str]:
    return {str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")}


def audit_routing_metadata(
    skill_dir: Path,
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    task_conflict_matrix: dict[str, Any],
    routing_fixture: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    texts = text_map(skill_dir)
    tasks = catalog_task_types(task_catalog)
    routes = route_task_types(router)

    if router.get("routing_scope") != "inside_single_child_skill":
        add_finding(findings, "error", "wrong_routing_scope", "Router must select task_type entries inside one child skill.")
    if tasks != routes:
        for task_type in sorted(tasks.difference(routes)):
            add_finding(findings, "error", "task_missing_route", "Task_type is missing from router routes.", task_type)
        for task_type in sorted(routes.difference(tasks)):
            add_finding(findings, "error", "route_missing_task", "Router route does not map to a task_catalog task_type.", task_type)
    selection_order = " ".join(str(item).lower() for item in router.get("selection_order", []))
    for required in ("ask", "refuse", "metadata"):
        if required not in selection_order:
            add_finding(findings, "error", "routing_order_missing_boundary", "Router selection_order must include ask/refuse/metadata boundaries.")

    for route in router.get("routes", []):
        task_type = str(route.get("task_type") or "")
        if not route.get("choose_when"):
            add_finding(findings, "error", "route_missing_choose_when", "Route is missing choose_when cues.", task_type)
        if not route.get("ask_when"):
            add_finding(findings, "error", "route_missing_ask_when", "Route is missing ask_when ambiguity rules.", task_type)
        if not route.get("refuse_when"):
            add_finding(findings, "error", "route_missing_refuse_when", "Route is missing refusal reason keys.", task_type)
        if not route.get("evidence_refs"):
            add_finding(findings, "error", "route_missing_evidence_refs", "Route is missing evidence references.", task_type)
        for rel in ("SKILL.md", "references/task-types.md"):
            if task_type and task_type not in texts.get(rel, ""):
                add_finding(findings, "error", "route_not_rendered", "Route task_type is not rendered in child routing docs.", task_type, rel)
        for reason_key in route.get("refuse_when", []):
            if reason_key and str(reason_key) not in texts.get("references/limitations-and-refusal.md", ""):
                add_finding(findings, "error", "route_refusal_not_rendered", "Route refusal reason is not rendered in limitations-and-refusal.md.", task_type, "references/limitations-and-refusal.md")

    if "Task-Type Routing" not in texts.get("SKILL.md", ""):
        add_finding(findings, "error", "skill_missing_routing_section", "SKILL.md must include a task-type routing section.", path="SKILL.md")
    if "Routing Order" not in texts.get("references/task-types.md", ""):
        add_finding(findings, "error", "task_types_missing_routing_order", "task-types.md must include routing order.", path="references/task-types.md")
    if "not by switching to separate capability skills" not in texts.get("references/task-types.md", ""):
        add_finding(findings, "error", "task_types_missing_single_skill_boundary", "task-types.md must state that task_type selection stays inside one child skill.", path="references/task-types.md")

    case_kinds = set(routing_fixture.get("case_kinds", []))
    for required_kind in ("select_task_type", "structured_refusal", "unsupported_task"):
        if required_kind not in case_kinds:
            add_finding(findings, "error", "routing_fixture_missing_case_kind", "Routing fixture is missing a required case kind.")
    if task_conflict_matrix.get("pair_count", 0) > 0 and "ask_on_ambiguity" not in case_kinds:
        add_finding(findings, "error", "routing_fixture_missing_ambiguity_case", "Conflicting task_type pairs require ask_on_ambiguity fixtures.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "routing_scope": router.get("routing_scope"),
        "task_count": len(tasks),
        "route_count": len(routes),
        "conflict_pair_count": task_conflict_matrix.get("pair_count", 0),
        "fixture_case_kinds": sorted(case_kinds),
        "rendered_files_checked": sorted(texts),
        "findings": findings,
        "policy": [
            "Task routing must select task_type entries inside one child skill.",
            "Ambiguous requests must ask for missing distinctions instead of guessing.",
            "Unsupported or under-specified requests must use rendered refusal boundaries.",
        ],
    }
