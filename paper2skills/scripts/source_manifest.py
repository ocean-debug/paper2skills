"""Source manifest and provenance summary for build artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def build_source_manifest(
    request: dict[str, Any],
    source_grounding: dict[str, Any],
    source_fetch_report: dict[str, Any],
    source_index: dict[str, Any],
    evidence_cards: dict[str, Any],
) -> dict[str, Any]:
    fetch_lookup = {source.get("evidence_id"): source for source in source_fetch_report.get("sources", [])}
    files_by_source: dict[str, list[dict[str, Any]]] = {}
    for record in source_index.get("files", []):
        files_by_source.setdefault(str(record.get("evidence_id")), []).append(record)
    cards_by_source: dict[str, list[dict[str, Any]]] = {}
    for card in evidence_cards.get("cards", []):
        cards_by_source.setdefault(str(card.get("source_evidence_id")), []).append(card)

    sources = []
    for source in source_grounding.get("sources", []):
        evidence_id = source.get("evidence_id")
        fetch = fetch_lookup.get(evidence_id, {})
        indexed = files_by_source.get(str(evidence_id), [])
        cards = cards_by_source.get(str(evidence_id), [])
        sources.append(
            {
                "evidence_id": evidence_id,
                "type": source.get("type"),
                "priority": source.get("priority"),
                "official": source.get("official", False),
                "uri": source.get("uri"),
                "fetch_status": fetch.get("status"),
                "resolved_uri": fetch.get("resolved_uri"),
                "local_path": fetch.get("local_path") or fetch.get("extract_path"),
                "sha256": fetch.get("sha256"),
                "indexed_file_count": len(indexed),
                "evidence_card_count": len(cards),
                "indexed_kinds": sorted({str(record.get("kind")) for record in indexed if record.get("kind")}),
                "claim_types": sorted({str(card.get("claim_type")) for card in cards if card.get("claim_type")}),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "source_count": len(sources),
        "indexed_file_count": source_index.get("file_count", 0),
        "evidence_card_count": evidence_cards.get("card_count", 0),
        "sources": sources,
        "policy": "Store source metadata and hashes only; do not publish long excerpts or full logs.",
    }
