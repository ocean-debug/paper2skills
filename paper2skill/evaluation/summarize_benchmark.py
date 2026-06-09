from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from paper2skill.common import write_json, write_text


def summarize_results(paths: list[str | Path]) -> str:
    results = [load_result(path) for path in expand_paths(paths)]
    summary = summarize_data_from_results(results)
    lines = ["# Paper2Skill Benchmark Summary", ""]
    if not results:
        lines.extend(["No evaluation results were found.", ""])
        return "\n".join(lines)
    lines.append(f"- Cases: {summary['case_count']}")
    lines.append(f"- Average score: {summary['average_score']:.2f}")
    lines.append("")
    lines.append("| Case | Score | Grade | Passed | L0 | L1 | L2 | L2 Status | L3 | L4 |")
    lines.append("|---|---:|---|---|---:|---:|---:|---|---:|---:|")
    for item in sorted(results, key=lambda value: str(value.get("case_id", ""))):
        levels = item.get("score_by_level") or {}
        lines.append(
            "| {case} | {score:.2f} | {grade} | {passed} | {l0:.2f} | {l1:.2f} | {l2:.2f} | {l2_status} | {l3:.2f} | {l4:.2f} |".format(
                case=item.get("case_id", "unknown"),
                score=float(item.get("score", 0.0)),
                grade=item.get("grade", "unknown"),
                passed="yes" if item.get("passed") else "no",
                l0=float(levels.get("L0", 0.0)),
                l1=float(levels.get("L1", legacy_l1_score(item))),
                l2=float(levels.get("L2", 0.0)),
                l2_status=format_l2_status(item),
                l3=float(levels.get("L3", 0.0)),
                l4=float(levels.get("L4", 0.0)),
            )
        )
    lines.append("")
    lines.append("## L1 Static Components")
    lines.append("")
    lines.append("| Case | Source | Dependency | Tutorial/Workflow | IO/Bio | Evidence | Adapter | Validation |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for item in sorted(results, key=lambda value: str(value.get("case_id", ""))):
        scores = item.get("category_scores") or {}
        lines.append(
            "| {case} | {source:.2f} | {dep:.2f} | {tw:.2f} | {io:.2f} | {ev:.2f} | {ad:.2f} | {val:.2f} |".format(
                case=item.get("case_id", "unknown"),
                source=float(scores.get("source_collection", 0.0)),
                dep=float(scores.get("dependency_mining", 0.0)),
                tw=float(scores.get("tutorial_workflow_dag", 0.0)),
                io=float(scores.get("io_bio_contract", 0.0)),
                ev=float(scores.get("evidence_graph_correctness", 0.0)),
                ad=float(scores.get("adapter_safety_behavior", 0.0)),
                val=float(scores.get("generated_skill_validation", 0.0)),
            )
        )
    warnings = []
    for item in results:
        warnings.extend(f"{item.get('case_id')}: {warning}" for warning in item.get("warnings", []) or [])
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in sorted(dict.fromkeys(warnings)))
    lines.append("")
    return "\n".join(lines)


def summarize_data(paths: list[str | Path]) -> dict[str, Any]:
    return summarize_data_from_results([load_result(path) for path in expand_paths(paths)])


def summarize_data_from_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(results, key=lambda value: str(value.get("case_id", "")))
    average = sum(float(item.get("score", 0.0)) for item in ordered) / len(ordered) if ordered else 0.0
    cases = []
    for item in ordered:
        cases.append(
            {
                "case_id": item.get("case_id", "unknown"),
                "score": float(item.get("score", 0.0)),
                "grade": item.get("grade", "unknown"),
                "passed": bool(item.get("passed")),
                "score_by_level": item.get("score_by_level") or {},
                "score_by_component": item.get("score_by_component") or item.get("category_scores") or {},
                "l2_summary": extract_l2_summary(item),
                "warnings": item.get("warnings") or [],
            }
        )
    return {
        "case_count": len(ordered),
        "average_score": round(average, 2),
        "passed_case_count": sum(1 for item in cases if item["passed"]),
        "failed_case_count": sum(1 for item in cases if not item["passed"]),
        "cases": cases,
    }


def expand_paths(paths: list[str | Path]) -> list[Path]:
    result: list[Path] = []
    for value in paths:
        matches = [Path(path) for path in glob.glob(str(value))]
        result.extend(matches or [Path(value)])
    return [path for path in result if path.exists()]


def load_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_l1_score(item: dict[str, Any]) -> float:
    levels = item.get("level_results") or {}
    if "L1" in levels:
        return float(levels["L1"].get("score", 0.0))
    if "score_by_level" in item:
        return 0.0
    return float(item.get("score", 0.0))


def extract_l2_summary(item: dict[str, Any]) -> dict[str, Any]:
    l2 = ((item.get("level_results") or {}).get("L2") or {}).get("evaluators") or {}
    evaluator = l2.get("official_example_execution") or {}
    summary = evaluator.get("l2_summary")
    return summary if isinstance(summary, dict) else {}


def format_l2_status(item: dict[str, Any]) -> str:
    summary = extract_l2_summary(item)
    if not summary:
        return "n/a"
    counts = summary.get("execution_depth_counts") or {}
    status_counts = summary.get("status_counts") or {}
    reason_counts = summary.get("score_reasons") or {}
    parts = []
    if counts.get("live_execute"):
        parts.append(f"live_execute success {counts['live_execute']}")
    smoke_fallback = int(reason_counts.get("data_smoke_success_when_live_execute_requested") or 0)
    if smoke_fallback:
        parts.append(f"smoke_only_when_live_requested {smoke_fallback}")
    data_smoke = max(0, int(counts.get("data_smoke") or 0) - smoke_fallback)
    if data_smoke:
        parts.append(f"data_smoke success {data_smoke}")
    if counts.get("dry_run_policy_block"):
        parts.append(f"policy_block {counts['dry_run_policy_block']}")
    if counts.get("dry_run_skip"):
        parts.append(f"dry_run skip {counts['dry_run_skip']}")
    if status_counts.get("install_approval_required"):
        parts.append(f"install_approval {status_counts['install_approval_required']}")
    for status in ["install_failed", "dependencies_missing_after_install", "preflight_failed", "execution_failed", "execution_timeout", "output_validation_failed"]:
        if status_counts.get(status):
            parts.append(f"{status} {status_counts[status]}")
    if not parts:
        parts.extend(f"{key} {value}" for key, value in sorted(status_counts.items()))
    return ", ".join(parts) if parts else "n/a"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Paper2Skill benchmark evaluation JSON files.")
    parser.add_argument("--results", nargs="+", required=True, help="Evaluation JSON paths or glob patterns")
    parser.add_argument("--out", required=True, help="Markdown summary output path")
    parser.add_argument("--json-out", help="Optional machine-readable JSON summary output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    markdown = summarize_results(args.results)
    write_text(Path(args.out), markdown)
    if args.json_out:
        write_json(Path(args.json_out), summarize_data(args.results))
    print(f"Wrote benchmark summary to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
