"""Derive compact API-grounding candidates from parsed source records."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def cards_by_record(evidence_cards: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for card in evidence_cards.get("cards", []):
        key = (str(card.get("source_evidence_id")), str(card.get("source_path")))
        grouped.setdefault(key, []).append(card)
    return grouped


def candidate_tasks(cards: list[dict[str, Any]]) -> list[str]:
    tasks: list[str] = []
    for card in cards:
        for task_type in card.get("task_type_candidates", []):
            if task_type not in tasks:
                tasks.append(task_type)
    return tasks or ["general_algorithm_use"]


def candidate_evidence_refs(cards: list[dict[str, Any]]) -> list[str]:
    refs = []
    for card in cards:
        if card.get("claim_type") == "api_entrypoint" and card.get("evidence_card_id"):
            refs.append(str(card["evidence_card_id"]))
    if not refs:
        refs = [str(card["evidence_card_id"]) for card in cards if card.get("evidence_card_id")]
    return refs[:8]


def confidence_for(cards: list[dict[str, Any]]) -> str:
    confidences = {str(card.get("confidence")) for card in cards}
    if "documented" in confidences:
        return "documented"
    if "source_observed" in confidences:
        return "source_observed"
    if confidences:
        return sorted(confidences)[0]
    return "parsed_symbol"


def add_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    symbol: str,
    kind: str,
    record: dict[str, Any],
    cards: list[dict[str, Any]],
) -> None:
    symbol = symbol.strip()
    if not symbol:
        return
    key = (symbol, kind, str(record.get("relative_path")))
    if key in seen:
        return
    seen.add(key)
    candidate_id = f"api:{slugify(kind)}:{slugify(symbol)}:{len(candidates) + 1:04d}"
    candidates.append(
        {
            "api_candidate_id": candidate_id,
            "symbol": symbol,
            "kind": kind,
            "source_evidence_id": record.get("evidence_id"),
            "source_path": record.get("relative_path"),
            "task_type_candidates": candidate_tasks(cards),
            "evidence_refs": candidate_evidence_refs(cards),
            "confidence": confidence_for(cards),
        }
    )


def build_api_grounding(
    request: dict[str, Any],
    source_index: dict[str, Any],
    evidence_cards: dict[str, Any],
) -> dict[str, Any]:
    grouped_cards = cards_by_record(evidence_cards)
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for record in source_index.get("files", []):
        if record.get("status") != "indexed":
            continue
        cards = grouped_cards.get((str(record.get("evidence_id")), str(record.get("relative_path"))), [])
        for symbol in record.get("classes", [])[:80]:
            add_candidate(candidates, seen, str(symbol), "class", record, cards)
        for symbol in record.get("functions", [])[:80]:
            add_candidate(candidates, seen, str(symbol), "function", record, cards)
        for symbol in record.get("api_calls", [])[:120]:
            add_candidate(candidates, seen, str(symbol), "api_call", record, cards)
        for symbol in record.get("imports", [])[:80]:
            add_candidate(candidates, seen, str(symbol), "import", record, cards)

    by_task_type: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for task_type in candidate.get("task_type_candidates", []):
            bucket = by_task_type.setdefault(task_type, {"api_candidates": [], "evidence_refs": []})
            bucket["api_candidates"].append(candidate["api_candidate_id"])
            for ref in candidate.get("evidence_refs", []):
                if ref not in bucket["evidence_refs"]:
                    bucket["evidence_refs"].append(ref)

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "api_candidate_count": len(candidates),
        "api_candidates": candidates,
        "by_task_type": by_task_type,
        "notes": [
            "API grounding is derived from parsed source records and concise evidence cards.",
            "API candidates are hints for review, not proof that a workflow was executed.",
        ],
    }
