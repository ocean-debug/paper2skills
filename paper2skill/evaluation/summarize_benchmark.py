from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from paper2skill.common import write_text


def summarize_results(paths: list[str | Path]) -> str:
    results = [load_result(path) for path in expand_paths(paths)]
    lines = ["# Paper2Skill Benchmark Summary", ""]
    if not results:
        lines.extend(["No evaluation results were found.", ""])
        return "\n".join(lines)
    average = sum(float(item.get("score", 0.0)) for item in results) / len(results)
    lines.append(f"- Cases: {len(results)}")
    lines.append(f"- Average score: {average:.2f}")
    lines.append("")
    lines.append("| Case | Score | Grade | Passed | Source | Dependency | Tutorial/Workflow | IO/Bio | Evidence | Adapter | Validation |")
    lines.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for item in sorted(results, key=lambda value: str(value.get("case_id", ""))):
        scores = item.get("category_scores") or {}
        lines.append(
            "| {case} | {score:.2f} | {grade} | {passed} | {source:.2f} | {dep:.2f} | {tw:.2f} | {io:.2f} | {ev:.2f} | {ad:.2f} | {val:.2f} |".format(
                case=item.get("case_id", "unknown"),
                score=float(item.get("score", 0.0)),
                grade=item.get("grade", "unknown"),
                passed="yes" if item.get("passed") else "no",
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


def expand_paths(paths: list[str | Path]) -> list[Path]:
    result: list[Path] = []
    for value in paths:
        matches = [Path(path) for path in glob.glob(str(value))]
        result.extend(matches or [Path(value)])
    return [path for path in result if path.exists()]


def load_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Paper2Skill benchmark evaluation JSON files.")
    parser.add_argument("--results", nargs="+", required=True, help="Evaluation JSON paths or glob patterns")
    parser.add_argument("--out", required=True, help="Markdown summary output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    markdown = summarize_results(args.results)
    write_text(Path(args.out), markdown)
    print(f"Wrote benchmark summary to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
