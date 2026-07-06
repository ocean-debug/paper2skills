"""Convert indexed source records into evidence cards and claim hints."""

from __future__ import annotations

from typing import Any

from common import lower_join, now_utc, slugify
from constants import CLAIM_KEYWORDS, SCHEMA_VERSION, TASK_HEURISTICS


def candidate_task_types(text: str) -> list[str]:
    lowered = text.lower()
    tasks = []
    for task_type, needles in TASK_HEURISTICS.items():
        if any(needle.lower() in lowered for needle in needles):
            tasks.append(task_type)
    return tasks or ["general_algorithm_use"]


def candidate_claim_types(text: str, kind: str, has_api_surface: bool) -> list[str]:
    lowered = text.lower()
    claims = []
    for claim_type, needles in CLAIM_KEYWORDS.items():
        if any(needle.lower() in lowered for needle in needles):
            claims.append(claim_type)
    if kind in {"python", "notebook"} and has_api_surface and "api_entrypoint" not in claims:
        claims.append("api_entrypoint")
    return claims or ["task_support"]


def summarize_file_record(record: dict[str, Any]) -> str:
    pieces = []
    kind = record.get("kind")
    rel = record.get("relative_path")
    pieces.append(f"{kind} source {rel}")
    if record.get("headings"):
        pieces.append("headings: " + "; ".join(record["headings"][:4]))
    if record.get("functions"):
        pieces.append("functions: " + ", ".join(record["functions"][:8]))
    if record.get("classes"):
        pieces.append("classes: " + ", ".join(record["classes"][:8]))
    if record.get("imports"):
        pieces.append("imports: " + ", ".join(record["imports"][:8]))
    if record.get("api_calls"):
        pieces.append("api calls: " + ", ".join(record["api_calls"][:8]))
    return " | ".join(pieces)[:600]


def build_evidence_cards(
    request: dict[str, Any],
    source_index: dict[str, Any],
    source_grounding: dict[str, Any],
) -> dict[str, Any]:
    cards = []
    source_lookup = {source["evidence_id"]: source for source in source_grounding.get("sources", [])}
    for index, record in enumerate(source_index.get("files", []), start=1):
        if record.get("status") != "indexed":
            continue
        text = lower_join(
            [
                record.get("relative_path"),
                record.get("kind"),
                " ".join(record.get("terms", [])[:100]),
                " ".join(record.get("headings", [])[:20]),
                " ".join(record.get("functions", [])[:50]),
                " ".join(record.get("classes", [])[:50]),
                " ".join(record.get("imports", [])[:50]),
                " ".join(record.get("api_calls", [])[:80]),
            ]
        )
        task_types = candidate_task_types(text)
        has_api_surface = bool(record.get("functions") or record.get("classes") or record.get("api_calls"))
        claim_types = candidate_claim_types(text, str(record.get("kind")), has_api_surface)
        source = source_lookup.get(record.get("evidence_id"), {})
        for claim_type in claim_types:
            cards.append(
                {
                    "evidence_card_id": f"evidence:card:{index:04d}:{slugify(claim_type)}",
                    "source_evidence_id": record.get("evidence_id"),
                    "source_type": source.get("type"),
                    "source_path": record.get("relative_path"),
                    "claim_type": claim_type,
                    "task_type_candidates": task_types,
                    "summary": summarize_file_record(record),
                    "confidence": "documented" if source.get("type") in {"official_tutorial", "official_docs"} else "source_observed",
                    "claim_support": {
                        "has_api_surface": has_api_surface,
                        "function_count": len(record.get("functions", [])),
                        "class_count": len(record.get("classes", [])),
                        "api_call_count": len(record.get("api_calls", [])),
                        "heading_count": len(record.get("headings", [])),
                    },
                    "provenance": {
                        "path": record.get("path"),
                        "sha256": record.get("sha256"),
                    },
                }
            )
    if not cards:
        for source in source_grounding.get("sources", []):
            cards.append(
                {
                    "evidence_card_id": f"evidence:card:source:{slugify(source.get('evidence_id'))}",
                    "source_evidence_id": source.get("evidence_id"),
                    "source_type": source.get("type"),
                    "source_path": None,
                    "claim_type": "task_support",
                    "task_type_candidates": candidate_task_types(str(source.get("uri", ""))),
                    "summary": f"Official source URI recorded for {request.get('package_name')}: {source.get('uri')}",
                    "confidence": "uri_recorded",
                    "provenance": {"uri": source.get("uri")},
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "card_count": len(cards),
        "cards": cards,
        "notes": [
            "Evidence cards are concise claim hints, not long source excerpts.",
            "Cards should be reviewed before becoming hard refusal or validation rules.",
        ],
    }
