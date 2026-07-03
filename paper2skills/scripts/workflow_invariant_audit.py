"""Audit Papert2Skills first-principles workflow invariants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, slugify
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        finding["task_type"] = task_type
    findings.append(finding)


def task_set(task_catalog: dict[str, Any]) -> set[str]:
    return {str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")}


def task_values(items: list[dict[str, Any]], key: str = "task_type") -> set[str]:
    return {str(item.get(key)) for item in items if item.get(key)}


def check_missing_tasks(
    findings: list[dict[str, Any]],
    all_tasks: set[str],
    covered_tasks: set[str],
    code: str,
    message: str,
) -> None:
    for task_type in sorted(all_tasks.difference(covered_tasks)):
        add_finding(findings, "error", code, message, task_type)


def required_child_files() -> set[str]:
    return {"SKILL.md"} | {f"references/{name}" for name in REQUIRED_CHILD_REFERENCES}


def actual_child_files(child_skill_dir: Path) -> set[str]:
    if not child_skill_dir.exists():
        return set()
    return {
        str(path.relative_to(child_skill_dir)).replace("\\", "/")
        for path in child_skill_dir.rglob("*")
        if path.is_file()
    }


def audit_workflow_invariants(
    request: dict[str, Any],
    child_skill_dir: Path,
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    eval_plan: dict[str, Any],
    execution_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    contract_traceability: dict[str, Any],
    lineage_graph: dict[str, Any],
    claim_consistency_audit: dict[str, Any],
    backend_contract: dict[str, Any],
    draft_candidates: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tasks = task_set(task_catalog)

    if request.get("target_agent") != "codex":
        add_finding(findings, "error", "target_agent_not_codex", "Papert2Skills must target Codex child skills.")
    if not task_catalog.get("one_package_one_skill"):
        add_finding(findings, "error", "one_package_one_skill_false", "Task catalog must keep one package as one child skill.")
    for task in task_catalog.get("tasks", []):
        if task.get("skill_scope") != "same_child_skill":
            add_finding(
                findings,
                "error",
                "task_scope_not_same_child_skill",
                "Task_type must remain inside the same child skill.",
                str(task.get("task_type")),
            )
    if draft_candidates.get("candidate_count") != 1:
        add_finding(findings, "error", "candidate_count_not_one", "Build must produce exactly one child-skill candidate.")
    for candidate in draft_candidates.get("candidates", []):
        if not candidate.get("one_package_one_skill"):
            add_finding(findings, "error", "candidate_not_one_package_one_skill", "Draft candidate violates one-package-one-skill invariant.")
        if candidate.get("target_agent") != "codex":
            add_finding(findings, "error", "candidate_target_agent_not_codex", "Draft candidate does not target Codex.")

    expected_dir_name = slugify(str(request.get("method_name") or request.get("package_name") or "skill"))
    if child_skill_dir.name != expected_dir_name:
        add_finding(findings, "warning", "child_skill_dir_name_mismatch", "Child skill directory name does not match method/package slug.")
    missing_files = sorted(required_child_files().difference(actual_child_files(child_skill_dir)))
    for _path in missing_files:
        add_finding(findings, "error", "missing_child_skill_file", "Required child-skill file is missing.")

    if str(request.get("language_backend") or "python").lower() == "python":
        if backend_contract.get("status") != "supported":
            add_finding(findings, "error", "python_backend_not_supported", "Python backend request must be supported.")
    else:
        if backend_contract.get("status") != "extension_reserved":
            add_finding(findings, "error", "non_python_backend_not_reserved", "Non-Python backends must be explicit extension reservations.")
        for task in task_catalog.get("tasks", []):
            reasons = {boundary.get("reason_key") for boundary in task.get("refusal_boundaries", [])}
            if "backend_not_implemented" not in reasons:
                add_finding(
                    findings,
                    "error",
                    "missing_backend_refusal_boundary",
                    "Non-Python backend requires backend_not_implemented refusal boundary.",
                    str(task.get("task_type")),
                )

    if not tasks:
        add_finding(findings, "error", "no_task_types", "Workflow must produce at least one task_type.")
    check_missing_tasks(
        findings,
        tasks,
        task_values(router.get("routes", [])),
        "task_missing_router_entry",
        "Task_type is missing from task_type_router.",
    )
    check_missing_tasks(
        findings,
        tasks,
        task_values(eval_plan.get("scenarios", [])),
        "task_missing_eval_scenario",
        "Task_type is missing from eval_plan.",
    )
    check_missing_tasks(
        findings,
        tasks,
        task_values(execution_plan.get("tasks", [])),
        "task_missing_execution_plan",
        "Task_type is missing from execution_plan.",
    )
    check_missing_tasks(
        findings,
        tasks,
        task_values(tutorial_reproduction_plan.get("replays", [])),
        "task_missing_tutorial_reproduction_plan",
        "Task_type is missing from tutorial_reproduction_plan.",
    )
    check_missing_tasks(
        findings,
        tasks,
        task_values(contract_traceability.get("records", [])),
        "task_missing_contract_traceability",
        "Task_type is missing from contract_traceability.",
    )
    lineage_tasks = {
        str(node.get("task_type") or str(node.get("id", "")).removeprefix("task:"))
        for node in lineage_graph.get("nodes", [])
        if node.get("kind") == "task_type" or str(node.get("id", "")).startswith("task:")
    }
    check_missing_tasks(
        findings,
        tasks,
        lineage_tasks,
        "task_missing_lineage_node",
        "Task_type is missing from lineage_graph.",
    )
    claim_tasks = set(claim_consistency_audit.get("allowed_task_types", []))
    check_missing_tasks(
        findings,
        tasks,
        claim_tasks,
        "task_missing_claim_consistency_coverage",
        "Task_type is missing from claim consistency audit coverage.",
    )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "task_count": len(tasks),
        "checked_invariants": [
            "target_agent_codex",
            "one_package_one_child_skill",
            "task_type_internal_capabilities",
            "python_first_backend_with_r_extension_reserved",
            "single_draft_candidate",
            "task_coverage_across_router_eval_execution_tutorial_contract_lineage_claim_audit",
            "lightweight_child_skill_file_set",
        ],
        "findings": findings,
        "policy": "Workflow invariants protect the Papert2Skills product shape across all generated artifacts.",
    }
