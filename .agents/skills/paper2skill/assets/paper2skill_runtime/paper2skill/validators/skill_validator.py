from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from paper2skill.common import PROJECT_ROOT
from paper2skill.validators.adapter_review import adapter_review_mismatches, missing_explicit_adapter_mapping
from paper2skill.validators.schema_validator import validate_simple_schema


REQUIRED_FILES = [
    "SKILL.md",
    "scripts/preflight.py",
    "scripts/env_manager.py",
    "scripts/run_in_env.sh",
    "scripts/plan.py",
    "scripts/run.py",
    "scripts/validate_outputs.py",
    "scripts/adapters/__init__.py",
    "scripts/adapters/command_adapter.py",
    "scripts/adapters/python_api_adapter.py",
    "scripts/adapters/cli_adapter.py",
    "scripts/adapters/notebook_adapter.py",
    "scripts/adapters/workflow_engine_adapter.py",
    "scripts/adapters/r_script_adapter.py",
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
    "references/tutorial_catalog.yaml",
    "references/maturity.yaml",
    "references/run_trace.template.json",
    "references/evidence_summary.md",
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
    "references/contracts/algorithm_contract.yaml",
    "references/contracts/adapter_contract.yaml",
    "references/contracts/bio_contract.yaml",
    "references/contracts/environment_contract.yaml",
    "references/contracts/io_contract.yaml",
    "references/evidence_graph.json",
    "references/build_report.json",
    "assets/input_manifest_template.yaml",
    "assets/config_template.yaml",
    "assets/environment_spec.yaml",
    "assets/requirements.txt",
    "assets/environment.yml",
    "assets/env/paper2skill.environment.yml",
    "assets/env/normalization_report.json",
    "assets/official_attempt_manifest.yaml",
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

ADAPTER_STATUSES = {"dry_run_only", "verified"}
EXECUTABLE_ADAPTER_STATUSES = {"verified"}
MATURITY_LEVELS = {"L1", "L2", "L3", "L4"}


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
    _validate_yaml_contract(root / "references/contracts/algorithm_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/algorithm_skill_schema.yaml", "contracts.algorithm_contract", errors)
    _validate_yaml_contract(root / "references/contracts/adapter_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/adapter_spec_schema.yaml", "contracts.adapter_contract", errors)
    _validate_yaml_contract(root / "references/contracts/bio_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/bio_contract_schema.yaml", "contracts.bio_contract", errors)
    _validate_yaml_contract(root / "references/contracts/io_contract.yaml", PROJECT_ROOT / "paper2skill/schemas/algorithm_skill_schema.yaml", "contracts.io_contract", errors, required_only=("input_contract", "output_contract"))
    _load_yaml_mapping(root / "references/contracts/environment_contract.yaml", "contracts.environment_contract", errors)
    _validate_yaml_contract(root / "assets/environment_spec.yaml", PROJECT_ROOT / "paper2skill/schemas/environment_schema.yaml", "environment_spec", errors)
    _validate_environment_spec(root / "assets/environment_spec.yaml", errors)
    _validate_workflow_dag(root / "references/workflow_dag.json", errors)
    _validate_adapter_spec(root / "references/adapter_spec.yaml", errors)
    _validate_adapter_review(root / "references/adapter_review.yaml", errors)
    _validate_tutorial_catalog(root / "references/tutorial_catalog.yaml", errors, warnings)
    _validate_maturity(root / "references/maturity.yaml", errors)
    _validate_contract_consistency(root, errors)
    _validate_run_trace_template(root / "references/run_trace.template.json", errors)
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


def _load_yaml_mapping(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{label}: invalid YAML: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}: expected mapping")
        return {}
    return data


def _validate_tutorial_catalog(path: Path, errors: list[str], warnings: list[str]) -> None:
    catalog = _load_yaml_mapping(path, "tutorial_catalog", errors)
    if not catalog:
        return
    examples = catalog.get("examples")
    if not isinstance(examples, list) or not examples:
        errors.append("tutorial_catalog.examples: expected non-empty list")
        return
    default_example_id = catalog.get("default_example_id")
    example_ids: set[str] = set()
    for index, item in enumerate(examples):
        if not isinstance(item, dict):
            errors.append(f"tutorial_catalog.examples[{index}]: expected object")
            continue
        example_id = item.get("example_id")
        if not example_id:
            errors.append(f"tutorial_catalog.examples[{index}].example_id: missing required key")
        else:
            example_ids.add(str(example_id))
        maturity = item.get("maturity")
        if maturity is not None and maturity not in MATURITY_LEVELS:
            errors.append(f"tutorial_catalog.examples[{index}].maturity: invalid maturity level")
        adapter = item.get("adapter") if isinstance(item.get("adapter"), dict) else item.get("selected_adapter")
        if not isinstance(adapter, dict):
            errors.append(f"tutorial_catalog.examples[{index}].adapter: expected mapping")
        else:
            status = adapter.get("status")
            if status not in ADAPTER_STATUSES:
                errors.append(f"tutorial_catalog.examples[{index}].adapter.status: invalid adapter status")
        for url in _catalog_data_urls(item):
            if _invalid_data_url(url):
                errors.append(f"tutorial_catalog.examples[{index}].inputs.data_sources: non-data URL classified as data: {url}")
        if (item.get("verification") or {}).get("status") == "pass" and isinstance(adapter, dict) and adapter.get("status") != "verified":
            warnings.append(f"tutorial_catalog.examples[{index}]: passing verification should normally promote adapter.status to verified")
    if default_example_id not in example_ids:
        errors.append("tutorial_catalog.default_example_id: must match an examples[].example_id")


def _catalog_data_urls(item: dict[str, Any]) -> list[str]:
    sources = []
    inputs = item.get("inputs") if isinstance(item.get("inputs"), dict) else {}
    for candidate in [item.get("data_sources"), inputs.get("data_sources")]:
        if isinstance(candidate, list):
            sources.extend(candidate)
    urls = []
    for source in sources:
        if isinstance(source, dict) and source.get("url"):
            urls.append(str(source["url"]))
        elif isinstance(source, str):
            urls.append(source)
    return urls


def _invalid_data_url(url: str) -> bool:
    raw = url.lower().strip()
    if raw.rstrip("`]").endswith((".**", ".*", ".md", ".html", "/locally", "/locally/")):
        return True
    lowered = raw.rstrip("`].\\*")
    if "#egg=" in lowered or "git+" in lowered:
        return True
    if any(token in lowered for token in ["readthedocs", "docs.", "pytorch.org/get-started", "conda.io", "documentation"]):
        return True
    suffix = Path(lowered.split("?", 1)[0]).suffix
    return bool(suffix) and suffix not in {".h5ad", ".h5", ".hdf5", ".loom", ".rds", ".rda", ".mtx", ".csv", ".tsv", ".txt", ".fastq", ".fq", ".bam", ".sam", ".bed", ".gtf", ".gff", ".vcf"}


def _validate_maturity(path: Path, errors: list[str]) -> None:
    maturity = _load_yaml_mapping(path, "maturity", errors)
    if not maturity:
        return
    if maturity.get("level") not in MATURITY_LEVELS:
        errors.append("maturity.level: invalid maturity level")
    if not maturity.get("status"):
        errors.append("maturity.status: missing required key")


def _validate_contract_consistency(root: Path, errors: list[str]) -> None:
    algorithm_contract = _load_yaml_mapping(root / "references/algorithm_contract.yaml", "algorithm_contract", errors)
    adapter_spec = _load_yaml_mapping(root / "references/adapter_spec.yaml", "adapter_spec", errors)
    maturity = _load_yaml_mapping(root / "references/maturity.yaml", "maturity", errors)
    algorithm = algorithm_contract.get("algorithm") if isinstance(algorithm_contract.get("algorithm"), dict) else {}
    if adapter_spec and algorithm.get("adapter_status") and algorithm.get("adapter_status") != adapter_spec.get("status"):
        errors.append("algorithm_contract.algorithm.adapter_status: must match adapter_spec.status")
    if maturity and algorithm.get("maturity_level") and algorithm.get("maturity_level") != maturity.get("level"):
        errors.append("algorithm_contract.algorithm.maturity_level: must match maturity.level")


def _validate_run_trace_template(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        trace = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"run_trace.template: invalid JSON: {exc}")
        return
    if not isinstance(trace, dict):
        errors.append("run_trace.template: expected object")
        return
    for key in ["schema_version", "trace_type", "status", "output_validation", "commands", "produced_files"]:
        if key not in trace:
            errors.append(f"run_trace.template.{key}: missing required key")


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
    if status == "verified" and adapter_type == "python_api":
        if not spec.get("module"):
            errors.append("adapter_spec.module: required when python_api status is executable")
        if not spec.get("function"):
            errors.append("adapter_spec.function: required when python_api status is executable")
    if status not in ADAPTER_STATUSES:
        errors.append("adapter_spec.status: invalid adapter status")
    if status == "verified":
        verification = spec.get("verification") if isinstance(spec.get("verification"), dict) else {}
        output_validation = verification.get("output_validation") if isinstance(verification.get("output_validation"), dict) else {}
        if not _has_run_trace_evidence(spec, verification):
            errors.append("adapter_spec.verification: verified status requires run_trace evidence")
        if output_validation.get("status") != "pass":
            errors.append("adapter_spec.verification.output_validation.status: verified status requires pass")


def _validate_adapter_review(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    try:
        review = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"adapter_review: invalid YAML: {exc}")
        return
    for key in ["adapter_type", "status", "entrypoint", "command", "module", "function", "verification", "expected_outputs", "evidence", "caveats"]:
        if key not in review:
            errors.append(f"adapter_review: missing required key '{key}'")
    status = review.get("status")
    if status not in ADAPTER_STATUSES:
        errors.append("adapter_review.status: invalid adapter status")
    if "verification" in review and not isinstance(review.get("verification"), dict):
        errors.append("adapter_review.verification: expected mapping")
    for key in ["expected_outputs", "evidence", "caveats"]:
        if key in review and not isinstance(review.get(key), list):
            errors.append(f"adapter_review.{key}: expected list")
    adapter_spec = _load_adapter_spec_for_review(path)
    mapping_spec = adapter_spec or {"adapter_type": review.get("adapter_type")}
    if adapter_spec:
        if status and adapter_spec.get("status") != status:
            errors.append("adapter_review.status: must match adapter_spec.status")
        if review.get("adapter_type") and adapter_spec.get("adapter_type") != review.get("adapter_type"):
            errors.append("adapter_review.adapter_type: must match adapter_spec.adapter_type")
    for mismatch in adapter_review_mismatches(mapping_spec, review):
        if mismatch == "adapter_type" and adapter_spec:
            continue
        if mismatch in {"entrypoint", "module", "function"}:
            errors.append(f"adapter_review.{mismatch}: must match adapter_spec.{mismatch}")
        elif mismatch.startswith("command:"):
            errors.append(f"adapter_review.command: {mismatch.split(':', 1)[1]}")
        elif mismatch == "adapter_type":
            errors.append("adapter_review.adapter_type: must match adapter_spec.adapter_type")
    if status in EXECUTABLE_ADAPTER_STATUSES:
        for key in missing_explicit_adapter_mapping(mapping_spec, review):
            errors.append(f"adapter_review.{key}: required when adapter status is executable")
    if status == "verified":
        verification = review.get("verification") or {}
        output_validation = verification.get("output_validation") if isinstance(verification, dict) else {}
        if not isinstance(verification, dict) or verification.get("status") != "pass":
            errors.append("adapter_review.verification.status: verified status requires pass")
        if not isinstance(output_validation, dict) or output_validation.get("status") != "pass":
            errors.append("adapter_review.verification.output_validation.status: verified status requires pass")
        if not isinstance(verification, dict) or not _has_run_trace_evidence(review, verification):
            errors.append("adapter_review.verification: verified status requires run_trace evidence")
        if not review.get("expected_outputs"):
            errors.append("adapter_review.expected_outputs: verified status requires at least one expected output")


def _has_run_trace_evidence(data: dict[str, Any], verification: dict[str, Any]) -> bool:
    evidence = [str(item).lower() for item in data.get("evidence", []) or []]
    return verification.get("source") == "run_trace" or "run_trace" in evidence or bool(verification.get("run_trace"))


def _load_adapter_spec_for_review(review_path: Path) -> dict[str, Any]:
    spec_path = review_path.with_name("adapter_spec.yaml")
    if not spec_path.exists():
        return {}
    try:
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


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
