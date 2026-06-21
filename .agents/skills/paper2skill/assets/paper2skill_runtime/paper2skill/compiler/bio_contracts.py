from __future__ import annotations

from typing import Any


def normalize_bio_contract_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    """Ensure claim-like bio fields carry uniform provenance metadata."""
    return _normalize_node(contract)


def _normalize_node(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {key: _normalize_node(item) for key, item in value.items()}
        if "value" in normalized and "confidence" in normalized:
            evidence = normalized.get("evidence")
            evidence_list = evidence if isinstance(evidence, list) else ([] if evidence is None else [str(evidence)])
            normalized["evidence"] = evidence_list
            normalized.setdefault("evidence_id", evidence_list[0] if evidence_list else "not_confirmed")
            normalized.setdefault("source_type", source_type_from_evidence(evidence_list))
            normalized.setdefault("claim_type", claim_type_from_source(normalized["source_type"]))
        return normalized
    if isinstance(value, list):
        return [_normalize_node(item) for item in value]
    return value


def source_type_from_evidence(evidence: list[Any]) -> str:
    text = " ".join(str(item).lower() for item in evidence)
    if "paper" in text:
        return "paper"
    if "readme" in text or "tutorial" in text or "notebook" in text:
        return "official_tutorial"
    if "repo" in text or "api" in text or "setup.py" in text:
        return "repo_code"
    if text:
        return "inferred"
    return "not_confirmed"


def claim_type_from_source(source_type: str) -> str:
    if source_type == "paper":
        return "paper_method"
    if source_type == "official_tutorial":
        return "official_tutorial"
    if source_type == "repo_code":
        return "repo_code"
    if source_type == "not_confirmed":
        return "inferred"
    return "inferred"
