from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

from paper2skill.build_validation.skill_package import validate_skill_package
from paper2skill.common import ensure_dir, slugify, write_json
from paper2skill.generators.codex_skill_generator import build_context, generate_skill
from paper2skill.validators.skill_validator import validate_skill


BENCHMARK_LEVELS = ("L0", "L1", "L2", "L3", "L4")
DEFAULT_EVIDENCE_FILES = [
    "references/source_manifest.json",
    "references/tutorial_trace.json",
    "references/tutorial_catalog.yaml",
    "references/workflow_dag.json",
    "assets/environment_spec.yaml",
    "references/algorithm_contract.yaml",
    "references/io_contract.yaml",
    "references/bio_contract.yaml",
    "references/maturity.yaml",
    "references/evidence_graph.json",
    "references/adapter_spec.yaml",
    "references/adapter_review.yaml",
    "references/notebook_execution_policy.json",
    "references/contracts/algorithm_contract.yaml",
]


def run_benchmark(
    case_path: str | Path,
    *,
    level: str = "L1",
    skill_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    case_file = Path(case_path)
    if level not in BENCHMARK_LEVELS:
        raise ValueError(f"unknown benchmark level: {level}")
    case = load_case(case_file)
    case_id = str(case.get("case_id") or case_file.parent.name or case_file.stem)
    output_root = ensure_dir(Path(out_dir) if out_dir else Path("paper2skill_benchmark") / slugify(case_id))
    skill = Path(skill_dir) if skill_dir else build_skill_for_case(case, case_file, output_root / "skill")
    result = benchmark_result(case_id=case_id, level=level, skill=skill, case_file=case_file)
    if level == "L0":
        evaluate_l0(result, skill, case)
    elif level == "L1":
        evaluate_l0(result, skill, case)
        if result["status"] == "pass":
            evaluate_l1(result, skill, case)
    elif level in {"L2", "L3"}:
        evaluate_l0(result, skill, case)
        if result["status"] == "pass":
            evaluate_l1(result, skill, case)
        if result["status"] == "pass":
            evaluate_execution_level(result, skill, case, case_file, output_root, level)
    else:
        evaluate_l0(result, skill, case)
        if result["status"] == "pass":
            evaluate_l1(result, skill, case)
        if result["status"] == "pass":
            evaluate_agentic_level(result, case, case_file)
    result["score"] = benchmark_score(result)
    write_json(output_root / "benchmark_result.json", result)
    return result


def load_case(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"benchmark case must be a mapping: {path}")
    return data


def build_skill_for_case(case: dict[str, Any], case_file: Path, out_dir: Path) -> Path:
    inputs = case.get("inputs") or {}
    tutorials = [str(resolve_case_path(case_file, item)) for item in inputs.get("tutorials", []) or []]
    context = build_context(
        skill_name=inputs.get("skill_name") or case.get("case_id"),
        algorithm_name=inputs.get("algorithm_name") or case.get("case_id"),
        task=inputs.get("task") or "algorithm_execution",
        paper=str(resolve_case_path(case_file, inputs["paper"])) if inputs.get("paper") else None,
        repo=str(resolve_case_path(case_file, inputs["repo"])) if inputs.get("repo") else None,
        tutorials=tutorials,
        adapter_review=str(resolve_case_path(case_file, inputs["adapter_review"])) if inputs.get("adapter_review") else None,
        maturity_level=inputs.get("maturity_target") or "L1",
        strict_evidence=bool(inputs.get("strict_evidence", False)),
        no_execute_tutorials=True,
        collection_dir=out_dir.parent / ".paper2skill_collection",
    )
    return generate_skill(context, out_dir)


def benchmark_result(*, case_id: str, level: str, skill: Path, case_file: Path) -> dict[str, Any]:
    return {
        "benchmark_type": "independent_gold_standard",
        "case_id": case_id,
        "level": level,
        "status": "pass",
        "failure_layer": None,
        "skill_dir": str(skill),
        "case_path": str(case_file),
        "checks": [],
        "errors": [],
        "warnings": [],
    }


def evaluate_l0(result: dict[str, Any], skill: Path, case: dict[str, Any]) -> None:
    gold = ((case.get("gold") or {}).get("level0") or {})
    report = validate_skill_package(skill, gold=gold)
    add_check(result, "L0", "skill_package", report["passed"], report)
    if not report["passed"]:
        fail(result, "L0", "skill_package_failed")


def evaluate_l1(result: dict[str, Any], skill: Path, case: dict[str, Any]) -> None:
    validation = validate_skill(skill)
    add_check(result, "L1", "validate_skill", validation["status"] == "pass", validation)
    if validation["status"] != "pass":
        fail(result, "L1", "validate_skill_failed")
        result["errors"].extend(validation.get("errors", []))
        return
    gold = (case.get("gold") or {}).get("level1") or {}
    required_files = gold.get("required_evidence_files") or DEFAULT_EVIDENCE_FILES
    missing = [rel for rel in required_files if not (skill / rel).is_file()]
    add_check(result, "L1", "evidence_bundle", not missing, {"missing": missing, "required": required_files})
    if missing:
        fail(result, "L1", "evidence_bundle_incomplete")
        result["errors"].extend(f"missing_evidence:{item}" for item in missing)
        return
    compare_expected_yaml_field(result, "L1", skill / "references" / "adapter_spec.yaml", "adapter_type", gold.get("expected_adapter_type"))
    compare_expected_yaml_field(result, "L1", skill / "references" / "adapter_spec.yaml", "status", gold.get("expected_adapter_status"))
    compare_expected_yaml_field(result, "L1", skill / "references" / "algorithm_contract.yaml", ("algorithm", "language"), gold.get("expected_language"))
    routing_report = validate_algorithm_routing_contract(skill)
    add_check(result, "L1", "algorithm_routing_contract", routing_report["passed"], routing_report)
    if not routing_report["passed"]:
        fail(result, "L1", "routing_contract_incomplete")
        result["errors"].extend(f"routing_contract_missing:{item}" for item in routing_report["missing"])


def evaluate_execution_level(result: dict[str, Any], skill: Path, case: dict[str, Any], case_file: Path, output_root: Path, level: str) -> None:
    gold = (case.get("gold") or {}).get(level.lower()) or (case.get("gold") or {}).get(level) or {}
    manifest = gold.get("manifest")
    expected_outputs = gold.get("expected_outputs")
    if not manifest or not expected_outputs:
        fail(result, level, f"{level.lower()}_gold_execution_contract_required")
        add_check(result, level, "gold_execution_contract", False, {"manifest": manifest, "expected_outputs": expected_outputs})
        return
    manifest_path = resolve_case_path(case_file, manifest)
    execution_manifest = materialize_execution_manifest(manifest_path, output_root / level.lower() / "manifest.yaml")
    run_dir = output_root / level.lower() / "result"
    command_records = []
    stage_commands = [
        ("preflight", [sys.executable, str(skill / "scripts" / "preflight.py"), "--manifest", str(execution_manifest), "--out", str(run_dir)]),
        ("plan", [sys.executable, str(skill / "scripts" / "plan.py"), "--manifest", str(execution_manifest), "--out", str(run_dir)]),
        ("run", [sys.executable, str(skill / "scripts" / "run.py"), "--manifest", str(execution_manifest), "--out", str(run_dir)]),
        ("validate_outputs", [sys.executable, str(skill / "scripts" / "validate_outputs.py"), "--result", str(run_dir)]),
    ]
    for stage, command in stage_commands:
        completed = subprocess.run(command, cwd=skill, text=True, capture_output=True, check=False)
        record = {
            "stage": stage,
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": tail_text(completed.stdout),
            "stderr_tail": tail_text(completed.stderr),
        }
        command_records.append(record)
        if completed.returncode != 0:
            fail(result, level, f"{level.lower()}_{stage}_failed")
            add_check(result, level, stage, False, {"commands": command_records})
            return
    add_check(result, level, "execution_stages", True, {"commands": command_records})
    missing_outputs = [rel for rel in expected_outputs if not (run_dir / rel).is_file()]
    add_check(result, level, "expected_outputs", not missing_outputs, {"missing": missing_outputs, "commands": command_records})
    if missing_outputs:
        fail(result, level, f"{level.lower()}_expected_outputs_missing")
        return
    value_mismatches = compare_expected_output_values(run_dir, gold.get("expected_output_values") or {})
    if value_mismatches:
        add_check(result, level, "expected_output_values", False, {"mismatches": value_mismatches})
        fail(result, level, f"{level.lower()}_expected_output_values_mismatch")
    elif gold.get("expected_output_values"):
        add_check(result, level, "expected_output_values", True, {"checked": sorted(gold["expected_output_values"])})


def evaluate_agentic_level(result: dict[str, Any], case: dict[str, Any], case_file: Path) -> None:
    gold = (case.get("gold") or {}).get("level4") or (case.get("gold") or {}).get("L4") or {}
    trace = gold.get("agent_trace")
    required_events = gold.get("required_trace_events") or []
    if not trace or not required_events:
        fail(result, "L4", "l4_agentic_gold_trace_required")
        add_check(result, "L4", "agentic_trace_contract", False, {"agent_trace": trace, "required_trace_events": required_events})
        return
    trace_path = resolve_case_path(case_file, trace)
    events = load_json_file(trace_path).get("events", [])
    event_names = {str(event.get("event")) for event in events if isinstance(event, dict)}
    missing = [event for event in required_events if event not in event_names]
    add_check(result, "L4", "agentic_trace", not missing, {"missing_events": missing})
    if missing:
        fail(result, "L4", "l4_required_trace_events_missing")


def compare_expected_yaml_field(result: dict[str, Any], level: str, path: Path, key: str | tuple[str, ...], expected: Any) -> None:
    if expected is None:
        return
    data = load_yaml_file(path)
    actual = nested_get(data, key)
    name = ".".join(key) if isinstance(key, tuple) else key
    passed = actual == expected
    add_check(result, level, f"gold:{name}", passed, {"expected": expected, "actual": actual, "path": str(path)})
    if not passed:
        fail(result, level, f"gold_mismatch:{name}")


def validate_algorithm_routing_contract(skill: Path) -> dict[str, Any]:
    contract_path = skill / "references" / "contracts" / "algorithm_contract.yaml"
    if not contract_path.exists():
        contract_path = skill / "references" / "algorithm_contract.yaml"
    contract = load_yaml_file(contract_path)
    required_paths = [
        ("algorithm", "task"),
        ("algorithm", "domain"),
        ("algorithm", "modality"),
        ("algorithm", "adapter_status"),
        ("algorithm", "maturity_level"),
        ("applicability", "supported_task"),
        ("applicability", "domain"),
        ("applicability", "modality"),
        ("applicability", "allowed_execution_modes"),
        ("applicability", "real_execution_allowed"),
        ("applicability", "refusal_rules"),
        ("recommended_execution", "default_manifest"),
        ("recommended_execution", "entrypoints", "preflight"),
        ("recommended_execution", "entrypoints", "plan"),
        ("recommended_execution", "entrypoints", "run"),
        ("recommended_execution", "entrypoints", "validate_outputs"),
        ("recommended_execution", "real_execution_requires"),
        ("recommended_execution", "can_execute_real_data"),
    ]
    missing = [".".join(path) for path in required_paths if missing_contract_value(contract, path)]
    refusal_rules = nested_get(contract, ("applicability", "refusal_rules"))
    rule_codes = {str(item.get("code")) for item in refusal_rules or [] if isinstance(item, dict)}
    for code in ["unsupported_task", "adapter_not_verified", "bio_contract_mismatch"]:
        if code not in rule_codes:
            missing.append(f"applicability.refusal_rules.{code}")
    return {"passed": not missing, "missing": sorted(missing), "path": str(contract_path)}


def missing_contract_value(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    value = nested_get(data, path)
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def compare_expected_output_values(run_dir: Path, expected_values: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for rel, expected in expected_values.items():
        path = run_dir / rel
        actual = load_json_file(path)
        if not isinstance(expected, dict):
            mismatches.append({"path": rel, "expected": expected, "actual": actual, "reason": "expected_value_contract_must_be_mapping"})
            continue
        for key, expected_value in expected.items():
            actual_value = actual.get(key) if isinstance(actual, dict) else None
            if actual_value != expected_value:
                mismatches.append({"path": rel, "field": key, "expected": expected_value, "actual": actual_value})
    return mismatches


def materialize_execution_manifest(manifest_path: Path, out_path: Path) -> Path:
    manifest = load_yaml_file(manifest_path)
    if not manifest:
        return manifest_path
    inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
    primary = inputs.get("primary_data") if isinstance(inputs.get("primary_data"), dict) else {}
    resolve_manifest_file(primary, manifest_path.parent)
    ensure_dir(out_path.parent)
    out_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return out_path


def resolve_manifest_file(section: dict[str, Any], base_dir: Path) -> None:
    value = section.get("path")
    if not isinstance(value, str) or "://" in value:
        return
    path = Path(value)
    if path.is_absolute():
        return
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        section["path"] = str(candidate)


def add_check(result: dict[str, Any], level: str, name: str, passed: bool, details: dict[str, Any]) -> None:
    result["checks"].append({"level": level, "name": name, "passed": passed, "details": details})


def fail(result: dict[str, Any], layer: str, error: str) -> None:
    result["status"] = "fail"
    result["failure_layer"] = result.get("failure_layer") or layer
    if error not in result["errors"]:
        result["errors"].append(error)


def benchmark_score(result: dict[str, Any]) -> float:
    checks = result.get("checks", [])
    if not checks:
        return 0.0
    passed = sum(1 for check in checks if check.get("passed"))
    return round(100.0 * passed / len(checks), 2)


def resolve_case_path(case_file: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (case_file.parent / path).resolve()


def load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def nested_get(data: dict[str, Any], key: str | tuple[str, ...]) -> Any:
    if isinstance(key, str):
        return data.get(key)
    current: Any = data
    for part in key:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def tail_text(value: str, *, max_chars: int = 4000) -> str:
    return value[-max_chars:] if len(value) > max_chars else value


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run an independent Paper2Skill benchmark case.")
    parser.add_argument("--case", required=True)
    parser.add_argument("--level", default="L1", choices=BENCHMARK_LEVELS)
    parser.add_argument("--skill", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    result = run_benchmark(args.case, level=args.level, skill_dir=args.skill, out_dir=args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
