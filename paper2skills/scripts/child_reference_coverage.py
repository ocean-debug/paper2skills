"""Audit whether rendered child references consume key build artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    value: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    if value:
        item["value"] = value
    findings.append(item)


def markdown_texts(skill_dir: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.is_file():
            texts[str(path.relative_to(skill_dir)).replace("\\", "/")] = read_text(path)
    return texts


def require_text(
    findings: list[dict[str, Any]],
    texts: dict[str, str],
    path: str,
    needle: str,
    code: str,
    message: str,
) -> None:
    if needle not in texts.get(path, ""):
        add_finding(findings, "error", code, message, path=path, value=needle)


def audit_child_reference_coverage(
    skill_dir: Path,
    task_catalog: dict[str, Any],
    source_parsing_coverage: dict[str, Any],
    environment_install_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any],
    evidence_precedence: dict[str, Any],
    task_conflict_matrix: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    texts = markdown_texts(skill_dir)

    required_files = {"SKILL.md"} | {f"references/{name}" for name in REQUIRED_CHILD_REFERENCES}
    for rel in sorted(required_files.difference(texts)):
        add_finding(
            findings,
            "error",
            "missing_child_reference_file",
            "Generated child skill is missing a required Markdown file.",
            path=rel,
        )

    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type") or "")
        if not task_type:
            continue
        for rel in (
            "SKILL.md",
            "references/task-types.md",
            "references/input-output-contracts.md",
            "references/validation.md",
            "references/evidence.md",
        ):
            require_text(
                findings,
                texts,
                rel,
                task_type,
                "task_not_rendered_in_reference",
                "Task_type is missing from a required child reference.",
            )

    if source_parsing_coverage:
        require_text(
            findings,
            texts,
            "references/evidence.md",
            "Source Parsing Coverage",
            "source_parsing_coverage_not_rendered",
            "Source parsing coverage must be rendered into evidence.md.",
        )
        require_text(
            findings,
            texts,
            "references/evidence.md",
            "Parser Capability Matrix",
            "parser_capability_matrix_not_rendered",
            "Parser capability matrix must be rendered into evidence.md.",
        )
        status = source_parsing_coverage.get("status")
        if status:
            require_text(
                findings,
                texts,
                "references/evidence.md",
                f"Status: {status}",
                "source_parsing_status_not_rendered",
                "Source parsing coverage status must be rendered into evidence.md.",
            )

    if environment_install_plan:
        for rel in ("references/environment.md", "references/validation.md"):
            require_text(
                findings,
                texts,
                rel,
                "Plan only:",
                "environment_install_boundary_not_rendered",
                "Environment install plan boundary must be rendered into child references.",
            )
        if environment_install_plan.get("requires_user_approval") is not None:
            require_text(
                findings,
                texts,
                "references/environment.md",
                "User approval required:",
                "environment_approval_boundary_not_rendered",
                "Environment approval boundary must be rendered into environment.md.",
            )

    replays = tutorial_reproduction_plan.get("replays", []) if tutorial_reproduction_plan else []
    if replays:
        require_text(
            findings,
            texts,
            "references/validation.md",
            "Tutorial Replay Plan",
            "tutorial_replay_plan_not_rendered",
            "Tutorial replay plan must be rendered into validation.md.",
        )
        require_text(
            findings,
            texts,
            "references/troubleshooting.md",
            "Replay Boundaries",
            "tutorial_replay_boundaries_not_rendered",
            "Tutorial replay refusal boundaries must be rendered into troubleshooting.md.",
        )

    precedence_tasks = evidence_precedence.get("tasks", []) if evidence_precedence else []
    if precedence_tasks:
        require_text(
            findings,
            texts,
            "references/evidence.md",
            "Evidence Precedence By Task",
            "evidence_precedence_not_rendered",
            "Evidence precedence must be rendered into evidence.md.",
        )
        for item in precedence_tasks:
            task_type = str(item.get("task_type") or "")
            if task_type:
                require_text(
                    findings,
                    texts,
                    "references/evidence.md",
                    task_type,
                    "evidence_precedence_task_not_rendered",
                    "Evidence precedence task entry is missing from evidence.md.",
                )

    if task_conflict_matrix.get("pair_count", 0) > 0:
        require_text(
            findings,
            texts,
            "references/task-types.md",
            "Conflict Matrix",
            "task_conflict_matrix_not_rendered",
            "Task conflict matrix must be rendered into task-types.md when conflicts exist.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "checked_file_count": len(texts),
        "task_count": len(task_catalog.get("tasks", [])),
        "rendered_reference_files": sorted(texts),
        "findings": findings,
        "policy": "Generated child references must consume source parsing, environment, tutorial replay, evidence precedence, and task conflict artifacts.",
    }
