from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from paper2skill.generators.codex_skill_generator import build_context, generate_skill
from paper2skill.validators.skill_validator import validate_skill


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    root: Path
    manifest: dict[str, Any]


def load_cases(cases_root: Path) -> list[BenchmarkCase]:
    cases = []
    for manifest_path in sorted(cases_root.glob("*/case.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        cases.append(BenchmarkCase(case_id=manifest["id"], root=manifest_path.parent, manifest=manifest))
    return cases


def run_case(case: BenchmarkCase, tmp_path: Path) -> None:
    out = build_case_skill(case, tmp_path)
    bundle = load_bundle(out)
    assert_expected(case, out, bundle)


def build_case_skill(case: BenchmarkCase, tmp_path: Path) -> Path:
    inputs = case.manifest["inputs"]
    build = case.manifest.get("build", {})
    tutorials = [case.root / value for value in inputs.get("tutorials", [])]
    adapter_review = build.get("adapter_review")
    context = build_context(
        skill_name=case.case_id,
        algorithm_name=case.case_id,
        paper=str(case.root / inputs["paper"]),
        repo=str(case.root / inputs["repo"]),
        tutorials=[str(path) for path in tutorials],
        no_execute_tutorials=build.get("no_execute_tutorials", True),
        strict_evidence=build.get("strict_evidence", False),
        adapter_review=str(case.root / adapter_review) if adapter_review else None,
    )
    return generate_skill(context, tmp_path / f"{case.case_id}_skill")


def load_bundle(skill_dir: Path) -> dict[str, Any]:
    refs = skill_dir / "references"
    assets = skill_dir / "assets"
    return {
        "source_manifest": load_json(refs / "source_manifest.json"),
        "paper_sections": load_json(refs / "paper_sections.json"),
        "repo_index": load_json(refs / "repo_index.json"),
        "tutorial_candidates": load_json(refs / "tutorial_candidates.json"),
        "tutorial_trace": load_json(refs / "tutorial_trace.json"),
        "workflow_dag": load_json(refs / "workflow_dag.json"),
        "environment_spec": load_yaml(assets / "environment_spec.yaml"),
        "io_contract": load_yaml(refs / "io_contract.yaml"),
        "bio_contract": load_yaml(refs / "bio_contract.yaml"),
        "evidence_graph": load_json(refs / "evidence_graph.json"),
        "adapter_spec": load_yaml(refs / "adapter_spec.yaml"),
        "adapter_review": load_yaml(refs / "adapter_review.yaml"),
        "notebook_execution_policy": load_json(refs / "notebook_execution_policy.json"),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def assert_expected(case: BenchmarkCase, skill_dir: Path, bundle: dict[str, Any]) -> None:
    expected = case.manifest["expected"]
    if expected.get("validate_skill") == "pass":
        result = validate_skill(skill_dir)
        assert result["status"] == "pass", f"{case.case_id}: validate_skill failed: {result}"
    for rel in expected.get("generated_files", []):
        assert (skill_dir / rel).exists(), f"{case.case_id}: missing generated file {rel}"
    assert_source_collection(case, bundle, expected.get("source_collection", {}))
    assert_dependencies(case, bundle["environment_spec"], expected.get("dependencies", {}))
    assert_tutorial(case, bundle["tutorial_trace"], expected.get("tutorial", {}))
    assert_workflow(case, bundle["workflow_dag"], expected.get("workflow", {}))
    assert_io_contract(case, bundle["io_contract"], expected.get("io_contract", {}))
    assert_bio_contract(case, bundle["bio_contract"], expected.get("bio_contract", {}))
    assert_evidence_graph(case, bundle["evidence_graph"], expected.get("evidence_graph", {}))
    assert_adapter(case, bundle["adapter_spec"], expected.get("adapter", {}))
    assert_notebook_policy(case, bundle["notebook_execution_policy"], expected.get("notebook_policy", {}))
    if expected.get("blocked_non_demo_run"):
        assert_blocked_non_demo_run(case, skill_dir, expected["blocked_non_demo_run"])


def assert_source_collection(case: BenchmarkCase, bundle: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    assert len(bundle["paper_sections"]) >= expected.get("paper_sections_min", 0), f"{case.case_id}: too few paper sections"
    for needle in expected.get("repo_index_contains", []):
        assert json_contains(bundle["repo_index"], needle), f"{case.case_id}: repo index missing {needle}"
    for needle in expected.get("tutorial_candidates_contains", []):
        assert (
            json_contains(bundle["tutorial_candidates"], needle)
            or json_contains(bundle["tutorial_trace"], needle)
            or json_contains(bundle["source_manifest"], needle)
        ), f"{case.case_id}: selected tutorial evidence missing {needle}"


def assert_dependencies(case: BenchmarkCase, env: dict[str, Any], expected: dict[str, Any]) -> None:
    python_names = {item.get("name") for item in ((env.get("python") or {}).get("packages") or [])}
    r_names = {item.get("name") for item in ((env.get("r") or {}).get("packages") or [])}
    optional_text = json.dumps(
        {
            "optional": env.get("optional", {}),
            "optional_dependencies": env.get("optional_dependencies", {}),
        },
        sort_keys=True,
    )
    for name in expected.get("python_required", []):
        assert name in python_names, f"{case.case_id}: missing required Python dependency {name}"
    for name in expected.get("python_absent", []):
        assert name not in python_names, f"{case.case_id}: unexpected required Python dependency {name}"
    for name in expected.get("r_required", []):
        assert name in r_names, f"{case.case_id}: missing required R dependency {name}"
    for name in expected.get("r_absent", []):
        assert name not in r_names, f"{case.case_id}: unexpected required R dependency {name}"
    for name in expected.get("optional_contains", []):
        assert name in optional_text, f"{case.case_id}: optional dependency evidence missing {name}"


def assert_tutorial(case: BenchmarkCase, trace: dict[str, Any], expected: dict[str, Any]) -> None:
    for needle in expected.get("paths_include", []):
        assert json_contains(trace.get("tutorials", []), needle), f"{case.case_id}: tutorial trace missing {needle}"
    if "workflow_steps_min" in expected:
        assert len(trace.get("workflow_steps", [])) >= expected["workflow_steps_min"], f"{case.case_id}: too few workflow steps"


def assert_workflow(case: BenchmarkCase, dag: dict[str, Any], expected: dict[str, Any]) -> None:
    nodes = dag.get("nodes", [])
    types = [node.get("type") for node in nodes]
    for step_type in expected.get("step_types_include", []):
        assert step_type in types, f"{case.case_id}: workflow missing step type {step_type}; got {types}"
    ordered = expected.get("ordered_step_types")
    if ordered:
        assert is_subsequence(ordered, types), f"{case.case_id}: workflow types {types} do not contain ordered sequence {ordered}"
    if "edges_min" in expected:
        assert len(dag.get("edges", [])) >= expected["edges_min"], f"{case.case_id}: too few workflow edges"
    for state in expected.get("object_states", []):
        assert any_object_state(nodes, state["object"], state["key"], state["value"]), f"{case.case_id}: missing object state {state}"


def assert_io_contract(case: BenchmarkCase, contract: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    primary = (((contract.get("input_contract") or {}).get("required") or {}).get("primary_data") or {})
    if "primary_format" in expected:
        assert field_value(primary.get("format")) == expected["primary_format"], f"{case.case_id}: unexpected primary format"
    for key, value in expected.get("metadata_keys", {}).items():
        actual = field_value(((primary.get("metadata_keys") or {}).get(key) or {}))
        assert actual == value, f"{case.case_id}: metadata key {key} expected {value}, got {actual}"


def assert_bio_contract(case: BenchmarkCase, contract: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    bio = contract.get("bio_contract") or {}
    if "modality" in expected:
        assert field_value(((bio.get("modality") or {}).get("primary") or {})) == expected["modality"], f"{case.case_id}: unexpected modality"
    if "matrix_state" in expected:
        state = field_value(((bio.get("input_matrix_state") or {}).get("raw_counts_required") or {}))
        transformations = (bio.get("input_matrix_state") or {}).get("matrix_transformations") or []
        assert expected["matrix_state"] == state or expected["matrix_state"] in transformations, f"{case.case_id}: missing matrix state {expected['matrix_state']}"
    for key in expected.get("modality_contracts_include", []):
        assert key in (bio.get("modality_contracts") or {}), f"{case.case_id}: missing modality contract {key}"


def assert_evidence_graph(case: BenchmarkCase, graph: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    assert len(graph.get("items", [])) >= expected.get("min_items", 0), f"{case.case_id}: too few evidence items"
    source_types = {item.get("source_type") for item in graph.get("items", [])}
    for source_type in expected.get("source_types_include", []):
        assert source_type in source_types, f"{case.case_id}: missing evidence source type {source_type}"
    if "claims_min" in expected:
        assert len(graph.get("claims", [])) >= expected["claims_min"], f"{case.case_id}: too few evidence claims"


def assert_adapter(case: BenchmarkCase, adapter: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    if "type" in expected:
        assert adapter.get("adapter_type") == expected["type"], f"{case.case_id}: unexpected adapter type {adapter}"
    if "status" in expected:
        assert adapter.get("status") == expected["status"], f"{case.case_id}: unexpected adapter status {adapter}"


def assert_notebook_policy(case: BenchmarkCase, policy: dict[str, Any], expected: dict[str, Any]) -> None:
    if not expected:
        return
    for risk in expected.get("risks_include", []):
        assert risk in policy.get("risks", []), f"{case.case_id}: missing notebook risk {risk}"
    magics = {item.get("magic", "").lower() for item in policy.get("cell_magics", [])}
    for magic in expected.get("cell_magics_include", []):
        assert magic.lower() in magics, f"{case.case_id}: missing notebook cell magic {magic}"
    if "parameter_cells_min" in expected:
        assert len(policy.get("parameter_cells", [])) >= expected["parameter_cells_min"], f"{case.case_id}: too few parameter cells"


def assert_blocked_non_demo_run(case: BenchmarkCase, skill_dir: Path, expected: dict[str, Any]) -> None:
    manifest = skill_dir / "benchmark_run_manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "inputs": {
                    "primary_data": {"path": "assets/demo_input.csv", "format": "csv", "exists": True},
                    "algorithm": {"mode": "run", "parameters": {}},
                },
                "environment": {"install_policy": "ask"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = skill_dir / "benchmark_run_result"
    result = subprocess.run([sys.executable, str(skill_dir / "scripts" / "run.py"), "--manifest", str(manifest), "--out", str(out)], text=True, capture_output=True, check=False)
    assert result.returncode == expected.get("returncode", 2), f"{case.case_id}: unexpected run result {result.returncode}\n{result.stdout}\n{result.stderr}"
    run_result = load_json(out / "result.json")
    assert run_result.get("status") == expected["status"], f"{case.case_id}: unexpected blocked run status {run_result}"


def field_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def json_contains(value: Any, needle: str) -> bool:
    return needle in json.dumps(value, sort_keys=True)


def is_subsequence(expected: list[str], actual: list[str]) -> bool:
    position = 0
    for value in actual:
        if position < len(expected) and value == expected[position]:
            position += 1
    return position == len(expected)


def any_object_state(nodes: list[dict[str, Any]], object_name: str, key: str, value: Any) -> bool:
    for node in nodes:
        state = (node.get("object_state_after") or {}).get(object_name)
        if isinstance(state, dict) and state.get(key) == value:
            return True
    return False
