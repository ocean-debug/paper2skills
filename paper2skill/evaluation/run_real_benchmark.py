from __future__ import annotations

import argparse
import json
import re
import traceback
from pathlib import Path
from typing import Any, Callable

import yaml

from paper2skill.common import ensure_dir, write_json, write_text
from paper2skill.evaluation.evaluate_case import evaluate_case
from paper2skill.evaluation.schemas import BENCHMARK_L2_MODE
from paper2skill.evaluation.summarize_benchmark import summarize_data, summarize_results
from paper2skill.generators.codex_skill_generator import build_context, generate_skill


Builder = Callable[..., dict[str, Any]]
Generator = Callable[[dict[str, Any], str | Path], Path]
Evaluator = Callable[[str | Path, str | Path], dict[str, Any]]


def load_case_metadata(case_dir: str | Path) -> dict[str, Any]:
    root = Path(case_dir)
    metadata_yaml = root / "gold" / "case_metadata.yaml"
    if metadata_yaml.exists():
        data = yaml.safe_load(metadata_yaml.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"invalid case_metadata.yaml: {metadata_yaml}")
        validate_case_metadata(data, metadata_yaml)
        return data
    case_md = root / "case.md"
    if not case_md.exists():
        raise FileNotFoundError(f"missing case.md: {case_md}")
    text = case_md.read_text(encoding="utf-8")
    match = re.search(r"## Basic information\s*```yaml\s*\n(.*?)\n```", text, flags=re.S)
    if not match:
        raise ValueError(f"missing Basic information YAML block: {case_md}")
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid Basic information YAML block: {case_md}")
    validate_case_metadata(data, case_md)
    return data


def validate_case_metadata(data: dict[str, Any], source: Path) -> None:
    required = ["case_id", "tool_name", "paper_title", "paper_url", "repo_url", "primary_language"]
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"{source}: missing required metadata: {', '.join(missing)}")


def discover_cases(cases_root: str | Path) -> list[Path]:
    root = Path(cases_root)
    if (root / "case.md").exists():
        return [root]
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "case.md").exists())


def run_real_benchmark(
    *,
    cases_root: str | Path,
    out_root: str | Path,
    strict_evidence: bool = False,
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
    builder: Builder = build_context,
    generator: Generator = generate_skill,
    evaluator: Evaluator = evaluate_case,
) -> dict[str, Any]:
    case_dirs = discover_cases(cases_root)
    out_base = ensure_dir(Path(out_root))
    results = []
    for case_dir in case_dirs:
        results.append(
            run_one_case(
                case_dir,
                out_base,
                strict_evidence=strict_evidence,
                levels=levels,
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
                builder=builder,
                generator=generator,
                evaluator=evaluator,
            )
        )
    summary_path = out_base / "benchmark_summary.md"
    result_paths = [item["evaluation_path"] for item in results if item.get("evaluation_path")]
    summary = summarize_results(result_paths)
    write_text(summary_path, summary)
    summary_json_path = out_base / "benchmark_summary.json"
    write_json(summary_json_path, summarize_data(result_paths))
    run_result = {
        "status": "complete",
        "cases_root": str(cases_root),
        "out_root": str(out_base),
        "summary_path": str(summary_path),
        "summary_json_path": str(summary_json_path),
        "case_count": len(results),
        "failed_case_count": sum(1 for item in results if item.get("status") != "evaluated"),
        "benchmark_policy": {
            "build_validation_is_scoring": False,
            "l2_requires_live_execute": True,
            "requested_l2_mode": l2_mode,
        },
        "cases": results,
    }
    write_json(out_base / "run_real_benchmark.json", run_result)
    return run_result


def run_one_case(
    case_dir: Path,
    out_root: Path,
    *,
    strict_evidence: bool,
    levels: list[str] | None,
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
    builder: Builder,
    generator: Generator,
    evaluator: Evaluator,
) -> dict[str, Any]:
    metadata = load_case_metadata(case_dir)
    case_id = str(metadata["case_id"])
    case_out = ensure_dir(out_root / case_id)
    skill_dir = case_out / "skill"
    evaluation_path = case_out / "evaluation.json"
    try:
        context = builder(
            skill_name=case_id,
            algorithm_name=str(metadata["tool_name"]),
            paper_url=str(metadata["paper_url"]),
            paper_title=str(metadata["paper_title"]),
            repo=str(metadata["repo_url"]),
            repo_ref=None,
            language=language_value(metadata.get("primary_language")),
            no_execute_tutorials=True,
            strict_evidence=strict_evidence,
            collection_dir=case_out / ".paper2skill_collection",
        )
        generator(context, skill_dir)
        try:
            evaluation = evaluator(
                case_dir,
                skill_dir,
                levels=levels,
                allow_download=allow_download,
                download_cache=download_cache,
                max_download_mb=max_download_mb,
                allow_execution=allow_execution,
                l2_mode=l2_mode,
                allow_install=allow_install,
                install_env=install_env or default_l2_env(case_id),
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
        except TypeError:
            evaluation = evaluator(case_dir, skill_dir / "references")
        evaluation["build"] = {"status": "built", "case_metadata": public_case_metadata(metadata)}
        write_json(evaluation_path, evaluation)
        return {"case_id": case_id, "status": "evaluated", "skill_dir": str(skill_dir), "evaluation_path": str(evaluation_path), "score": evaluation.get("score"), "grade": evaluation.get("grade")}
    except Exception as exc:  # noqa: BLE001 - runner must preserve batch progress.
        evaluation = failed_evaluation(case_dir, skill_dir, metadata, exc)
        write_json(evaluation_path, evaluation)
        return {"case_id": case_id, "status": "failed", "skill_dir": str(skill_dir), "evaluation_path": str(evaluation_path), "error": str(exc)}


def language_value(value: Any) -> str | None:
    text = str(value).strip().lower()
    if text == "python":
        return "python"
    if text == "r":
        return "r"
    return None


def default_l2_env(case_id: str) -> str:
    return f"p2s_l2_{case_id}"


def public_case_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": metadata.get("case_id"),
        "tool_name": metadata.get("tool_name"),
        "paper_title": metadata.get("paper_title"),
        "paper_url": metadata.get("paper_url"),
        "repo_url": metadata.get("repo_url"),
        "tutorial_urls": metadata.get("tutorial_urls"),
        "primary_language": metadata.get("primary_language"),
    }


def failed_evaluation(case_dir: Path, skill_dir: Path, metadata: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "case_id": metadata.get("case_id") or case_dir.name,
        "case_dir": str(case_dir),
        "generated_dir": str(skill_dir / "references"),
        "score": 0.0,
        "passed": False,
        "grade": "fail",
        "category_scores": {},
        "evaluators": {},
        "missing_gold_files": [],
        "missing_generated_files": [],
        "warnings": [f"build_or_evaluation_failed: {exc}"],
        "build": {
            "status": "failed",
            "case_metadata": public_case_metadata(metadata),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and evaluate all real Paper2Skill benchmark cases.")
    parser.add_argument("--cases", default="benchmarks/real", help="Real benchmark cases root, or a single case directory")
    parser.add_argument("--out-root", default="generated/real", help="Output root for generated skills and evaluations")
    parser.add_argument("--strict-evidence", action="store_true", help="Use strict evidence mode during skill generation")
    parser.add_argument("--levels", default="L0,L1,L2,L3,L4", help="Comma-separated levels to evaluate")
    parser.add_argument("--allow-download", action="store_true", help="Allow explicit official-data downloads")
    parser.add_argument("--download-cache", default="benchmarks/data_cache", help="Download cache directory")
    parser.add_argument("--max-download-mb", type=float, default=0.0, help="Maximum download size for entries without a tighter limit")
    parser.add_argument("--allow-execution", default="reviewed_only", choices=["none", "reviewed_only", "all"], help="Execution policy for L2/L3")
    parser.add_argument("--l2-mode", default=BENCHMARK_L2_MODE, choices=["dry_run", "data_smoke", "live_execute"], help="Benchmark L2 depth; live_execute is required for real L2 scoring. dry_run/data_smoke are diagnostic-only.")
    parser.add_argument("--allow-install", default="none", choices=["none", "ask", "approved"], help="Dependency install policy; 'approved' installs into the case env")
    parser.add_argument("--install-env", help="Target environment name/path; omitted means p2s_l2_<case_id>")
    parser.add_argument("--create-conda-env", action="store_true", help="Create the target conda env before approved live execution")
    parser.add_argument("--python-version", default="3.11", help="Python version for --create-conda-env")
    parser.add_argument("--env-rebuilder", default="legacy", choices=["legacy", "bio"], help="Environment rebuild planner for approved L2 installs")
    parser.add_argument("--target-env-mode", default="new", choices=["new", "existing"], help="BioEnvRebuilder target mode")
    parser.add_argument("--allow-github-install", default="ask", choices=["ask", "approved"], help="Whether BioEnvRebuilder may execute GitHub install steps")
    parser.add_argument("--gpu-policy", default="optional", choices=["required", "optional", "cpu_only"], help="BioEnvRebuilder GPU policy")
    parser.add_argument("--torch-backend", default="auto", choices=["auto", "cpu", "cu118", "cu121", "cu124", "cu126", "cu128"], help="PyTorch special-route CPU/CUDA profile")
    parser.add_argument("--repair-attempts", type=int, default=3, help="Number of BioEnvRebuilder repair attempts to record/request")
    parser.add_argument("--export-lock", action="store_true", help="Request lockfile export artifacts after L2 approved installs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_real_benchmark(
        cases_root=args.cases,
        out_root=args.out_root,
        strict_evidence=args.strict_evidence,
        levels=[args.levels],
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
    print(json.dumps({"status": result["status"], "case_count": result["case_count"], "failed_case_count": result["failed_case_count"], "summary_path": result["summary_path"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
