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
    section_role: str = "unknown"
    weight: float = 1.0


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
        role = section_role(section.get("section_id", ""), section.get("title", ""))
        items.append(
            EvidenceItem(
                section["section_id"],
                f"paper_{role}" if role != "unknown" else "paper",
                section.get("source_path", ""),
                f"lines:{section.get('start_line')}-{section.get('end_line')}",
                section.get("text", ""),
                "medium" if role in {"methods", "data", "code"} else "low",
                role,
                source_weight(f"paper_{role}"),
            )
        )
    for tutorial in (tutorial_trace or {}).get("tutorials", []) or []:
        for step in tutorial.get("steps", tutorial.get("workflow_steps", [])):
            items.append(EvidenceItem(step.get("evidence_id") or step.get("step_id"), "tutorial", tutorial.get("path", ""), step.get("source", ""), step.get("command_or_code") or step.get("code_preview", ""), step.get("confidence", "high"), "code", source_weight("tutorial")))
    for file_path in (dependency_evidence or {}).get("dependency_files", []):
        evidence_id = f"dependency:{file_path}"
        items.append(EvidenceItem(evidence_id, "dependency", file_path, "file", file_path, "medium", "dependency", source_weight("dependency")))
    collect_claims("bio_contract", bio_contract or {}, claims)
    collect_claims("algorithm_contract", algorithm_contract or {}, claims)
    conflicts = detect_conflicts(claims)
    decisions = build_decisions(claims, items, conflicts)
    return {"items": [asdict(item) for item in items], "claims": [asdict(claim) for claim in claims], "conflicts": conflicts, "decisions": decisions}


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


def build_decisions(claims: list[EvidenceClaim], items: list[EvidenceItem], conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_map = {item.evidence_id: item for item in items}
    fields = {conflict["field"] for conflict in conflicts}
    decisions = []
    for field in sorted(fields):
        candidates = [claim for claim in claims if claim.field == field and claim.value not in {None, "not_confirmed"}]
        ranked = sorted(candidates, key=lambda claim: claim_score(claim, item_map), reverse=True)
        if not ranked:
            continue
        best = ranked[0]
        tied = [claim for claim in ranked if claim_score(claim, item_map) == claim_score(best, item_map)]
        candidate_values = [
            {
                "value": claim.value,
                "evidence_ids": claim.evidence_ids,
                "source_priority": best_source_type(claim, item_map),
                "confidence": claim.confidence,
            }
            for claim in ranked
        ]
        if len({str(claim.value) for claim in tied}) == 1:
            decision = {"value": best.value, "rule": "highest_weighted_evidence", "confidence": downgrade_confidence(best.confidence), "status": "decided"}
        else:
            decision = {"value": "not_confirmed", "rule": "conflicting_equal_weight_evidence", "confidence": "low", "status": "unresolved"}
        decisions.append({"field": field, "candidate_values": candidate_values, "decision": decision})
    return decisions


def claim_score(claim: EvidenceClaim, item_map: dict[str, EvidenceItem]) -> tuple[float, int]:
    confidence_rank = {"low": 0, "medium": 1, "high": 2}.get(claim.confidence, 0)
    evidence_weight = max((item_map[eid].weight for eid in claim.evidence_ids if eid in item_map), default=0.0)
    return (evidence_weight, confidence_rank)


def best_source_type(claim: EvidenceClaim, item_map: dict[str, EvidenceItem]) -> str:
    ranked = sorted((item_map[eid] for eid in claim.evidence_ids if eid in item_map), key=lambda item: item.weight, reverse=True)
    return ranked[0].source_type if ranked else "unknown"


def source_weight(source_type: str) -> float:
    if source_type == "tutorial":
        return 1.0
    if source_type in {"docs", "api"}:
        return 0.9
    if source_type == "dependency":
        return 0.7
    if source_type in {"paper_methods", "paper_data", "paper_code"}:
        return 0.6
    if source_type.startswith("paper"):
        return 0.2
    if source_type == "readme":
        return 0.1
    return 0.0


def section_role(section_id: str, title: str) -> str:
    text = f"{section_id} {title}".lower()
    if "data" in text:
        return "data"
    if "code" in text or "software" in text:
        return "code"
    if "method" in text:
        return "methods"
    if any(word in text for word in ["result", "benchmark", "evaluation"]):
        return "results"
    if any(word in text for word in ["abstract", "intro", "background", "discussion", "limitation"]):
        return "background"
    return "unknown"


def downgrade_confidence(confidence: str) -> str:
    return "medium" if confidence == "high" else confidence
