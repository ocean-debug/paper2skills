from __future__ import annotations

import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import yaml

from paper2skill.build_validation.skill_package import validate_skill_package
from paper2skill.collectors.path_sanitizer import public_data
from paper2skill.compiler import annotate_run_trace_promotion, ingest_run_directory, promote_from_run_trace, update_algorithm_contract_after_promotion


VALIDATION_DEPTHS = ("dry_run", "data_smoke", "live_execute")
EXECUTABLE_ADAPTER_STATUSES = {"verified"}
BUILD_VALIDATION_TYPE = "build_time_self_check"
DATA_SMOKE_KINDS = {"minimal", "official_minimal"}
LIVE_EXECUTE_KINDS = {"official_example"}


def validate_build(
    skill_dir: str | Path,
    *,
    validation_depth: str = "dry_run",
    manifest: str | Path | None = None,
    result_dir: str | Path | None = None,
    timeout_seconds: int = 600,
    example_id: str | None = None,
    env_prefix: str | Path | None = None,
    python_executable: str | Path | None = None,
    example_data_cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    depth = normalize_validation_depth(validation_depth)
    root = Path(skill_dir).resolve()
    package = validate_skill_package(root)
    preflight_plan = file_status(root / "scripts" / "preflight.py")
    install_plan = install_plan_status(root)
    execution_plan = file_status(root / "scripts" / "run.py")
    policy = {
        "package_structure": package["passed"],
        "preflight_plan": preflight_plan["present"],
        "install_plan": install_plan["present"],
        "execution_plan": execution_plan["present"],
    }
    check_passed = all(policy.values())
    report = {
        "validation_type": BUILD_VALIDATION_TYPE,
        "validation_depth": depth,
        "self_check_status": "pass" if check_passed else "fail",
        "passed": check_passed,
        "diagnostic_only": True,
        "package_structure": package,
        "policy_safety": {
            "notebook_policy_safe": metric_passed(package, "notebook_policy_safe"),
            "install_policy_safe": metric_passed(package, "install_policy_safe"),
            "path_leakage_absent": metric_passed(package, "path_leakage_absent"),
        },
        "preflight_plan_status": preflight_plan,
        "install_plan_status": install_plan,
        "execution_plan_status": execution_plan,
        "review_gate": {"required": depth in {"data_smoke", "live_execute"}, "passed": depth == "dry_run", "checks": []},
        "example_id": example_id,
        "execution": {"status": "not_run", "commands": []},
        "repair_actions": [],
        "warnings": [],
        "errors": [],
    }
    if not check_passed:
        report["status"] = "fail"
        report["errors"].extend(collect_dry_run_errors(report))
        return finalize_report(report, root)
    if depth == "dry_run":
        report["status"] = "pass"
        return finalize_report(report, root)

    gate = verification_execution_gate(root, depth=depth, manifest=manifest, example_id=example_id)
    report["review_gate"] = gate
    if not gate["passed"]:
        report["passed"] = False
        report["self_check_status"] = "blocked"
        report["status"] = gate["status"]
        report["errors"].extend(gate["errors"])
        report["warnings"].append(f"{depth} build validation requires a runnable generated adapter, input manifest, and output contract.")
        return finalize_report(report, root)

    execution = run_verification_validation(
        root,
        depth=depth,
        validation_manifest=gate["validation_manifest"],
        input_manifest=gate["input_manifest"],
        manifest_data=gate["manifest_data"],
        example_id=gate.get("example_id"),
        result_dir=result_dir,
        timeout_seconds=timeout_seconds,
        env_prefix=env_prefix,
        python_executable=python_executable,
        example_data_cache_dir=example_data_cache_dir,
    )
    report["execution"] = execution
    report["passed"] = execution["status"] == "pass"
    report["self_check_status"] = execution["status"]
    report["status"] = execution["status"]
    if execution["status"] != "pass":
        report["errors"].append(execution.get("failure_code") or f"{depth}_execution_failed")
    else:
        mark_verified(root, execution=execution, gate=gate)
    return finalize_report(report, root)


def normalize_validation_depth(value: str) -> str:
    depth = str(value or "").strip()
    if depth not in VALIDATION_DEPTHS:
        raise ValueError(f"unknown validation depth: {depth}")
    return depth


def finalize_report(report: dict[str, Any], root: Path) -> dict[str, Any]:
    report.pop("benchmark_score", None)
    return public_data(report, root)


def file_status(path: Path) -> dict[str, Any]:
    return {"present": path.is_file(), "path": str(path)}


def install_plan_status(root: Path) -> dict[str, Any]:
    candidates = [
        root / "assets" / "environment_spec.yaml",
        root / "assets" / "env" / "paper2skill.environment.yml",
        root / "assets" / "install_plan.json",
    ]
    present = [path for path in candidates if path.is_file()]
    return {"present": bool(present), "paths": [str(path) for path in present]}


def metric_passed(package_report: dict[str, Any], metric: str) -> bool:
    return float((package_report.get("metrics") or {}).get(metric, 0.0)) >= 1.0


def collect_dry_run_errors(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    package = report.get("package_structure") or {}
    for item in package.get("missing_items", []) or []:
        errors.append(f"missing_required_item:{item}")
    for item in package.get("mismatched_items", []) or []:
        field = item.get("field", "policy")
        errors.append(f"policy_mismatch:{field}")
    for key in ["preflight_plan_status", "install_plan_status", "execution_plan_status"]:
        status = report.get(key) or {}
        if not status.get("present"):
            errors.append(f"{key}:missing")
    return errors


def verification_execution_gate(root: Path, *, depth: str, manifest: str | Path | None, example_id: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    catalog = read_catalog_reference(root)
    generated_manifest_error: str | None = None
    try:
        manifest_path = resolve_manifest(root, manifest) or generated_validation_manifest(root, depth=depth, example_id=example_id)
    except ValueError as exc:
        generated_manifest_error = str(exc)
        manifest_path = None
    manifest_data: dict[str, Any] = {}
    manifest_errors: list[str] = []
    input_manifest_path: Path | None = None
    manifest_base = manifest_path.parent if manifest_path else root
    if manifest_path and manifest_path.is_file():
        manifest_data, manifest_errors = read_yaml_mapping(manifest_path)
        if manifest_errors:
            errors.extend(manifest_errors)
        input_manifest_path = resolve_referenced_path(root, manifest_base, manifest_data.get("manifest_path"))
    if generated_manifest_error:
        errors.append(generated_manifest_error)
    spec = read_yaml_reference(root / "references" / "adapter_spec.yaml")
    selected_example_id = manifest_data.get("example_id") or example_id
    selected_example = {}
    try:
        selected_example = select_example(catalog, str(selected_example_id) if selected_example_id else None)
        selected_example_id = selected_example.get("example_id") or selected_example_id
    except ValueError as exc:
        selected_example_id = str(selected_example_id)
        errors.append(str(exc))
    example_adapter = selected_example.get("adapter") if isinstance(selected_example.get("adapter"), dict) else {}
    adapter_status = str(example_adapter.get("status") or "dry_run_only")
    expected_outputs = manifest_data.get("expected_outputs") if isinstance(manifest_data.get("expected_outputs"), list) else []
    expected_output_values = manifest_data.get("expected_output_values")

    data_kind = str(manifest_data.get("data_kind") or "")
    add_gate_check(checks, errors, "validation_manifest_present", manifest_path is not None and manifest_path.is_file(), "validation_manifest_required")
    if manifest_path is not None and manifest_path.is_file():
        add_gate_check(checks, errors, "validation_manifest_loadable", not manifest_errors, "validation_manifest_invalid")
        if not manifest_errors:
            add_gate_check(checks, errors, "validation_type_build_time", manifest_data.get("validation_type") == BUILD_VALIDATION_TYPE, "validation_manifest.validation_type_invalid")
            add_gate_check(checks, errors, "input_manifest_declared", bool(manifest_data.get("manifest_path")), "validation_manifest.manifest_path_required")
            add_gate_check(checks, errors, "input_manifest_present", input_manifest_path is not None and input_manifest_path.is_file(), "validation_manifest.manifest_path_not_found")
            add_gate_check(checks, errors, "expected_outputs_declared", bool(expected_outputs), "validation_manifest.expected_outputs_required")
            if expected_output_values is not None:
                add_gate_check(checks, errors, "expected_output_values_mapping", isinstance(expected_output_values, dict), "validation_manifest.expected_output_values_must_be_mapping")
            if depth == "data_smoke":
                add_gate_check(checks, errors, "data_kind_minimal", data_kind in DATA_SMOKE_KINDS, "validation_manifest.data_kind_must_be_minimal")
            if depth == "live_execute":
                add_gate_check(checks, errors, "data_kind_official_example", data_kind in LIVE_EXECUTE_KINDS, "validation_manifest.data_kind_must_be_official_example")
    add_gate_check(checks, errors, "adapter_present", bool(spec.get("adapter_type")), "verification_adapter_required")
    add_gate_check(checks, errors, "selected_example_declared", bool(selected_example), "selected_example_not_found")

    return {
        "required": True,
        "passed": not errors,
        "status": "pass" if not errors else "blocked_verification_required",
        "validation_manifest": str(manifest_path) if manifest_path else None,
        "input_manifest": str(input_manifest_path) if input_manifest_path else None,
        "manifest_data": public_data(manifest_data, root) if manifest_data else {},
        "data_kind": data_kind or None,
        "example_id": selected_example_id,
        "expected_outputs": expected_outputs,
        "expected_output_values_declared": isinstance(expected_output_values, dict) and bool(expected_output_values),
        "adapter_status": adapter_status or "not_confirmed",
        "checks": checks,
        "errors": errors,
    }


def resolve_manifest(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        candidates = [root / path, Path.cwd() / path]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return path if path.is_file() else None


def generated_validation_manifest(root: Path, *, depth: str, example_id: str | None) -> Path | None:
    input_manifest = root / "assets" / "official_attempt_manifest.yaml"
    if not input_manifest.is_file():
        input_manifest = root / "assets" / "input_manifest_template.yaml"
    if not input_manifest.is_file():
        return None
    catalog = read_catalog_reference(root)
    selected = select_example(catalog, example_id)
    output_contract = selected.get("output_contract") if isinstance(selected.get("output_contract"), dict) else {}
    expected_outputs = list(output_contract.get("required_files") or selected.get("expected_outputs") or ["results/summary.json"])
    data_kind = str(selected.get("data_kind") or ("minimal" if depth == "data_smoke" else "official_example"))
    manifest_data = {
        "validation_type": BUILD_VALIDATION_TYPE,
        "validation_depth": depth,
        "data_kind": data_kind,
        "example_id": selected.get("example_id") or example_id or catalog.get("default_example_id"),
        "manifest_path": str(input_manifest.relative_to(root)).replace("\\", "/"),
        "expected_outputs": expected_outputs,
        "output_contract": output_contract,
        "official_example": {
            "source": selected.get("source"),
            "scenario": selected.get("scenario"),
            "data_sources": catalog_data_sources(selected),
        },
    }
    path = root / "build_validation" / f"{depth}_validation_manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest_data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def select_example(catalog: dict[str, Any], example_id: str | None) -> dict[str, Any]:
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    if example_id:
        for item in examples:
            if isinstance(item, dict) and item.get("example_id") == example_id:
                return item
        raise ValueError(f"unknown_example_id:{example_id}")
    target = catalog.get("default_example_id")
    for item in examples:
        if isinstance(item, dict) and item.get("example_id") == target:
            return item
    return examples[0] if examples and isinstance(examples[0], dict) else {"example_id": target}


def resolve_referenced_path(root: Path, base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute():
        return path if path.is_file() else None
    for candidate in [base / path, root / path, Path.cwd() / path]:
        if candidate.is_file():
            return candidate
    return None


def add_gate_check(checks: list[dict[str, Any]], errors: list[str], name: str, passed: bool, error: str) -> None:
    checks.append({"name": name, "passed": passed})
    if not passed:
        errors.append(error)


def read_yaml_reference(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def read_catalog_reference(root: Path) -> dict[str, Any]:
    catalog = read_yaml_reference(root / "references" / "tutorial_catalog.yaml")
    if catalog:
        return catalog
    return read_yaml_reference(root / "references" / "examples_catalog.yaml")


def catalog_data_sources(example: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    inputs = example.get("inputs") if isinstance(example.get("inputs"), dict) else {}
    for value in [example.get("data_sources"), inputs.get("data_sources")]:
        if isinstance(value, list):
            sources.extend(item for item in value if isinstance(item, dict))
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source in sources:
        key = (str(source.get("type") or ""), str(source.get("url") or ""), str(source.get("path") or source.get("filename") or ""))
        deduped[key] = source
    return list(deduped.values())


def read_yaml_mapping(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"validation_manifest_load_error:{exc}"]
    if not isinstance(data, dict):
        return {}, ["validation_manifest_must_be_mapping"]
    return data, []


def run_verification_validation(
    root: Path,
    *,
    depth: str,
    validation_manifest: str | Path | None,
    input_manifest: str | Path | None,
    manifest_data: dict[str, Any],
    example_id: str | None,
    result_dir: str | Path | None,
    timeout_seconds: int,
    env_prefix: str | Path | None,
    python_executable: str | Path | None,
    example_data_cache_dir: str | Path | None,
) -> dict[str, Any]:
    if result_dir:
        out = Path(result_dir)
    else:
        out = root / "build_validation" / "execution_result"
    if not out.is_absolute():
        out = root / out
    input_manifest_path = Path(str(input_manifest)) if input_manifest else None
    validation_manifest_path = Path(str(validation_manifest)) if validation_manifest else None
    staged_data = stage_example_data_cache(root, manifest_data, example_data_cache_dir)
    runner = validation_python_runner(env_prefix=env_prefix, python_executable=python_executable)
    stages = [
        ("preflight", [*runner, str(root / "scripts" / "preflight.py"), "--manifest", str(input_manifest_path), "--out", str(out)]),
        ("plan", [*runner, str(root / "scripts" / "plan.py"), "--manifest", str(input_manifest_path), "--out", str(out)]),
        (
            "adapter_smoke" if depth == "data_smoke" else "full_execution",
            [
                *runner,
                str(root / "scripts" / "run.py"),
                "--manifest",
                str(input_manifest_path),
                "--out",
                str(out),
                "--verification-run",
                *([] if not example_id else ["--example-id", str(example_id)]),
            ],
        ),
        (
            "output_validation",
            [
                *runner,
                str(root / "scripts" / "validate_outputs.py"),
                "--result",
                str(out),
                "--validation-manifest",
                str(validation_manifest_path),
                *([] if not example_id else ["--example-id", str(example_id)]),
            ],
        ),
    ]
    records = []
    for stage, command in stages:
        completed = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=timeout_seconds, check=False)
        record = {
            "stage": stage,
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": tail_text(completed.stdout),
            "stderr_tail": tail_text(completed.stderr),
        }
        records.append(record)
        if completed.returncode != 0:
            report = execution_report(
                root,
                depth=depth,
                status="fail",
                out=out,
                commands=records,
                validation_manifest=validation_manifest_path,
                input_manifest=input_manifest_path,
                manifest_data=manifest_data,
                staged_data=staged_data,
            )
            report["failed_stage"] = stage
            report["failure_code"] = classify_execution_failure(stage, out)
            report["failure_reason"] = failure_reason(stage, out, record)
            return report
    return execution_report(
        root,
        depth=depth,
        status="pass",
        out=out,
        commands=records,
        validation_manifest=validation_manifest_path,
        input_manifest=input_manifest_path,
        manifest_data=manifest_data,
        staged_data=staged_data,
    )


def stage_example_data_cache(root: Path, manifest_data: dict[str, Any], cache_dir: str | Path | None) -> list[dict[str, Any]]:
    if not cache_dir:
        return []
    cache = Path(cache_dir)
    if not cache.is_dir():
        return [{"status": "missing_cache_dir", "cache_dir": str(cache)}]
    targets = example_data_filenames(manifest_data)
    if not targets:
        return []
    data_dir = root / "assets" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for filename in targets:
        source = cache / filename
        destination = data_dir / filename
        if not source.is_file():
            records.append({"status": "missing", "filename": filename, "cache_dir": str(cache)})
            continue
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        try:
            destination.hardlink_to(source)
            mode = "hardlink"
        except OSError:
            shutil.copy2(source, destination)
            mode = "copy"
        records.append({"status": "staged", "filename": filename, "source": str(source), "destination": str(destination), "mode": mode, "bytes": destination.stat().st_size})
    return records


def example_data_filenames(manifest_data: dict[str, Any]) -> list[str]:
    filenames: list[str] = []
    official = manifest_data.get("official_example") if isinstance(manifest_data.get("official_example"), dict) else {}
    for source in official.get("data_sources") or []:
        if isinstance(source, dict) and source.get("filename"):
            filenames.append(Path(str(source["filename"])).name)
    return sorted(dict.fromkeys(filename for filename in filenames if filename))


def validation_python_runner(*, env_prefix: str | Path | None, python_executable: str | Path | None) -> list[str]:
    if python_executable:
        return [str(python_executable)]
    if env_prefix:
        return ["conda", "run", "-p", str(env_prefix), "python"]
    return [sys.executable]


def mark_verified(root: Path, *, execution: dict[str, Any], gate: dict[str, Any]) -> None:
    spec_path = root / "references" / "adapter_spec.yaml"
    review_path = root / "references" / "adapter_review.yaml"
    catalog_path = root / "references" / "tutorial_catalog.yaml"
    if not catalog_path.exists():
        catalog_path = root / "references" / "examples_catalog.yaml"
    spec = read_yaml_reference(spec_path)
    review = read_yaml_reference(review_path)
    catalog = read_yaml_reference(catalog_path)
    example_id = gate.get("example_id")
    output_validation = execution.get("output_validation") if isinstance(execution.get("output_validation"), dict) else {}
    if output_validation.get("status") != "pass":
        return
    trace = run_trace_from_execution(root, execution=execution, example_id=example_id, expected_outputs=gate.get("expected_outputs") or [])
    result = promote_from_run_trace(
        adapter_spec=spec,
        adapter_review=review,
        tutorial_catalog=catalog,
        run_trace=trace,
        example_id=example_id,
    )
    write_json_file(root / "debug" / "build_validation_run_trace.promoted.json", trace)
    write_json_file(root / "build_validation" / "promotion_report.json", result)
    if not result.get("promoted"):
        return
    algorithm_contract = read_yaml_reference(root / "references" / "algorithm_contract.yaml")
    updated_algorithm_contract = update_algorithm_contract_after_promotion(algorithm_contract, result["adapter_spec"], result["maturity"])
    write_yaml_file(root / "references" / "algorithm_contract.yaml", updated_algorithm_contract)
    write_yaml_file(root / "references" / "adapter_spec.yaml", result["adapter_spec"])
    write_yaml_file(root / "references" / "adapter_review.yaml", result["adapter_review"])
    write_yaml_file(root / "references" / "tutorial_catalog.yaml", result["tutorial_catalog"])
    write_yaml_file(root / "references" / "maturity.yaml", result["maturity"])
    write_yaml_file(root / "references" / "contracts" / "algorithm_contract.yaml", updated_algorithm_contract)
    write_yaml_file(root / "references" / "contracts" / "adapter_contract.yaml", result["adapter_spec"])


def run_trace_from_execution(root: Path, *, execution: dict[str, Any], example_id: str | None, expected_outputs: list[str]) -> dict[str, Any]:
    result_dir = execution.get("result_dir")
    if result_dir:
        result_path = Path(str(result_dir))
        if not result_path.is_absolute():
            result_path = root / result_path
        trace = ingest_run_directory(result_path, skill_dir=root, example_id=example_id)
    else:
        trace = {}
    trace["status"] = execution.get("status", trace.get("status"))
    trace["commands"] = execution.get("commands") or trace.get("commands") or []
    output_validation = execution.get("output_validation") if isinstance(execution.get("output_validation"), dict) else {}
    if expected_outputs and "expected_outputs" not in output_validation:
        output_validation = {**output_validation, "expected_outputs": expected_outputs}
    trace["output_validation"] = output_validation
    return annotate_run_trace_promotion(trace)


def write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def execution_report(
    root: Path,
    *,
    depth: str,
    status: str,
    out: Path,
    commands: list[dict[str, Any]],
    validation_manifest: Path | None,
    input_manifest: Path | None,
    manifest_data: dict[str, Any],
    staged_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": status,
        "mode": depth,
        "result_dir": str(out),
        "commands": commands,
        "stages": {record["stage"]: {"returncode": record["returncode"]} for record in commands},
        "result_json": load_result_json(out),
        "output_validation": load_json_file(out / "qc" / "output_validation.json"),
        "staged_data": public_data(staged_data or [], root),
    }
    if depth == "data_smoke":
        report["data_smoke"] = {
            "input_manifest": str(input_manifest) if input_manifest else None,
            "validation_manifest": str(validation_manifest) if validation_manifest else None,
            "expected_outputs": manifest_data.get("expected_outputs") or [],
        }
    if depth == "live_execute":
        report["live_execute"] = {
            "official_example_evidence": manifest_data.get("official_example") or {},
            "environment_snapshot": environment_snapshot(root, out),
            "input_manifest_path": str(input_manifest) if input_manifest else None,
            "input_manifest": public_data(load_yaml_file(input_manifest), root) if input_manifest else {},
            "validation_manifest_path": str(validation_manifest) if validation_manifest else None,
            "validation_manifest": public_data(manifest_data, root),
            "result_dir": str(out),
            "failure_reason": None if status == "pass" else "see failed_stage and command stderr/stdout tails",
        }
    return report


def classify_execution_failure(stage: str, out: Path) -> str:
    if stage == "preflight":
        return "preflight_failed"
    if stage == "plan":
        return "execution_plan_failed"
    if stage in {"adapter_smoke", "full_execution"}:
        return "adapter_execution_failed"
    if stage == "output_validation":
        validation = load_json_file(out / "qc" / "output_validation.json")
        if validation.get("value_mismatches"):
            return "output_contract_mismatch"
        if validation.get("missing_expected_outputs"):
            return "expected_outputs_missing"
        if validation.get("missing_required_outputs"):
            return "required_outputs_missing"
        return "output_validation_failed"
    return "verification_execution_failed"


def failure_reason(stage: str, out: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "failure_code": classify_execution_failure(stage, out),
        "returncode": record.get("returncode"),
        "stdout_tail": record.get("stdout_tail"),
        "stderr_tail": record.get("stderr_tail"),
        "output_validation": load_json_file(out / "qc" / "output_validation.json"),
    }


def load_result_json(out: Path) -> dict[str, Any]:
    path = out / "result.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_json_file(path: Path) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_yaml_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def environment_snapshot(root: Path, out: Path) -> dict[str, Any]:
    snapshot = {
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "platform": platform.platform(),
        "environment_report": load_json_file(out / "qc" / "environment_report.json"),
    }
    return public_data(snapshot, root)


def tail_text(value: str, *, max_chars: int = 4000) -> str:
    return value[-max_chars:] if len(value) > max_chars else value
