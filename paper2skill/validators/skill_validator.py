from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from paper2skill.common import PROJECT_ROOT
from paper2skill.validators.schema_validator import validate_simple_schema


REQUIRED_FILES = [
    "SKILL.md",
    "scripts/preflight.py",
    "scripts/env_manager.py",
    "scripts/plan.py",
    "scripts/run.py",
    "scripts/validate_outputs.py",
    "references/evidence_report.md",
    "references/paper_summary.md",
    "references/repo_summary.md",
    "references/api_reference.md",
    "references/tutorial_trace.md",
    "references/tutorial_trace.json",
    "references/tutorial_candidates.json",
    "references/tutorial_scanner_report.json",
    "references/environment_report.json",
    "references/source_manifest.json",
    "references/paper_evidence.json",
    "references/repo_evidence.json",
    "references/paper.md",
    "references/paper_sections.json",
    "references/paper_parser_report.json",
    "references/repo_manifest.json",
    "references/repo_index.json",
    "references/install_plan.md",
    "references/algorithm_contract.yaml",
    "references/bio_contract.yaml",
    "references/io_contract.yaml",
    "references/evidence_graph.json",
    "references/build_report.json",
    "assets/input_manifest_template.yaml",
    "assets/config_template.yaml",
    "assets/environment_spec.yaml",
    "assets/requirements.txt",
    "assets/environment.yml",
    "assets/demo_input_manifest.yaml",
    "tests/test_preflight.py",
    "tests/test_environment.py",
    "tests/test_plan.py",
    "tests/test_output_contract.py",
    "agents/openai.yaml",
]

REQUIRED_SKILL_SECTIONS = [
    "## What this skill does",
    "## When to use",
    "## When not to use",
    "## Required inputs",
    "## Input state requirements",
    "## Environment policy",
    "## Preflight workflow",
    "## Planning workflow",
    "## Execution workflow",
    "## Output contract",
    "## Validation workflow",
    "## Interpretation boundary",
    "## Failure modes",
    "## Evidence sources",
]


def validate_skill(skill_dir: str | Path) -> dict[str, Any]:
    root = Path(skill_dir)
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"missing required file: {rel}")
    skill_md = root / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        for section in REQUIRED_SKILL_SECTIONS:
            if section not in text:
                errors.append(f"SKILL.md missing section: {section}")
        if "Do not install anything unless the user explicitly approves" not in text:
            errors.append("SKILL.md missing explicit install confirmation policy")
    _validate_yaml_contract(root / "references/algorithm_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/algorithm_skill_schema.yaml", "algorithm_contract", errors)
    _validate_yaml_contract(root / "references/bio_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/bio_contract_schema.yaml", "bio_contract", errors)
    trace_path = root / "references/tutorial_trace.json"
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            if not trace.get("workflow_steps"):
                warnings.append("tutorial_trace.json has no workflow steps")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid tutorial_trace.json: {exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors, "warnings": warnings}


def _validate_yaml_contract(contract_path: Path, schema_path: Path, label: str, errors: list[str]) -> None:
    if not contract_path.exists() or not schema_path.exists():
        return
    try:
        data = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{label}: invalid YAML: {exc}")
        return
    errors.extend(validate_simple_schema(data, schema, label))
