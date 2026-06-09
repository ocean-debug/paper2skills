from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paper2skill.evaluation.load_gold import GOLD_FILES, load_gold
from paper2skill.evaluation.schemas import VALID_TUTORIAL_SELECTION_MODES, VALID_WORKFLOW_MODES


def validate_gold(case_dir: str | Path) -> dict[str, Any]:
    bundle = load_gold(case_dir)
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(f"missing gold file: {path}" for path in bundle["missing_files"])
    gold = bundle["gold"]
    metadata = gold.get("case_metadata") or {}
    for field in ["case_id", "tool_name", "paper_title", "paper_url", "repo_url", "tutorial_urls", "primary_language", "expected_adapter_type", "expected_initial_adapter_status"]:
        if not metadata.get(field):
            errors.append(f"case_metadata missing required field: {field}")
    if metadata.get("tutorial_urls") and not isinstance(metadata["tutorial_urls"], list):
        errors.append("case_metadata.tutorial_urls must be a list")
    validate_tutorial_gold(gold.get("tutorial_selection") or {}, errors, warnings)
    validate_workflow_gold(gold.get("workflow_dag") or {}, errors, warnings)
    return {
        "case_id": bundle["case_id"],
        "passed": not errors,
        "required_gold_files": sorted(GOLD_FILES.values()),
        "errors": errors,
        "warnings": warnings,
    }


def validate_tutorial_gold(gold: dict[str, Any], errors: list[str], _warnings: list[str]) -> None:
    mode = gold.get("selection_mode")
    if mode and mode not in VALID_TUTORIAL_SELECTION_MODES:
        errors.append(f"invalid tutorial selection_mode: {mode}")
    for item in gold.get("required_tutorials") or []:
        if isinstance(item, dict) and not item.get("tutorial_id"):
            errors.append("required_tutorials item missing tutorial_id")


def validate_workflow_gold(gold: dict[str, Any], errors: list[str], _warnings: list[str]) -> None:
    mode = gold.get("workflow_mode")
    if mode and mode not in VALID_WORKFLOW_MODES:
        errors.append(f"invalid workflow_mode: {mode}")
    for workflow in gold.get("workflows") or []:
        if isinstance(workflow, dict) and not workflow.get("workflow_id"):
            errors.append("workflows item missing workflow_id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate benchmark gold YAML files.")
    parser.add_argument("--case", required=True, help="Benchmark case directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_gold(args.case)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
