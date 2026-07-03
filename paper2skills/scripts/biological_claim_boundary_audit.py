"""Audit high-risk biological claims in rendered child skills against evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import lower_join, now_utc, read_text
from constants import SCHEMA_VERSION


SOURCE_MODALITY_TERMS = [
    "image",
    "images",
    "pixel",
    "pixels",
    "histology",
    "morphology",
    "h&e",
    "he stained",
    "slide",
    "wsi",
]

TARGET_CLAIM_TERMS = [
    "gene expression",
    "transcriptomic",
    "transcriptomics",
    "molecular",
    "pathway",
    "pathways",
    "mutation",
    "mutations",
    "protein abundance",
    "ligand",
    "receptor",
    "survival",
    "prognosis",
    "diagnosis",
    "clinical outcome",
]

ASSERTIVE_CONNECTORS = [
    "predict",
    "infer",
    "estimate",
    "derive",
    "recover",
    "produce",
    "generate",
    "call",
    "classify",
]

REQUIRED_REFUSAL_KEYS = {
    "unsupported_modality_or_format",
    "unsupported_task_type",
}


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


def sentences(text: str) -> list[str]:
    rough = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [item.strip() for item in rough if item.strip()]


def contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def risky_claim_sentences(text: str) -> list[str]:
    risky: list[str] = []
    for sentence in sentences(text):
        lowered = sentence.lower()
        if (
            contains_any(lowered, SOURCE_MODALITY_TERMS)
            and contains_any(lowered, TARGET_CLAIM_TERMS)
            and contains_any(lowered, ASSERTIVE_CONNECTORS)
            and "without" not in lowered
            and "do not" not in lowered
            and "refuse" not in lowered
        ):
            risky.append(sentence[:240])
    return risky


def evidence_support_text(
    task_catalog: dict[str, Any],
    source_grounding: dict[str, Any],
    evidence_cards: dict[str, Any],
) -> str:
    task_bits: list[Any] = []
    for task in task_catalog.get("tasks", []):
        task_bits.extend(
            [
                task.get("task_type"),
                task.get("capability_name"),
                task.get("routing_cues"),
                task.get("evidence_refs"),
            ]
        )
        task_bits.append((task.get("input_contract") or {}).get("notes"))
        task_bits.append((task.get("output_contract") or {}).get("notes"))
    source_bits = [source.get("uri") for source in source_grounding.get("sources", [])]
    card_bits: list[Any] = []
    for card in evidence_cards.get("cards", []):
        card_bits.extend([card.get("summary"), card.get("task_type_candidates"), card.get("claim_type")])
    return lower_join(task_bits + source_bits + card_bits)


def has_cross_modal_evidence(support_text: str) -> bool:
    return (
        contains_any(support_text, SOURCE_MODALITY_TERMS)
        and contains_any(support_text, TARGET_CLAIM_TERMS)
    )


def build_biological_claim_boundary_audit(
    skill_dir: Path,
    task_catalog: dict[str, Any],
    source_grounding: dict[str, Any],
    evidence_cards: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit for unsupported high-risk biological claims."""
    findings: list[dict[str, Any]] = []
    texts = markdown_texts(skill_dir)
    support_text = evidence_support_text(task_catalog, source_grounding, evidence_cards)
    supported = has_cross_modal_evidence(support_text)

    risky_records: list[dict[str, str]] = []
    for path, text in texts.items():
        for sentence in risky_claim_sentences(text):
            risky_records.append({"path": path, "sentence": sentence})
            if not supported:
                add_finding(
                    findings,
                    "error",
                    "unsupported_cross_modal_biological_claim",
                    "Rendered child skill makes a high-risk cross-modal biological claim without matching task or evidence support.",
                    path=path,
                    value=sentence,
                )

    refusal_reasons = {
        str(boundary.get("reason_key"))
        for task in task_catalog.get("tasks", [])
        for boundary in task.get("refusal_boundaries", [])
        if boundary.get("reason_key")
    }
    missing_refusals = sorted(REQUIRED_REFUSAL_KEYS - refusal_reasons)
    for reason in missing_refusals:
        add_finding(
            findings,
            "error",
            "missing_biological_claim_refusal_boundary",
            "Task catalog must include refusal boundaries for unsupported task types and unsupported modalities or formats.",
            value=reason,
        )

    limitations_text = texts.get("references/limitations-and-refusal.md", "")
    for reason in sorted(REQUIRED_REFUSAL_KEYS):
        if reason not in limitations_text:
            add_finding(
                findings,
                "error",
                "biological_claim_refusal_not_rendered",
                "Required biological-claim refusal boundary is not rendered in limitations-and-refusal.md.",
                path="references/limitations-and-refusal.md",
                value=reason,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "checked_file_count": len(texts),
        "risky_claim_count": len(risky_records),
        "cross_modal_evidence_supported": supported,
        "risky_claims": risky_records,
        "required_refusal_keys": sorted(REQUIRED_REFUSAL_KEYS),
        "missing_refusal_keys": missing_refusals,
        "findings": findings,
        "policy": [
            "High-risk biological claims that bridge source modality and molecular, pathway, or clinical targets require matching task/evidence support.",
            "Unsupported task and unsupported modality/format refusal boundaries must be present and rendered.",
            "This audit is static and does not execute package code or judge biological truth beyond rendered claim/evidence alignment.",
        ],
    }
