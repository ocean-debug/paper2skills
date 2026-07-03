"""Audit evidence claim taxonomy and source priority by task_type."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import CLAIM_KEYWORDS, EVIDENCE_PRIORITY, SCHEMA_VERSION


REQUIRED_OPERATIONAL_CLAIMS = {
    "task_support",
    "input_contract",
    "output_contract",
    "api_entrypoint",
    "validation_rule",
    "refusal_boundary",
}
SOURCE_REQUIRED_CLAIMS = {
    "input_contract",
    "output_contract",
    "api_entrypoint",
    "validation_rule",
    "refusal_boundary",
    "environment_requirement",
}
KNOWN_CLAIM_TYPES = set(CLAIM_KEYWORDS) | {"task_support", "execution_verification"}


def priority_rank(priority: str | None) -> int:
    if priority in EVIDENCE_PRIORITY:
        return EVIDENCE_PRIORITY.index(str(priority))
    return len(EVIDENCE_PRIORITY)


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    task_type: str | None = None,
    value: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if task_type:
        item["task_type"] = task_type
    if value:
        item["value"] = value
    findings.append(item)


def source_lookup(source_grounding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(source.get("evidence_id")): source
        for source in source_grounding.get("sources", [])
        if source.get("evidence_id")
    }


def card_lookup(evidence_cards: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(card.get("evidence_card_id")): card
        for card in evidence_cards.get("cards", [])
        if card.get("evidence_card_id")
    }


def source_for_ref(
    evidence_ref: str,
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if evidence_ref in sources:
        return sources[evidence_ref]
    card = cards.get(evidence_ref, {})
    return sources.get(str(card.get("source_evidence_id")), {})


def claim_for_ref(evidence_ref: str, cards: dict[str, dict[str, Any]]) -> str:
    card = cards.get(evidence_ref)
    if card and card.get("claim_type"):
        return str(card["claim_type"])
    return "task_support"


def evidence_item(
    evidence_ref: str,
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = source_for_ref(evidence_ref, cards, sources)
    claim_type = claim_for_ref(evidence_ref, cards)
    priority = str(source.get("priority") or "unknown")
    return {
        "evidence_ref": evidence_ref,
        "claim_type": claim_type,
        "priority": priority,
        "priority_rank": priority_rank(priority),
        "source_type": source.get("type"),
        "source_evidence_id": source.get("evidence_id"),
    }


def task_claim_items(
    task: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    execution_trace_validation: dict[str, Any],
) -> list[dict[str, Any]]:
    task_type = str(task.get("task_type") or "")
    refs = {str(ref) for ref in task.get("evidence_refs", []) if ref}
    for card_id, card in cards.items():
        if task_type in [str(item) for item in card.get("task_type_candidates", [])]:
            refs.add(card_id)
    items = [evidence_item(ref, cards, sources) for ref in sorted(refs)]
    for record in execution_trace_validation.get("records", []):
        if record.get("task_type") != task_type:
            continue
        if not record.get("success") or record.get("missing_fields") or not record.get("known_task_type"):
            continue
        trace_ref = str(record.get("trace_ref") or "")
        if trace_ref:
            items.append(
                {
                    "evidence_ref": trace_ref,
                    "claim_type": "execution_verification",
                    "priority": "execution_trace",
                    "priority_rank": priority_rank("execution_trace"),
                    "source_type": "execution_trace",
                    "source_evidence_id": trace_ref,
                }
            )
    return items


def best_priority_by_claim(items: list[dict[str, Any]]) -> dict[str, str]:
    best: dict[str, dict[str, Any]] = {}
    for item in items:
        claim_type = str(item.get("claim_type") or "task_support")
        current = best.get(claim_type)
        if current is None or int(item.get("priority_rank", 99)) < int(current.get("priority_rank", 99)):
            best[claim_type] = item
    return {
        claim_type: str(item.get("priority") or "unknown")
        for claim_type, item in sorted(best.items())
    }


def task_taxonomy_record(
    task: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence_precedence: dict[str, Any],
    execution_trace_validation: dict[str, Any],
) -> dict[str, Any]:
    task_type = str(task.get("task_type") or "")
    items = task_claim_items(task, cards, sources, execution_trace_validation)
    claim_types = sorted({str(item.get("claim_type")) for item in items if item.get("claim_type")})
    best_by_claim = best_priority_by_claim(items)
    precedence_record = next(
        (record for record in evidence_precedence.get("tasks", []) if record.get("task_type") == task_type),
        {},
    )
    missing_required = sorted(REQUIRED_OPERATIONAL_CLAIMS.difference(claim_types))
    paper_only_operational = sorted(
        claim_type
        for claim_type, priority in best_by_claim.items()
        if claim_type in SOURCE_REQUIRED_CLAIMS and priority == "paper"
    )
    unknown_claim_types = sorted(set(claim_types).difference(KNOWN_CLAIM_TYPES))
    return {
        "task_type": task_type,
        "verification_status": task.get("verification_status"),
        "claim_types": claim_types,
        "missing_required_claim_types": missing_required,
        "best_priority_by_claim": best_by_claim,
        "paper_only_operational_claim_types": paper_only_operational,
        "unknown_claim_types": unknown_claim_types,
        "precedence_status": "present" if precedence_record else "missing",
        "precedence_best_priority": precedence_record.get("best_priority"),
        "precedence_best_operational_priority": precedence_record.get("best_operational_priority"),
    }


def build_evidence_claim_taxonomy_audit(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    evidence_cards: dict[str, Any],
    source_grounding: dict[str, Any],
    evidence_precedence: dict[str, Any],
    execution_trace_validation: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit for claim-type coverage and evidence priority."""
    findings: list[dict[str, Any]] = []
    cards = card_lookup(evidence_cards)
    sources = source_lookup(source_grounding)
    records = [
        task_taxonomy_record(task, cards, sources, evidence_precedence, execution_trace_validation)
        for task in task_catalog.get("tasks", [])
    ]

    for card_id, card in cards.items():
        claim_type = str(card.get("claim_type") or "")
        if claim_type not in KNOWN_CLAIM_TYPES:
            add_finding(findings, "error", "unknown_evidence_card_claim_type", "Evidence card has an unsupported claim_type.", value=card_id)

    for record in records:
        task_type = str(record.get("task_type") or "")
        missing_required = record.get("missing_required_claim_types", [])
        if missing_required:
            add_finding(
                findings,
                "error",
                "missing_required_claim_taxonomy",
                "Task_type is missing required operational claim-type evidence.",
                task_type=task_type,
                value=", ".join(missing_required),
            )
        paper_only = record.get("paper_only_operational_claim_types", [])
        if paper_only:
            add_finding(
                findings,
                "error",
                "paper_only_operational_claim",
                "Operational claims must be grounded in official docs/tutorials, source/API, or execution trace, not only paper evidence.",
                task_type=task_type,
                value=", ".join(paper_only),
            )
        if record.get("precedence_status") != "present":
            add_finding(findings, "error", "missing_evidence_precedence_record", "Task_type has no evidence precedence record.", task_type=task_type)
        if record.get("verification_status") == "execution_verified" and "execution_verification" not in record.get("claim_types", []):
            add_finding(findings, "error", "verified_without_execution_claim_type", "execution_verified task_type requires execution_verification claim evidence.", task_type=task_type)

    has_environment_claim = any(card.get("claim_type") == "environment_requirement" for card in cards.values())
    if request.get("execution_grounded") and not has_environment_claim:
        add_finding(
            findings,
            "error",
            "execution_grounding_without_environment_claim",
            "execution_grounded builds require environment_requirement evidence.",
        )
    elif not has_environment_claim:
        add_finding(
            findings,
            "warning",
            "environment_claim_not_observed",
            "No environment_requirement claim evidence was observed; environment.md must stay conservative.",
        )

    if evidence_precedence.get("status") == "fail":
        add_finding(findings, "error", "evidence_precedence_failed", "Claim taxonomy requires passing evidence precedence.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    all_claim_types = sorted({claim for record in records for claim in record.get("claim_types", [])})
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "task_count": len(records),
        "evidence_card_count": len(cards),
        "required_operational_claim_types": sorted(REQUIRED_OPERATIONAL_CLAIMS),
        "source_required_claim_types": sorted(SOURCE_REQUIRED_CLAIMS),
        "observed_claim_types": all_claim_types,
        "tasks": records,
        "findings": findings,
        "policy": [
            "Each task_type must have evidence for task support, input, output, API, validation, and refusal claims.",
            "Operational claims cannot be supported only by paper evidence.",
            "execution_verified claims require execution_verification evidence from validated traces.",
        ],
    }
