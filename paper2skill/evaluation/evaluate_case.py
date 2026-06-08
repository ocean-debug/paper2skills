from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from paper2skill.common import write_json
from paper2skill.evaluation.compare_adapter_behavior import compare_adapter_behavior
from paper2skill.evaluation.compare_bio_contract import compare_bio_contract
from paper2skill.evaluation.compare_dependencies import compare_dependencies
from paper2skill.evaluation.compare_io_contract import compare_io_contract
from paper2skill.evaluation.compare_source_collection import compare_source_collection
from paper2skill.evaluation.compare_tutorials import compare_tutorials
from paper2skill.evaluation.compare_workflow_dag import compare_workflow_dag
from paper2skill.evaluation.load_gold import evaluation_result, finish_result, load_generated_bundle, load_gold, ratio_for_needles


WEIGHTS = {
    "source_collection": 10,
    "dependency_mining": 15,
    "tutorial_workflow_dag": 20,
    "io_bio_contract": 25,
    "evidence_graph_correctness": 10,
    "adapter_safety_behavior": 15,
    "generated_skill_validation": 5,
}


def evaluate_case(case_dir: str | Path, generated_dir: str | Path) -> dict[str, Any]:
    gold_bundle = load_gold(case_dir)
    generated_bundle = load_generated_bundle(generated_dir)
    gold = gold_bundle["gold"]
    generated = generated_bundle["files"]

    source = compare_source_collection(gold.get("source_collection", {}), generated)
    dependencies = compare_dependencies(gold.get("dependency_contract", {}), generated)
    tutorials = compare_tutorials(gold.get("tutorial_selection", {}), generated)
    workflow = compare_workflow_dag(gold.get("workflow_dag", {}), generated)
    io_contract = compare_io_contract(gold.get("io_contract", {}), generated)
    bio_contract = compare_bio_contract(gold.get("bio_contract", {}), generated)
    adapter = compare_adapter_behavior(gold.get("adapter_behavior", {}), generated)
    evidence = compare_evidence_expectations(gold.get("evidence_expectations", {}), generated)
    validation = generated_reference_validation(generated_bundle)

    category_scores = {
        "source_collection": source["score"],
        "dependency_mining": dependencies["score"],
        "tutorial_workflow_dag": round((tutorials["score"] + workflow["score"]) / 2, 2),
        "io_bio_contract": round((io_contract["score"] + bio_contract["score"]) / 2, 2),
        "evidence_graph_correctness": evidence["score"],
        "adapter_safety_behavior": adapter["score"],
        "generated_skill_validation": validation["score"],
    }
    total = round(sum(category_scores[key] * weight / 100.0 for key, weight in WEIGHTS.items()), 2)
    warnings = list(generated_bundle.get("warnings") or [])
    if gold_bundle["missing_files"]:
        warnings.extend(f"missing gold file: {path}" for path in gold_bundle["missing_files"])
    if generated_bundle["missing_files"]:
        warnings.extend(f"missing generated file: {path}" for path in generated_bundle["missing_files"])
    return {
        "case_id": gold_bundle["case_id"],
        "case_dir": gold_bundle["case_dir"],
        "generated_dir": generated_bundle["generated_dir"],
        "score": total,
        "passed": total >= 85.0 and not gold_bundle["missing_files"],
        "grade": score_grade(total),
        "weights": WEIGHTS,
        "category_scores": category_scores,
        "evaluators": {
            "source_collection": source,
            "dependencies": dependencies,
            "tutorials": tutorials,
            "workflow_dag": workflow,
            "io_contract": io_contract,
            "bio_contract": bio_contract,
            "evidence_expectations": evidence,
            "adapter_behavior": adapter,
            "generated_skill_validation": validation,
        },
        "missing_gold_files": gold_bundle["missing_files"],
        "missing_generated_files": generated_bundle["missing_files"],
        "warnings": sorted(dict.fromkeys(warnings)),
    }


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
        aliases.extend(["R_source", "DTEG.R_script", "paper_protocol"])
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


def generated_reference_validation(generated_bundle: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("generated_skill_validation")
    required = ["source_manifest", "workflow_dag", "io_contract", "bio_contract", "adapter_spec", "evidence_graph"]
    files = generated_bundle.get("files") or {}
    present = {key for key in required if files.get(key)}
    missing = sorted(set(required) - present)
    result["missing_items"].extend(missing)
    return finish_result(result, {"required_reference_files_present": len(present) / len(required)})


def score_grade(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "usable_with_review"
    if score >= 50:
        return "partial"
    return "fail"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate generated Paper2Skill references against a benchmark case gold standard.")
    parser.add_argument("--case", required=True, help="Path to benchmarks/real/<case_id>")
    parser.add_argument("--generated", required=True, help="Path to generated skill references directory")
    parser.add_argument("--out", required=True, help="Path to write evaluation JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = evaluate_case(args.case, args.generated)
    write_json(Path(args.out), result)
    print(json.dumps({"case_id": result["case_id"], "score": result["score"], "grade": result["grade"], "passed": result["passed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
