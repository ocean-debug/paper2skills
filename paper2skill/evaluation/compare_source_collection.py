from __future__ import annotations

import re
from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, finish_result, ratio_for_needles, text_blob


def compare_source_collection(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("source_collection")
    source_manifest = generated.get("source_manifest") or {}
    repo_index = generated.get("repo_index") or ((source_manifest.get("repo") or {}).get("index") or {})
    tutorial_bundle = {
        "tutorial_candidates": generated.get("tutorial_candidates") or {},
        "tutorial_trace": generated.get("tutorial_trace") or {},
        "source_manifest": source_manifest,
    }

    repo_gold = gold.get("repo") or {}
    tutorial_gold = gold.get("tutorial") or {}
    repo_files = repo_gold.get("expected_files_or_dirs") or []
    repo_recall, missing_repo = ratio_for_needles(repo_files, repo_index)
    result["missing_items"].extend(f"repo_index:{item}" for item in missing_repo)

    tutorial_needles = []
    for key in ["expected_candidate_keywords", "expected_tutorial_sections", "expected_tutorial_pages", "expected_demo_files", "expected_readme_sections"]:
        tutorial_needles.extend(tutorial_gold.get(key) or [])
    tutorial_recall, missing_tutorials = ratio_for_needles(tutorial_needles, tutorial_bundle)
    result["missing_items"].extend(f"tutorial_candidate:{item}" for item in missing_tutorials)

    metrics = {
        "commit_sha_present": commit_sha_present(source_manifest) if repo_gold.get("expected_commit_sha") else 1.0,
        "repo_index_contains": repo_recall,
        "tutorial_candidate_recall": tutorial_recall,
        "path_leakage_rate": 1.0 - path_leakage_rate(generated),
    }
    return finish_result(result, metrics)


def commit_sha_present(source_manifest: dict[str, Any]) -> bool:
    repo = source_manifest.get("repo") or {}
    text = text_blob(repo)
    return bool(re.search(r"\b[0-9a-f]{7,40}\b", text))


def path_leakage_rate(value: Any) -> float:
    strings = [item for item in text_blob(value).splitlines() if item.strip()]
    if not strings:
        return 0.0
    leaked = [
        item
        for item in strings
        if re.search(r"([a-z]:\\|/home/|/users/|/tmp/|\\\\)", item, flags=re.I) and "<redacted" not in item.lower()
    ]
    return len(leaked) / len(strings)
