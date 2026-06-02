from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    source_path: str
    locator: str
    text: str
    confidence_hint: str = "medium"


@dataclass
class EvidenceClaim:
    claim_id: str
    field: str
    value: Any
    confidence: str
    evidence_ids: list[str]
    notes: str | None = None


def build_evidence_graph(
    *,
    paper_evidence: dict[str, Any] | None = None,
    tutorial_trace: dict[str, Any] | None = None,
    dependency_evidence: dict[str, Any] | None = None,
    bio_contract: dict[str, Any] | None = None,
    algorithm_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[EvidenceItem] = []
    claims: list[EvidenceClaim] = []
    for section in ((paper_evidence or {}).get("parsed_document") or {}).get("sections", []) or []:
        items.append(EvidenceItem(section["section_id"], "paper", section.get("source_path", ""), f"lines:{section.get('start_line')}-{section.get('end_line')}", section.get("text", ""), "medium"))
    for tutorial in (tutorial_trace or {}).get("tutorials", []) or []:
        for step in tutorial.get("steps", tutorial.get("workflow_steps", [])):
            items.append(EvidenceItem(step.get("evidence_id") or step.get("step_id"), "tutorial", tutorial.get("path", ""), step.get("source", ""), step.get("command_or_code") or step.get("code_preview", ""), step.get("confidence", "high")))
    for file_path in (dependency_evidence or {}).get("dependency_files", []):
        evidence_id = f"dependency:{file_path}"
        items.append(EvidenceItem(evidence_id, "dependency", file_path, "file", file_path, "medium"))
    collect_claims("bio_contract", bio_contract or {}, claims)
    collect_claims("algorithm_contract", algorithm_contract or {}, claims)
    return {"items": [asdict(item) for item in items], "claims": [asdict(claim) for claim in claims], "conflicts": detect_conflicts(claims)}


def collect_claims(prefix: str, value: Any, claims: list[EvidenceClaim], path: str = "") -> None:
    if isinstance(value, dict) and {"value", "confidence", "evidence"} <= value.keys():
        claim_id = f"{prefix}:{path or 'root'}"
        evidence = value.get("evidence") or []
        claims.append(EvidenceClaim(claim_id, path or prefix, value.get("value"), value.get("confidence", "low"), evidence))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            collect_claims(prefix, item, claims, f"{path}.{key}" if path else key)


def detect_conflicts(claims: list[EvidenceClaim]) -> list[dict[str, Any]]:
    by_field: dict[str, dict[str, list[str]]] = {}
    for claim in claims:
        if claim.value in {None, "not_confirmed"}:
            continue
        by_field.setdefault(claim.field, {}).setdefault(str(claim.value), []).extend(claim.evidence_ids)
    return [
        {"field": field, "conflict": True, "values": sorted(values), "evidence_ids": sorted({e for ids in values.values() for e in ids})}
        for field, values in by_field.items()
        if len(values) > 1
    ]
