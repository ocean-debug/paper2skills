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
from paper2skill.evaluation.summarize_benchmark import summarize_results
from paper2skill.generators.codex_skill_generator import build_context, generate_skill


Builder = Callable[..., dict[str, Any]]
Generator = Callable[[dict[str, Any], str | Path], Path]
Evaluator = Callable[[str | Path, str | Path], dict[str, Any]]


def load_case_metadata(case_dir: str | Path) -> dict[str, Any]:
    root = Path(case_dir)
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
    required = ["case_id", "tool_name", "paper_title", "paper_url", "repo_url", "primary_language"]
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"{case_md}: missing required metadata: {', '.join(missing)}")
    return data


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
    builder: Builder = build_context,
    generator: Generator = generate_skill,
    evaluator: Evaluator = evaluate_case,
) -> dict[str, Any]:
    case_dirs = discover_cases(cases_root)
    out_base = ensure_dir(Path(out_root))
    results = []
    for case_dir in case_dirs:
        results.append(run_one_case(case_dir, out_base, strict_evidence=strict_evidence, builder=builder, generator=generator, evaluator=evaluator))
    summary_path = out_base / "benchmark_summary.md"
    summary = summarize_results([item["evaluation_path"] for item in results if item.get("evaluation_path")])
    write_text(summary_path, summary)
    run_result = {
        "status": "complete",
        "cases_root": str(cases_root),
        "out_root": str(out_base),
        "summary_path": str(summary_path),
        "case_count": len(results),
        "failed_case_count": sum(1 for item in results if item.get("status") != "evaluated"),
        "cases": results,
    }
    write_json(out_base / "run_real_benchmark.json", run_result)
    return run_result


def run_one_case(
    case_dir: Path,
    out_root: Path,
    *,
    strict_evidence: bool,
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


def public_case_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": metadata.get("case_id"),
        "tool_name": metadata.get("tool_name"),
        "paper_title": metadata.get("paper_title"),
        "paper_url": metadata.get("paper_url"),
        "repo_url": metadata.get("repo_url"),
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_real_benchmark(cases_root=args.cases, out_root=args.out_root, strict_evidence=args.strict_evidence)
    print(json.dumps({"status": result["status"], "case_count": result["case_count"], "failed_case_count": result["failed_case_count"], "summary_path": result["summary_path"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
