"""Task-level evidence coverage report."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_CLAIM_TYPES = {
    "task_support",
    "input_contract",
    "output_contract",
    "api_entrypoint",
    "validation_rule",
    "refusal_boundary",
}


def card_lookup(evidence_cards: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(card.get("evidence_card_id")): card
        for card in evidence_cards.get("cards", [])
        if card.get("evidence_card_id")
    }


def source_lookup(source_grounding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(source.get("evidence_id")): source
        for source in source_grounding.get("sources", [])
        if source.get("evidence_id")
    }


def source_priority_for_ref(ref: str, cards: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> str | None:
    if ref in sources:
        return sources[ref].get("priority")
    card = cards.get(ref)
    if not card:
        return None
    source = sources.get(str(card.get("source_evidence_id")))
    return source.get("priority") if source else None


def claim_type_for_ref(ref: str, cards: dict[str, dict[str, Any]]) -> str | None:
    card = cards.get(ref)
    return str(card.get("claim_type")) if card and card.get("claim_type") else None


def task_evidence_record(
    task: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    refs = [str(ref) for ref in task.get("evidence_refs", [])]
    priorities = sorted({priority for ref in refs for priority in [source_priority_for_ref(ref, cards, sources)] if priority})
    claim_types = sorted({claim for ref in refs for claim in [claim_type_for_ref(ref, cards)] if claim})
    missing_claim_types = sorted(REQUIRED_CLAIM_TYPES.difference(claim_types))
    has_official_tutorial_or_docs = "official_tutorial_or_docs" in priorities
    has_source_code_or_api = "source_code_or_api" in priorities
    has_execution_trace = "execution_trace" in priorities or task.get("verification_status") == "execution_verified"
    status = "pass"
    if not refs:
        status = "fail"
    elif task.get("verification_status") == "execution_verified" and not has_execution_trace:
        status = "fail"
    elif not has_official_tutorial_or_docs and not has_source_code_or_api:
        status = "warning"
    elif missing_claim_types:
        status = "warning"
    return {
        "task_type": task.get("task_type"),
        "status": status,
        "verification_status": task.get("verification_status"),
        "evidence_ref_count": len(refs),
        "evidence_refs": refs,
        "priority_coverage": priorities,
        "claim_type_coverage": claim_types,
        "missing_claim_types": missing_claim_types,
        "has_execution_trace": has_execution_trace,
        "has_official_tutorial_or_docs": has_official_tutorial_or_docs,
        "has_source_code_or_api": has_source_code_or_api,
    }


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


def build_evidence_coverage(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    evidence_cards: dict[str, Any],
    source_grounding: dict[str, Any],
) -> dict[str, Any]:
    cards = card_lookup(evidence_cards)
    sources = source_lookup(source_grounding)
    records = [
        task_evidence_record(task, cards, sources)
        for task in task_catalog.get("tasks", [])
    ]
    findings: list[dict[str, Any]] = []
    for record in records:
        task_type = str(record.get("task_type"))
        if record["status"] == "fail":
            add_finding(
                findings,
                "error",
                "task_evidence_coverage_failed",
                "Task evidence coverage is missing or inconsistent with verification status.",
                task_type,
            )
        elif record["status"] == "warning":
            add_finding(
                findings,
                "warning",
                "task_evidence_coverage_weak",
                "Task has evidence refs, but priority or claim-type coverage is incomplete.",
                task_type,
            )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "task_count": len(records),
        "tasks": records,
        "findings": findings,
        "policy": [
            "Evidence coverage summarizes task_type support by source priority and claim type.",
            "Warnings indicate source-grounded but incomplete coverage; errors block missing evidence or verified claims without execution trace coverage.",
        ],
    }
