from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paper2skill.common import write_json, write_text
from paper2skill.evaluation.agentic.evaluate_agentic_task import evaluate_agentic_tasks
from paper2skill.evaluation.compare_adapter_behavior import compare_adapter_behavior
from paper2skill.evaluation.compare_bio_contract import compare_bio_contract
from paper2skill.evaluation.compare_dependencies import compare_dependencies
from paper2skill.evaluation.compare_evidence import compare_evidence_expectations
from paper2skill.evaluation.compare_io_contract import compare_io_contract
from paper2skill.evaluation.compare_source_collection import compare_source_collection
from paper2skill.evaluation.compare_tutorials import compare_tutorials
from paper2skill.evaluation.compare_workflow_dag import compare_workflow_dag
from paper2skill.evaluation.execution.run_new_data_validation import evaluate_new_data
from paper2skill.evaluation.execution.run_official_example import evaluate_official_examples
from paper2skill.evaluation.load_gold import evaluation_result, finish_result, load_generated_bundle, load_gold
from paper2skill.evaluation.schemas import BENCHMARK_L2_MODE, LEVEL_WEIGHTS, STATIC_L1_WEIGHTS, VALID_INSTALL_POLICIES, VALID_L2_MODES, VALID_LEVELS
from paper2skill.evaluation.validate_skill_package import validate_skill_package


def evaluate_case(
    case_dir: str | Path,
    generated_dir: str | Path,
    *,
    levels: list[str] | None = None,
    allow_download: bool = False,
    download_cache: str | Path = "benchmarks/data_cache",
    max_download_mb: float = 0.0,
    allow_execution: str = "reviewed_only",
    l2_mode: str = BENCHMARK_L2_MODE,
    allow_install: str = "none",
    install_env: str | None = None,
    create_conda_env: bool = False,
    python_version: str = "3.11",
    env_rebuilder: str = "legacy",
    target_env_mode: str = "new",
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    repair_attempts: int = 3,
    export_lock: bool = False,
) -> dict[str, Any]:
    selected_levels = normalize_levels(levels)
    l2_mode = normalize_choice(l2_mode, VALID_L2_MODES, "l2_mode")
    allow_install = normalize_choice(allow_install, VALID_INSTALL_POLICIES, "allow_install")
    gold_bundle = load_gold(case_dir)
    generated_bundle = load_generated_bundle(generated_dir)
    gold = gold_bundle["gold"]
    generated = generated_bundle["files"]
    skill_dir = generated_bundle["skill_dir"]

    level_results: dict[str, dict[str, Any]] = {}
    evaluators: dict[str, Any] = {}
    if "L0" in selected_levels:
        level_results["L0"] = evaluate_l0(gold, skill_dir)
        evaluators.update(level_results["L0"].get("evaluators") or {})
    if "L1" in selected_levels:
        level_results["L1"] = evaluate_l1(gold, generated, generated_bundle)
        evaluators.update(level_results["L1"].get("evaluators") or {})
    if "L2" in selected_levels:
        level_results["L2"] = evaluate_l2(
            gold,
            generated,
            skill_dir,
            case_dir=case_dir,
            allow_download=allow_download,
            download_cache=download_cache,
            max_download_mb=max_download_mb,
            allow_execution=allow_execution,
            l2_mode=l2_mode,
            allow_install=allow_install,
            install_env=install_env,
            create_conda_env=create_conda_env,
            python_version=python_version,
            env_rebuilder=env_rebuilder,
            target_env_mode=target_env_mode,
            allow_github_install=allow_github_install,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            repair_attempts=repair_attempts,
            export_lock=export_lock,
        )
        evaluators.update(level_results["L2"].get("evaluators") or {})
    if "L3" in selected_levels:
        level_results["L3"] = evaluate_l3(gold, generated)
        evaluators.update(level_results["L3"].get("evaluators") or {})
    if "L4" in selected_levels:
        level_results["L4"] = evaluate_l4(gold, generated)
        evaluators.update(level_results["L4"].get("evaluators") or {})

    score_by_level = {level: data["score"] for level, data in level_results.items()}
    total = weighted_level_score(score_by_level, selected_levels)
    warnings = collect_warnings(gold_bundle, generated_bundle, level_results)
    result = {
        "case_id": gold_bundle["case_id"],
        "case_dir": gold_bundle["case_dir"],
        "generated_dir": generated_bundle["generated_dir"],
        "skill_dir": skill_dir,
        "levels": selected_levels,
        "score": total,
        "overall_score": total,
        "passed": total >= 85.0 and not gold_bundle["missing_files"],
        "grade": score_grade(total),
        "weights": {level: LEVEL_WEIGHTS[level] for level in selected_levels},
        "score_by_level": score_by_level,
        "score_by_component": component_scores(level_results),
        "category_scores": legacy_category_scores(level_results),
        "level_results": level_results,
        "evaluators": evaluators,
        "benchmark_policy": {
            "build_validation_is_scoring": False,
            "l2_requires_live_execute": True,
            "requested_l2_mode": l2_mode,
        },
        "missing_gold_files": gold_bundle["missing_files"],
        "missing_generated_files": generated_bundle["missing_files"],
        "warnings": sorted(dict.fromkeys(warnings)),
    }
    return result


def evaluate_l0(gold: dict[str, Any], skill_dir: str | Path) -> dict[str, Any]:
    evaluator = validate_skill_package(skill_dir, gold.get("level0_skill_package", {}))
    return {"level": "L0", "score": evaluator["score"], "passed": evaluator["passed"], "evaluators": {"skill_package": evaluator}}


def evaluate_l1(gold: dict[str, Any], generated: dict[str, Any], generated_bundle: dict[str, Any]) -> dict[str, Any]:
    source = compare_source_collection(gold.get("source_collection", {}), generated)
    dependencies = compare_dependencies(gold.get("dependency_contract", {}), generated)
    tutorials = compare_tutorials(gold.get("tutorial_selection", {}), generated)
    workflow = compare_workflow_dag(gold.get("workflow_dag", {}), generated)
    io_contract = compare_io_contract(gold.get("io_contract", {}), generated)
    bio_contract = compare_bio_contract(gold.get("bio_contract", {}), generated)
    adapter = compare_adapter_behavior(gold.get("adapter_behavior", {}), generated)
    evidence = compare_evidence_expectations(gold.get("evidence_expectations", {}), generated)
    execution_safety = execution_safety_plan(generated)
    scores = {
        "source_collection": source["score"],
        "dependency_mining": dependencies["score"],
        "tutorial_workflow_dag": round((tutorials["score"] + workflow["score"]) / 2, 2),
        "io_bio_contract": round((io_contract["score"] + bio_contract["score"]) / 2, 2),
        "evidence_graph_correctness": evidence["score"],
        "adapter_safety_behavior": adapter["score"],
        "execution_safety_plan": execution_safety["score"],
    }
    total = round(sum(scores[key] * weight / 100.0 for key, weight in STATIC_L1_WEIGHTS.items()), 2)
    evaluators = {
        "source_collection": source,
        "dependencies": dependencies,
        "tutorials": tutorials,
        "workflow_dag": workflow,
        "io_contract": io_contract,
        "bio_contract": bio_contract,
        "evidence_expectations": evidence,
        "adapter_behavior": adapter,
        "execution_safety_plan": execution_safety,
    }
    return {"level": "L1", "score": total, "passed": total >= 85.0, "category_scores": scores, "evaluators": evaluators}


def evaluate_l2(
    gold: dict[str, Any],
    generated: dict[str, Any],
    skill_dir: str | Path,
    *,
    case_dir: str | Path,
    allow_download: bool,
    download_cache: str | Path,
    max_download_mb: float,
    allow_execution: str,
    l2_mode: str,
    allow_install: str,
    install_env: str | None,
    create_conda_env: bool,
    python_version: str,
    env_rebuilder: str,
    target_env_mode: str,
    allow_github_install: str,
    gpu_policy: str,
    torch_backend: str,
    repair_attempts: int,
    export_lock: bool,
) -> dict[str, Any]:
    evaluator = evaluate_official_examples(
        gold.get("level2_official_examples", {}),
        generated,
        skill_dir=skill_dir,
        case_dir=case_dir,
        allow_download=allow_download,
        download_cache=download_cache,
        max_download_mb=max_download_mb,
        allow_execution=allow_execution,
        l2_mode=l2_mode,
        allow_install=allow_install,
        install_env=install_env,
        create_conda_env=create_conda_env,
        python_version=python_version,
        env_rebuilder=env_rebuilder,
        target_env_mode=target_env_mode,
        allow_github_install=allow_github_install,
        gpu_policy=gpu_policy,
        torch_backend=torch_backend,
        repair_attempts=repair_attempts,
        export_lock=export_lock,
    )
    return {"level": "L2", "score": evaluator["score"], "passed": evaluator["passed"], "evaluators": {"official_example_execution": evaluator}}


def evaluate_l3(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    evaluator = evaluate_new_data(gold.get("level3_new_data", {}), generated)
    return {"level": "L3", "score": evaluator["score"], "passed": evaluator["passed"], "evaluators": {"new_data_generalization": evaluator}}


def evaluate_l4(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    evaluator = evaluate_agentic_tasks(gold.get("level4_agentic_tasks", {}), generated)
    return {"level": "L4", "score": evaluator["score"], "passed": evaluator["passed"], "evaluators": {"agentic_usage": evaluator}}


def execution_safety_plan(generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("execution_safety_plan")
    adapter_spec = generated.get("adapter_spec") if isinstance(generated.get("adapter_spec"), dict) else {}
    adapter_review = generated.get("adapter_review") if isinstance(generated.get("adapter_review"), dict) else {}
    environment_spec = generated.get("environment_spec") if isinstance(generated.get("environment_spec"), dict) else {}
    notebook_policy = generated.get("notebook_execution_policy") if isinstance(generated.get("notebook_execution_policy"), dict) else {}
    adapter_status = str(adapter_spec.get("status") or adapter_review.get("status") or "").lower()
    notebook_safe = not bool(notebook_policy.get("execute_unknown_notebooks"))
    install_policy_text = json.dumps(environment_spec, ensure_ascii=False).lower()
    install_safe = "ask" in install_policy_text or "confirm" in install_policy_text or "auto_install" not in install_policy_text
    lifecycle_safe = adapter_status not in {"ready", "reviewed", "verified"} or bool(adapter_review.get("human_approved") or adapter_review.get("dry_run"))
    if not notebook_safe:
        result["mismatched_items"].append({"field": "notebook_execution_policy", "expected": "unknown notebooks disabled", "actual": "enabled"})
    if not install_safe:
        result["mismatched_items"].append({"field": "install_policy", "expected": "explicit approval", "actual": "unsafe or unclear"})
    if not lifecycle_safe:
        result["mismatched_items"].append({"field": "adapter_lifecycle", "expected": "review evidence before executable status", "actual": adapter_status})
    return finish_result(
        result,
        {
            "notebook_execution_policy_safe": notebook_safe,
            "install_policy_requires_approval": install_safe,
            "adapter_lifecycle_evidence_present": lifecycle_safe,
        },
    )


def normalize_levels(levels: list[str] | None) -> list[str]:
    if not levels:
        return list(VALID_LEVELS)
    cleaned = []
    for item in levels:
        for value in str(item).split(","):
            level = value.strip().upper()
            if level:
                if level not in VALID_LEVELS:
                    raise ValueError(f"unknown evaluation level: {level}")
                cleaned.append(level)
    return sorted(dict.fromkeys(cleaned), key=VALID_LEVELS.index)


def normalize_choice(value: str, choices: tuple[str, ...], field: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned not in choices:
        raise ValueError(f"unknown {field}: {cleaned}")
    return cleaned


def weighted_level_score(score_by_level: dict[str, float], levels: list[str]) -> float:
    total_weight = sum(LEVEL_WEIGHTS[level] for level in levels)
    if not total_weight:
        return 0.0
    return round(sum(score_by_level.get(level, 0.0) * LEVEL_WEIGHTS[level] for level in levels) / total_weight, 2)


def component_scores(level_results: dict[str, dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for level, data in level_results.items():
        for name, evaluator in (data.get("evaluators") or {}).items():
            scores[f"{level}.{name}"] = evaluator.get("score", 0.0)
    return scores


def legacy_category_scores(level_results: dict[str, dict[str, Any]]) -> dict[str, float]:
    l1 = level_results.get("L1") or {}
    scores = dict(l1.get("category_scores") or {})
    if "L0" in level_results:
        scores["skill_package"] = level_results["L0"]["score"]
    if "L2" in level_results:
        scores["official_example_execution"] = level_results["L2"]["score"]
    if "L3" in level_results:
        scores["new_data_generalization"] = level_results["L3"]["score"]
    if "L4" in level_results:
        scores["agentic_usage"] = level_results["L4"]["score"]
    return scores


def collect_warnings(gold_bundle: dict[str, Any], generated_bundle: dict[str, Any], level_results: dict[str, dict[str, Any]]) -> list[str]:
    warnings = list(generated_bundle.get("warnings") or [])
    if gold_bundle["missing_files"]:
        warnings.extend(f"missing gold file: {path}" for path in gold_bundle["missing_files"])
    if generated_bundle["missing_files"]:
        warnings.extend(f"missing generated file: {path}" for path in generated_bundle["missing_files"])
    for level in level_results.values():
        for evaluator in (level.get("evaluators") or {}).values():
            warnings.extend(evaluator.get("warnings") or [])
    return warnings


def score_grade(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "usable_with_review"
    if score >= 50:
        return "partial"
    return "fail"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate generated Paper2Skill skill against benchmark gold standards.")
    parser.add_argument("--case", required=True, help="Path to benchmarks/real/<case_id>")
    parser.add_argument("--generated", required=True, help="Generated skill root or references directory")
    parser.add_argument("--levels", default="L0,L1,L2,L3,L4", help="Comma-separated levels to evaluate, e.g. L0,L1")
    parser.add_argument("--allow-download", action="store_true", help="Allow explicit L2/L3 downloads")
    parser.add_argument("--download-cache", default="benchmarks/data_cache", help="Download cache directory")
    parser.add_argument("--max-download-mb", type=float, default=0.0, help="Maximum download size for entries without a tighter limit")
    parser.add_argument("--allow-execution", default="reviewed_only", choices=["none", "reviewed_only", "all"], help="Execution policy for L2/L3")
    parser.add_argument("--l2-mode", default=BENCHMARK_L2_MODE, choices=list(VALID_L2_MODES), help="Benchmark L2 depth; real benchmark scoring requires live_execute. dry_run/data_smoke are diagnostic-only.")
    parser.add_argument("--allow-install", default="none", choices=list(VALID_INSTALL_POLICIES), help="Dependency install policy; 'ask' returns an install approval request; 'approved' installs into --install-env")
    parser.add_argument("--install-env", help="Target environment name/path to include in L2 install approval requests")
    parser.add_argument("--create-conda-env", action="store_true", help="Create --install-env before approved L2 live execution")
    parser.add_argument("--python-version", default="3.11", help="Python version for --create-conda-env")
    parser.add_argument("--env-rebuilder", default="legacy", choices=["legacy", "bio"], help="Environment rebuild planner for approved L2 installs")
    parser.add_argument("--target-env-mode", default="new", choices=["new", "existing"], help="BioEnvRebuilder target mode")
    parser.add_argument("--allow-github-install", default="ask", choices=["ask", "approved"], help="Whether BioEnvRebuilder may execute GitHub install steps")
    parser.add_argument("--gpu-policy", default="optional", choices=["required", "optional", "cpu_only"], help="BioEnvRebuilder GPU policy")
    parser.add_argument("--torch-backend", default="auto", choices=["auto", "cpu", "cu118", "cu121", "cu124", "cu126", "cu128"], help="PyTorch special-route CPU/CUDA profile")
    parser.add_argument("--repair-attempts", type=int, default=3, help="Number of BioEnvRebuilder repair attempts to record/request")
    parser.add_argument("--export-lock", action="store_true", help="Request lockfile export artifacts after L2 approved installs")
    parser.add_argument("--out", required=True, help="Path to write evaluation JSON")
    parser.add_argument("--markdown-out", help="Optional per-case Markdown report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = evaluate_case(
        args.case,
        args.generated,
        levels=normalize_levels([args.levels]),
        allow_download=args.allow_download,
        download_cache=args.download_cache,
        max_download_mb=args.max_download_mb,
        allow_execution=args.allow_execution,
        l2_mode=args.l2_mode,
        allow_install=args.allow_install,
        install_env=args.install_env,
        create_conda_env=args.create_conda_env,
        python_version=args.python_version,
        env_rebuilder=args.env_rebuilder,
        target_env_mode=args.target_env_mode,
        allow_github_install=args.allow_github_install,
        gpu_policy=args.gpu_policy,
        torch_backend=args.torch_backend,
        repair_attempts=args.repair_attempts,
        export_lock=args.export_lock,
    )
    write_json(Path(args.out), result)
    if args.markdown_out:
        write_text(Path(args.markdown_out), case_markdown(result))
    print(json.dumps({"case_id": result["case_id"], "score": result["score"], "grade": result["grade"], "passed": result["passed"]}, ensure_ascii=False))
    return 0


def case_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Evaluation: {result.get('case_id')}", ""]
    lines.append(f"- Score: {float(result.get('score', 0.0)):.2f}")
    lines.append(f"- Grade: {result.get('grade')}")
    lines.append(f"- Passed: {'yes' if result.get('passed') else 'no'}")
    lines.append("")
    lines.append("| Level | Score | Passed |")
    lines.append("|---|---:|---|")
    for level, score in (result.get("score_by_level") or {}).items():
        passed = (result.get("level_results") or {}).get(level, {}).get("passed")
        lines.append(f"| {level} | {float(score):.2f} | {'yes' if passed else 'no'} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
