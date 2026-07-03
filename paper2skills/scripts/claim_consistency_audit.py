"""Audit rendered child-skill claims against build artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


TASK_TOKEN_RE = re.compile(r"`([a-z][a-z0-9]+(?:_[a-z0-9]+)+)`")
EVIDENCE_TOKEN_RE = re.compile(r"\b(?:evidence:card:[A-Za-z0-9:_-]+|repo:main|tutorial:\d{2}|docs:\d{2}|paper:\d{2}|local:\d{2})\b")
STATUS_TOKENS = {"source_grounded", "execution_verified", "execution_failed", "unsupported"}


def markdown_texts(skill_dir: Path) -> dict[str, str]:
    texts = {}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.is_file():
            texts[str(path.relative_to(skill_dir)).replace("\\", "/")] = read_text(path)
    return texts


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    task_type: str | None = None,
    value: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    if task_type:
        item["task_type"] = task_type
    if value:
        item["value"] = value
    findings.append(item)


def known_evidence_refs(
    source_grounding: dict[str, Any],
    evidence_cards: dict[str, Any],
    task_catalog: dict[str, Any],
) -> set[str]:
    refs = {
        str(source.get("evidence_id"))
        for source in source_grounding.get("sources", [])
        if source.get("evidence_id")
    }
    refs.update(
        str(card.get("evidence_card_id"))
        for card in evidence_cards.get("cards", [])
        if card.get("evidence_card_id")
    )
    for task in task_catalog.get("tasks", []):
        refs.update(str(ref) for ref in task.get("evidence_refs", []) if ref)
        if task.get("trace_ref"):
            refs.add(str(task["trace_ref"]))
    return refs


def required_task_paths() -> list[str]:
    return [
        "SKILL.md",
        "references/task-types.md",
        "references/input-output-contracts.md",
        "references/validation.md",
        "references/evidence.md",
    ]


def audit_claim_consistency(
    skill_dir: Path,
    task_catalog: dict[str, Any],
    source_grounding: dict[str, Any],
    evidence_cards: dict[str, Any],
    backend_contract: dict[str, Any],
    evidence_precedence: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    texts = markdown_texts(skill_dir)
    all_text = "\n".join(texts.values())
    tasks = task_catalog.get("tasks", [])
    allowed_task_types = {str(task.get("task_type")) for task in tasks if task.get("task_type")}
    status_by_task = {
        str(task.get("task_type")): str(task.get("verification_status"))
        for task in tasks
        if task.get("task_type")
    }
    allowed_statuses = {status for status in status_by_task.values() if status}
    known_refs = known_evidence_refs(source_grounding, evidence_cards, task_catalog)

    if not texts:
        add_finding(findings, "error", "no_markdown_files", "Generated child skill has no Markdown files.")

    for task_type in sorted(allowed_task_types):
        for rel in required_task_paths():
            text = texts.get(rel, "")
            if task_type not in text:
                add_finding(
                    findings,
                    "error",
                    "task_missing_from_required_reference",
                    "Task_type is missing from a required child-skill file.",
                    path=rel,
                    task_type=task_type,
                )
        expected_status = status_by_task.get(task_type)
        if expected_status and expected_status not in all_text:
            add_finding(
                findings,
                "error",
                "verification_status_missing",
                "Task verification status is not rendered in the child skill.",
                task_type=task_type,
                value=expected_status,
            )

    for rel, text in texts.items():
        for token in sorted(set(TASK_TOKEN_RE.findall(text))):
            if token not in allowed_task_types:
                add_finding(
                    findings,
                    "warning",
                    "unknown_task_type_token",
                    "Rendered child skill contains a backticked task_type-like token that is not in task_catalog.",
                    path=rel,
                    value=token,
                )
        for status in STATUS_TOKENS:
            if status in text and status not in allowed_statuses and status not in {"source_grounded"}:
                add_finding(
                    findings,
                    "warning",
                    "unsupported_verification_status_rendered",
                    "Rendered child skill mentions a verification label not present in this task_catalog; this is allowed only as explanatory policy text.",
                    path=rel,
                    value=status,
                )
        for ref in sorted(set(EVIDENCE_TOKEN_RE.findall(text))):
            if ref not in known_refs:
                add_finding(
                    findings,
                    "error",
                    "unknown_evidence_ref_rendered",
                    "Rendered child skill references evidence not present in source/evidence/task artifacts.",
                    path=rel,
                    value=ref,
                )

    for task in tasks:
        task_type = str(task.get("task_type"))
        for boundary in task.get("refusal_boundaries", []):
            reason_key = str(boundary.get("reason_key") or "")
            if reason_key and reason_key not in texts.get("references/limitations-and-refusal.md", ""):
                add_finding(
                    findings,
                    "error",
                    "refusal_reason_missing",
                    "Task refusal reason is not rendered in limitations-and-refusal.md.",
                    path="references/limitations-and-refusal.md",
                    task_type=task_type,
                    value=reason_key,
                )

    if backend_contract.get("status") != "supported":
        expected_reason = str(backend_contract.get("refusal_boundary", {}).get("reason_key") or "backend_not_implemented")
        if expected_reason not in all_text:
            add_finding(
                findings,
                "error",
                "backend_refusal_missing",
                "Unsupported backend does not render the required refusal boundary.",
                value=expected_reason,
            )

    if evidence_precedence.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "upstream_evidence_precedence_failed",
            "Evidence precedence failed; rendered claims cannot be treated as publishable.",
        )

    missing_references = [
        f"references/{name}"
        for name in REQUIRED_CHILD_REFERENCES
        if f"references/{name}" not in texts
    ]
    for rel in missing_references:
        add_finding(
            findings,
            "error",
            "missing_reference_file",
            "Required reference file is missing from rendered child skill.",
            path=rel,
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "checked_file_count": len(texts),
        "task_count": len(allowed_task_types),
        "allowed_task_types": sorted(allowed_task_types),
        "allowed_statuses": sorted(allowed_statuses),
        "findings": findings,
        "policy": "Rendered child-skill claims must match task, evidence, refusal, backend, and verification artifacts.",
    }
