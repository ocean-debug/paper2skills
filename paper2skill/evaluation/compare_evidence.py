from __future__ import annotations

import json
import re
from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, finish_result


def compare_evidence_expectations(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("evidence_expectations")
    evidence_bundle = {
        "evidence_graph": generated.get("evidence_graph") or {},
        "source_manifest": generated.get("source_manifest") or {},
        "repo_evidence": generated.get("repo_evidence") or {},
        "paper_evidence": generated.get("paper_evidence") or {},
        "tutorial_trace": generated.get("tutorial_trace") or {},
        "tutorial_candidates": generated.get("tutorial_candidates") or {},
        "environment_spec": generated.get("environment_spec") or {},
        "io_contract": generated.get("io_contract") or {},
        "bio_contract": generated.get("bio_contract") or {},
        "adapter_spec": generated.get("adapter_spec") or {},
    }
    evidence_bundle = add_evidence_aliases(evidence_bundle)
    source_recall, missing_sources = evidence_ratio_for_needles(gold.get("high_priority_sources") or [], evidence_bundle)
    claim_recall, missing_claims = evidence_ratio_for_needles(gold.get("required_claims_with_evidence") or [], evidence_bundle)
    result["missing_items"].extend(f"evidence_source:{item}" for item in missing_sources)
    result["missing_items"].extend(f"evidence_claim:{item}" for item in missing_claims)
    return finish_result(result, {"source_recall": source_recall, "claim_recall": claim_recall})


def add_evidence_aliases(bundle: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(bundle, sort_keys=True).lower()
    aliases = []
    if "readme" in text:
        aliases.extend(["repo_readme", "official_documentation"])
    if any(value in text for value in ["requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "description", "namespace"]):
        aliases.append("setup_or_requirements")
    if any(value in text for value in [".ipynb", ".py", ".r", "tutorial"]):
        aliases.extend(["tutorial_code", "demo_notebooks"])
    if ".r" in text or "rscript" in text:
        aliases.extend(["R_source", "Rscript CLI source", "paper_protocol"])
    if "positional_arguments" in text and "rscript" in text:
        aliases.append("Rscript CLI positional arguments")
    if "condition_key" in text or "condition" in text:
        aliases.extend(["condition labels required", "metadata requires cell_type and label"])
    if "celltype_key" in text or "cell_type" in text:
        aliases.append("cell_type labels required")
    enriched = dict(bundle)
    enriched["_evidence_aliases"] = sorted(dict.fromkeys(aliases))
    return enriched


def evidence_ratio_for_needles(needles: list[Any], haystack: Any) -> tuple[float, list[str]]:
    expected = [str(item) for item in needles if str(item).strip()]
    if not expected:
        return 1.0, []
    haystack_text = json.dumps(haystack, sort_keys=True).lower()
    missing = []
    for item in expected:
        normalized = item.lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token and token not in {"and", "or", "the", "a", "an", "is", "are", "with"}]
        if normalized in haystack_text or (tokens and sum(1 for token in tokens if token in haystack_text) / len(tokens) >= 0.6):
            continue
        missing.append(item)
    return (len(expected) - len(missing)) / len(expected), missing
