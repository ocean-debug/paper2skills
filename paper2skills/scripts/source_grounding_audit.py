"""Audit source grounding from source records through rendered child skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import EVIDENCE_PRIORITY, SCHEMA_VERSION


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


def markdown_texts(skill_dir: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.is_file():
            texts[str(path.relative_to(skill_dir)).replace("\\", "/")] = read_text(path)
    return texts


def task_evidence_refs(task: dict[str, Any], contract_traceability: dict[str, Any]) -> set[str]:
    refs = {str(ref) for ref in task.get("evidence_refs", []) if ref}
    task_type = str(task.get("task_type") or "")
    for record in contract_traceability.get("records", []):
        if str(record.get("task_type") or "") != task_type:
            continue
        for ref in record.get("evidence_refs", []):
            if ref:
                refs.add(str(ref))
    return refs


def source_ids(source_grounding: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for source in source_grounding.get("sources", []):
        evidence_id = source.get("evidence_id")
        if evidence_id:
            ids.add(str(evidence_id))
    return ids


def card_ids(evidence_cards: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for card in evidence_cards.get("cards", []):
        card_id = card.get("evidence_card_id")
        if card_id:
            ids.add(str(card_id))
    return ids


def audit_source_grounding(
    request: dict[str, Any],
    source_grounding: dict[str, Any],
    source_parse_report: dict[str, Any],
    source_parsing_coverage: dict[str, Any],
    source_parsing_audit: dict[str, Any],
    evidence_cards: dict[str, Any],
    evidence_precedence: dict[str, Any],
    task_catalog: dict[str, Any],
    contract_traceability: dict[str, Any],
    skill_dir: Path,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    texts = markdown_texts(skill_dir)
    combined_text = "\n".join(texts.values())

    priority = source_grounding.get("evidence_priority", [])
    if priority != EVIDENCE_PRIORITY:
        add_finding(
            findings,
            "error",
            "evidence_priority_mismatch",
            "Source grounding must preserve the expected evidence priority order.",
        )

    if not source_grounding.get("sources"):
        add_finding(findings, "error", "missing_source_catalog", "Source grounding has no source entries.")

    strategy = source_parse_report.get("strategy") or {}
    execution_policy = str(strategy.get("execution_policy") or "").lower()
    if "never" not in execution_policy and "does not" not in execution_policy:
        add_finding(
            findings,
            "error",
            "implicit_source_parsing_execution_boundary",
            "Source parse report must explicitly state that parsing does not execute package code.",
        )

    if source_parsing_coverage.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_coverage_failed", "Source parsing coverage failed.")
    if source_parsing_audit.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_audit_failed", "Source parsing audit failed.")
    if evidence_precedence.get("status") == "fail":
        add_finding(findings, "error", "evidence_precedence_failed", "Evidence precedence failed.")
    if contract_traceability.get("status") == "fail":
        add_finding(findings, "error", "contract_traceability_failed", "Contract traceability failed.")

    known_refs = card_ids(evidence_cards) | source_ids(source_grounding)
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type") or "")
        refs = task_evidence_refs(task, contract_traceability)
        if not refs:
            add_finding(
                findings,
                "error",
                "task_without_grounding_refs",
                "Task_type has no source or evidence-card references.",
                task_type,
            )
        unknown_refs = sorted(ref for ref in refs if ref not in known_refs)
        if unknown_refs:
            add_finding(
                findings,
                "error",
                "task_unknown_grounding_ref",
                "Task_type references evidence ids that are not in source grounding or evidence cards.",
                task_type,
            )
        if task_type and task_type not in combined_text:
            add_finding(
                findings,
                "error",
                "task_grounding_not_rendered",
                "Task_type grounding is not rendered into the child skill Markdown.",
                task_type,
            )

    required_rendered_markers = [
        "evidence priority",
        "source parsing coverage",
        "evidence precedence by task",
    ]
    evidence_text = texts.get("references/evidence.md", "")
    evidence_text_lower = evidence_text.lower()
    for marker in required_rendered_markers:
        if marker not in evidence_text_lower:
            add_finding(
                findings,
                "error",
                "grounding_marker_not_rendered",
                "Generated evidence.md is missing a required grounding section.",
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "source_count": len(source_grounding.get("sources", [])),
        "evidence_card_count": evidence_cards.get("card_count", 0),
        "task_count": len(task_catalog.get("tasks", [])),
        "rendered_markdown_count": len(texts),
        "evidence_priority": priority,
        "required_evidence_priority": EVIDENCE_PRIORITY,
        "source_parsing_coverage_status": source_parsing_coverage.get("status"),
        "source_parsing_audit_status": source_parsing_audit.get("status"),
        "evidence_precedence_status": evidence_precedence.get("status"),
        "contract_traceability_status": contract_traceability.get("status"),
        "findings": findings,
        "policy": [
            "Source grounding is source-first and traceable from source catalog to task_type contracts.",
            "Static source parsing never executes package code and cannot mark a task_type verified.",
            "Rendered child references must expose evidence priority, source parsing coverage, and task-level precedence.",
        ],
    }
