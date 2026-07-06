"""Audit generated child-skill metadata and Codex trigger shape."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION
from lint_skill import frontmatter_fields


REQUIRED_DESCRIPTION_TERMS = ["task_type", "input-output", "refuse"]
FORBIDDEN_METADATA_TERMS = ["external routing selector", "separate routing selector"]
ALLOWED_CHILD_DIRS = {"references"}
ALLOWED_OPTIONAL_DIRS = {"agents"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def slug_like(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value))


def audit_optional_openai_yaml(skill_dir: Path, findings: list[dict[str, Any]]) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        return
    text = read_text(path)
    for field in ["display_name", "short_description", "default_prompt"]:
        if field not in text:
            add_finding(
                findings,
                "error",
                "openai_yaml_missing_interface_field",
                "Optional agents/openai.yaml is present but missing a required interface field.",
                rel(path, skill_dir),
            )


def has_task_workflow_dag(text: str, task_type: str) -> bool:
    heading = f"### `{task_type}`"
    start = text.find(heading)
    if start < 0:
        return False
    next_heading = text.find("\n### `", start + len(heading))
    section = text[start:] if next_heading < 0 else text[start:next_heading]
    return "```mermaid" in section and "flowchart TD" in section


def build_child_metadata_audit(
    request: dict[str, Any],
    child_skill_dir: Path,
    task_catalog: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    skill_md = child_skill_dir / "SKILL.md"
    fields: dict[str, str] = {}
    text = ""
    if not skill_md.exists():
        add_finding(findings, "error", "missing_skill_md", "Generated child skill is missing SKILL.md.", "SKILL.md")
    else:
        text = read_text(skill_md)
        parsed = frontmatter_fields(text)
        if parsed is None:
            add_finding(findings, "error", "invalid_frontmatter", "SKILL.md frontmatter is invalid.", "SKILL.md")
        else:
            fields = parsed

    name = fields.get("name", "")
    description = fields.get("description", "")
    if fields:
        if not slug_like(name):
            add_finding(findings, "error", "non_codex_skill_name", "Child skill frontmatter name must be a short lowercase hyphen slug.", "SKILL.md")
        missing_terms = [term for term in REQUIRED_DESCRIPTION_TERMS if term not in description.lower()]
        if missing_terms:
            add_finding(
                findings,
                "error",
                "description_missing_trigger_terms",
                "Child skill description must mention task_type selection, input-output contracts, and refusal behavior.",
                "SKILL.md",
            )
        if len(description.split()) > 60:
            add_finding(findings, "warning", "description_too_long", "Child skill description should remain concise for Codex triggering.", "SKILL.md")

    lowered_public_text = "\n".join(
        read_text(path).lower()
        for path in child_skill_dir.rglob("*.md")
        if path.is_file()
    )
    for term in FORBIDDEN_METADATA_TERMS:
        if term in lowered_public_text:
            add_finding(
                findings,
                "error",
                "forbidden_child_skill_routing_shape",
                "Child skill must not describe a separate routing selector or multiple capability skills.",
            )

    nested_skill_files = [
        rel(path, child_skill_dir)
        for path in child_skill_dir.rglob("SKILL.md")
        if path != skill_md
    ]
    if nested_skill_files:
        add_finding(
            findings,
            "error",
            "nested_child_skill_detected",
            "One package must produce one child skill; nested SKILL.md files are not allowed.",
        )

    top_dirs = {path.name for path in child_skill_dir.iterdir() if path.is_dir()} if child_skill_dir.exists() else set()
    unexpected_dirs = sorted(top_dirs.difference(ALLOWED_CHILD_DIRS.union(ALLOWED_OPTIONAL_DIRS)))
    if unexpected_dirs:
        add_finding(
            findings,
            "error",
            "unexpected_child_skill_directory",
            "Generated child skill should stay lightweight: SKILL.md plus references, with optional agents metadata only.",
        )
    if (child_skill_dir / "scripts").exists():
        add_finding(
            findings,
            "error",
            "child_scripts_generated_by_default",
            "Child skills must not include scripts by default; add scripts only with explicit adapter evidence.",
            "scripts",
        )

    audit_optional_openai_yaml(child_skill_dir, findings)
    task_types = [str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")]
    missing_task_mentions = [task for task in task_types if f"`{task}`" not in text and task not in text]
    if missing_task_mentions:
        add_finding(
            findings,
            "error",
            "skill_md_missing_task_type_mentions",
            "SKILL.md must mention every generated task_type for Codex routing.",
            "SKILL.md",
        )
    missing_task_dags = [task for task in task_types if not has_task_workflow_dag(text, task)]
    if missing_task_dags:
        add_finding(
            findings,
            "error",
            "skill_md_missing_task_type_dag",
            "SKILL.md must include one Mermaid workflow DAG for every generated task_type.",
            "SKILL.md",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "frontmatter": fields,
        "task_types": task_types,
        "task_type_dag_count": len(task_types) - len(missing_task_dags),
        "top_level_dirs": sorted(top_dirs),
        "nested_skill_files": nested_skill_files,
        "findings": findings,
        "policy": [
            "Child skill metadata must be enough for Codex to trigger the skill and select task_type internally.",
            "One package produces one child skill; task_type entries must not become nested skills or separate routing selectors.",
            "The generated child skill stays lightweight: SKILL.md plus references, with optional agents metadata only.",
        ],
    }
