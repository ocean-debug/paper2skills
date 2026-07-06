"""Resolve task evidence by source priority before publish."""

from __future__ import annotations

from typing import Any

from common import canonical_task_type, now_utc
from constants import EVIDENCE_PRIORITY, SCHEMA_VERSION


OPERATIONAL_CLAIMS = {
    "task_support",
    "input_contract",
    "output_contract",
    "api_entrypoint",
    "validation_rule",
    "refusal_boundary",
}


def priority_rank(priority: str | None) -> int:
    if priority in EVIDENCE_PRIORITY:
        return EVIDENCE_PRIORITY.index(str(priority))
    return len(EVIDENCE_PRIORITY)


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
    ref: str,
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if ref in sources:
        return sources[ref]
    card = cards.get(ref)
    if not card:
        return None
    return sources.get(str(card.get("source_evidence_id")))


def claim_type_for_ref(ref: str, cards: dict[str, dict[str, Any]]) -> str:
    card = cards.get(ref)
    if card and card.get("claim_type"):
        return str(card["claim_type"])
    return "task_support"


def evidence_item(
    ref: str,
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = source_for_ref(ref, cards, sources) or {}
    card = cards.get(ref) or {}
    priority = source.get("priority")
    return {
        "evidence_ref": ref,
        "claim_type": claim_type_for_ref(ref, cards),
        "priority": priority or "unknown",
        "priority_rank": priority_rank(str(priority) if priority else None),
        "source_type": source.get("type") or card.get("source_type"),
        "source_evidence_id": source.get("evidence_id") or card.get("source_evidence_id"),
        "official": source.get("official"),
    }


def trace_items_for_task(execution_trace_validation: dict[str, Any], task_type: str) -> list[dict[str, Any]]:
    items = []
    canonical_task = canonical_task_type(task_type, "task")
    for record in execution_trace_validation.get("records", []):
        if canonical_task_type(str(record.get("task_type") or ""), "task") != canonical_task:
            continue
        if not record.get("success") or record.get("missing_fields") or not record.get("known_task_type"):
            continue
        trace_ref = record.get("trace_ref")
        if not trace_ref:
            continue
        items.append(
            {
                "evidence_ref": trace_ref,
                "claim_type": "execution_verification",
                "priority": "execution_trace",
                "priority_rank": priority_rank("execution_trace"),
                "source_type": record.get("evidence_source") or "execution_trace",
                "source_evidence_id": trace_ref,
                "official": False,
            }
        )
    return items


def select_best_by_claim(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for item in items:
        claim_type = str(item.get("claim_type") or "task_support")
        current = best.get(claim_type)
        if current is None or int(item.get("priority_rank", 99)) < int(current.get("priority_rank", 99)):
            best[claim_type] = item
    return best


def task_precedence_record(
    task: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    execution_trace_validation: dict[str, Any],
) -> dict[str, Any]:
    task_type = canonical_task_type(str(task.get("task_type") or ""), "task")
    refs = [str(ref) for ref in task.get("evidence_refs", [])]
    items = [evidence_item(ref, cards, sources) for ref in refs]
    items.extend(trace_items_for_task(execution_trace_validation, task_type))
    best_by_claim = select_best_by_claim(items)
    best_priority = min((int(item.get("priority_rank", 99)) for item in items), default=99)
    operational_items = [
        item
        for item in items
        if str(item.get("claim_type")) in OPERATIONAL_CLAIMS
    ]
    best_operational_rank = min(
        (int(item.get("priority_rank", 99)) for item in operational_items),
        default=99,
    )
    accepted_refs = sorted({str(item.get("evidence_ref")) for item in best_by_claim.values() if item.get("evidence_ref")})
    background_refs = sorted(
        {
            str(item.get("evidence_ref"))
            for item in items
            if item.get("evidence_ref") and str(item.get("evidence_ref")) not in accepted_refs
        }
    )
    return {
        "task_type": task_type,
        "verification_status": task.get("verification_status"),
        "best_priority": EVIDENCE_PRIORITY[best_priority] if best_priority < len(EVIDENCE_PRIORITY) else "unknown",
        "best_operational_priority": EVIDENCE_PRIORITY[best_operational_rank] if best_operational_rank < len(EVIDENCE_PRIORITY) else "unknown",
        "accepted_refs": accepted_refs,
        "background_refs": background_refs,
        "claim_precedence": [
            {
                "claim_type": claim_type,
                "selected_ref": item.get("evidence_ref"),
                "selected_priority": item.get("priority"),
                "source_type": item.get("source_type"),
            }
            for claim_type, item in sorted(best_by_claim.items())
        ],
        "evidence_items": sorted(
            items,
            key=lambda item: (int(item.get("priority_rank", 99)), str(item.get("claim_type")), str(item.get("evidence_ref"))),
        ),
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


def build_evidence_precedence(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    evidence_cards: dict[str, Any],
    source_grounding: dict[str, Any],
    execution_trace_validation: dict[str, Any],
) -> dict[str, Any]:
    cards = card_lookup(evidence_cards)
    sources = source_lookup(source_grounding)
    tasks = [
        task_precedence_record(task, cards, sources, execution_trace_validation)
        for task in task_catalog.get("tasks", [])
    ]
    findings: list[dict[str, Any]] = []
    for task in tasks:
        task_type = str(task.get("task_type"))
        if not task.get("accepted_refs"):
            add_finding(
                findings,
                "error",
                "task_without_accepted_evidence",
                "Task_type has no accepted evidence after precedence resolution.",
                task_type,
            )
        if task.get("verification_status") == "execution_verified" and task.get("best_priority") != "execution_trace":
            add_finding(
                findings,
                "error",
                "verified_task_without_trace_precedence",
                "Task_type is execution_verified but execution_trace is not the highest available evidence.",
                task_type,
            )
        if task.get("best_operational_priority") == "paper":
            add_finding(
                findings,
                "warning",
                "operational_claim_paper_only",
                "Operational task guidance is supported only by paper-level evidence; prefer tutorial/docs/API before publish.",
                task_type,
            )
        if task.get("best_operational_priority") == "unknown":
            add_finding(
                findings,
                "warning",
                "operational_claim_unknown_priority",
                "Operational task guidance has no recognized evidence priority.",
                task_type,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "evidence_priority": EVIDENCE_PRIORITY,
        "task_count": len(tasks),
        "tasks": tasks,
        "findings": findings,
        "policy": [
            "Accepted operational evidence follows execution trace, official tutorials/docs, source/API, then paper.",
            "Paper-only operational guidance is allowed only as a warning for source-grounded drafts.",
            "Execution-verified task_type entries require successful trace precedence.",
        ],
    }
