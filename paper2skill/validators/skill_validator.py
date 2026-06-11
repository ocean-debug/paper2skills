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
    "scripts/run_in_env.sh",
    "scripts/qsub_template.sh",
    "scripts/plan.py",
    "scripts/run.py",
    "scripts/validate_outputs.py",
    "scripts/adapters/__init__.py",
    "scripts/adapters/python_api_adapter.py",
    "scripts/adapters/cli_adapter.py",
    "scripts/adapters/notebook_adapter.py",
    "scripts/adapters/r_script_adapter.R",
    "references/evidence_report.md",
    "references/paper_summary.md",
    "references/repo_summary.md",
    "references/api_reference.md",
    "references/tutorial_trace.md",
    "references/tutorial_trace.json",
    "references/workflow_dag.json",
    "references/tutorial_candidates.json",
    "references/tutorial_scanner_report.json",
    "references/environment_report.json",
    "references/source_manifest.json",
    "references/paper_evidence.json",
    "references/repo_evidence.json",
    "references/adapter_spec.yaml",
    "references/adapter_review.yaml",
    "references/notebook_execution_policy.json",
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
    "assets/env/paper2skill.environment.yml",
    "assets/env/normalization_report.json",
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

ADAPTER_STATUSES = {"demo_only", "candidate", "blocked", "ready", "reviewed", "verified"}
EXECUTABLE_ADAPTER_STATUSES = {"ready", "reviewed", "verified"}
READY_DRY_RUN_STATUSES = {"pass", "trusted_fixture"}


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
    _validate_yaml_contract(root / "references/adapter_spec.yaml", PROJECT_ROOT / "paper2skill/schemas/adapter_spec_schema.yaml", "adapter_spec", errors)
    _validate_yaml_contract(root / "references/bio_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/bio_contract_schema.yaml", "bio_contract", errors)
    _validate_yaml_contract(root / "references/io_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/algorithm_skill_schema.yaml", "io_contract", errors, required_only=("input_contract", "output_contract"))
    _validate_yaml_contract(root / "assets/environment_spec.yaml", PROJECT_ROOT / "paper2skill/schemas/environment_schema.yaml", "environment_spec", errors)
    _validate_environment_spec(root / "assets/environment_spec.yaml", errors)
    _validate_workflow_dag(root / "references/workflow_dag.json", errors)
    _validate_adapter_spec(root / "references/adapter_spec.yaml", errors)
    _validate_adapter_review(root / "references/adapter_review.yaml", errors)
    trace_path = root / "references/tutorial_trace.json"
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            if not trace.get("workflow_steps"):
                warnings.append("tutorial_trace.json has no workflow steps")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid tutorial_trace.json: {exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors, "warnings": warnings}


def _validate_yaml_contract(contract_path: Path, schema_path: Path, label: str, errors: list[str], required_only: tuple[str, ...] | None = None) -> None:
    if not contract_path.exists() or not schema_path.exists():
        return
    try:
        data = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{label}: invalid YAML: {exc}")
        return
    if required_only is not None:
        for key in required_only:
            if key not in data:
                errors.append(f"{label}: missing required key '{key}'")
        return
    errors.extend(validate_simple_schema(data, schema, label))


def _validate_workflow_dag(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"workflow_dag: invalid JSON: {exc}")
        return
    if not isinstance(data.get("nodes"), list):
        errors.append("workflow_dag.nodes: expected list")
        return
    node_ids = set()
    for index, node in enumerate(data["nodes"]):
        if not isinstance(node, dict):
            errors.append(f"workflow_dag.nodes[{index}]: expected object")
            continue
        if not node.get("step_id"):
            errors.append(f"workflow_dag.nodes[{index}]: missing required key 'step_id'")
        if not node.get("type"):
            errors.append(f"workflow_dag.nodes[{index}]: missing required key 'type'")
        if node.get("step_id"):
            node_ids.add(node["step_id"])
    for index, edge in enumerate(data.get("edges", []) or []):
        if edge.get("from") not in node_ids:
            errors.append(f"workflow_dag.edges[{index}]: unknown from node {edge.get('from')!r}")
        if edge.get("to") not in node_ids:
            errors.append(f"workflow_dag.edges[{index}]: unknown to node {edge.get('to')!r}")


def _validate_adapter_spec(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"adapter_spec: invalid YAML: {exc}")
        return
    status = spec.get("status")
    adapter_type = spec.get("adapter_type")
    if status in {"ready", "reviewed", "verified"} and adapter_type == "python_api":
        if not spec.get("module"):
            errors.append("adapter_spec.module: required when python_api status is executable")
        if not spec.get("function"):
            errors.append("adapter_spec.function: required when python_api status is executable")
    if status == "demo_only" and adapter_type != "demo_only":
        errors.append("adapter_spec.status: demo_only status requires demo_only adapter_type")


def _validate_adapter_review(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        review = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"adapter_review: invalid YAML: {exc}")
        return
    for key in ["adapter_type", "status", "entrypoint", "command", "module", "function", "human_approved", "dry_run", "expected_outputs", "evidence", "caveats"]:
        if key not in review:
            errors.append(f"adapter_review: missing required key '{key}'")
    status = review.get("status")
    if status not in ADAPTER_STATUSES:
        errors.append("adapter_review.status: invalid adapter status")
    if review.get("human_approved") is not None and not isinstance(review.get("human_approved"), bool):
        errors.append("adapter_review.human_approved: expected boolean")
    if "dry_run" in review and not isinstance(review.get("dry_run"), dict):
        errors.append("adapter_review.dry_run: expected mapping")
    for key in ["expected_outputs", "evidence", "caveats"]:
        if key in review and not isinstance(review.get(key), list):
            errors.append(f"adapter_review.{key}: expected list")
    command = review.get("command")
    if isinstance(command, str) and ("\n" in command or "\r" in command):
        errors.append("adapter_review.command: must not contain newlines")
    adapter_spec = _load_adapter_spec_for_review(path)
    if adapter_spec:
        if status and adapter_spec.get("status") != status:
            errors.append("adapter_review.status: must match adapter_spec.status")
        if review.get("adapter_type") and adapter_spec.get("adapter_type") != review.get("adapter_type"):
            errors.append("adapter_review.adapter_type: must match adapter_spec.adapter_type")
        for key in ["entrypoint", "command", "module", "function"]:
            expected = adapter_spec.get(key)
            approved = review.get(key)
            if expected and approved and expected != approved:
                errors.append(f"adapter_review.{key}: must match adapter_spec.{key}")
    if status in EXECUTABLE_ADAPTER_STATUSES:
        for key in _required_adapter_review_mapping_keys(review.get("adapter_type")):
            if _missing_adapter_review_mapping_value(review.get(key)):
                errors.append(f"adapter_review.{key}: required when adapter status is executable")
    if status == "reviewed" and review.get("human_approved") is not True:
        errors.append("adapter_review.human_approved: required when adapter status is reviewed")
    if status in {"ready", "verified"}:
        dry_run = review.get("dry_run") or {}
        if not isinstance(dry_run, dict) or dry_run.get("status") not in READY_DRY_RUN_STATUSES:
            errors.append("adapter_review.dry_run.status: ready or verified status requires pass or trusted_fixture")
    if status == "verified":
        output_validation = review.get("output_validation") or {}
        if not isinstance(output_validation, dict) or output_validation.get("status") != "pass":
            errors.append("adapter_review.output_validation.status: verified status requires pass")
        if not review.get("expected_outputs"):
            errors.append("adapter_review.expected_outputs: verified status requires at least one expected output")


def _load_adapter_spec_for_review(review_path: Path) -> dict[str, Any]:
    spec_path = review_path.with_name("adapter_spec.yaml")
    if not spec_path.exists():
        return {}
    try:
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _required_adapter_review_mapping_keys(adapter_type: str | None) -> list[str]:
    if adapter_type == "python_api":
        return ["adapter_type", "entrypoint", "module", "function"]
    if adapter_type in {"cli", "workflow_engine"}:
        return ["adapter_type", "entrypoint", "command"]
    if adapter_type in {"notebook", "r_script"}:
        return ["adapter_type", "entrypoint"]
    return ["adapter_type"]


def _missing_adapter_review_mapping_value(value: Any) -> bool:
    return not isinstance(value, str) or value == ""


def _validate_environment_spec(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"environment_spec: invalid YAML: {exc}")
        return
    python_packages = ((spec.get("python") or {}).get("packages") or [])
    for index, item in enumerate(python_packages):
        if not isinstance(item, dict):
            errors.append(f"environment_spec.python.packages[{index}]: expected object")
            continue
        if not item.get("spec"):
            errors.append(f"environment_spec.python.packages[{index}]: missing required key 'spec'")
        if item.get("required") is not None and not isinstance(item.get("required"), bool):
            errors.append(f"environment_spec.python.packages[{index}].required: expected boolean")
    r_packages = ((spec.get("r") or {}).get("packages") or [])
    for index, item in enumerate(r_packages):
        if not isinstance(item, dict):
            errors.append(f"environment_spec.r.packages[{index}]: expected object")
            continue
        if not item.get("name"):
            errors.append(f"environment_spec.r.packages[{index}]: missing required key 'name'")
        if item.get("required") is not None and not isinstance(item.get("required"), bool):
            errors.append(f"environment_spec.r.packages[{index}].required: expected boolean")
