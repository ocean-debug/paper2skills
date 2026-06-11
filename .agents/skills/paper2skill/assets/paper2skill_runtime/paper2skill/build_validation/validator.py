from __future__ import annotations

import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

from paper2skill.build_validation.skill_package import validate_skill_package
from paper2skill.collectors.path_sanitizer import public_data


VALIDATION_DEPTHS = ("dry_run", "data_smoke", "live_execute")
EXECUTABLE_ADAPTER_STATUSES = {"ready", "reviewed", "verified"}
READY_DRY_RUN_STATUSES = {"pass", "trusted_fixture"}
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

    gate = reviewed_execution_gate(root, depth=depth, manifest=manifest)
    report["review_gate"] = gate
    if not gate["passed"]:
        report["passed"] = False
        report["self_check_status"] = "blocked"
        report["status"] = gate["status"]
        report["errors"].extend(gate["errors"])
        report["warnings"].append(f"{depth} build validation requires an explicit reviewed example runner, approved data manifest, and expected outputs.")
        return finalize_report(report, root)

    execution = run_reviewed_validation(
        root,
        depth=depth,
        validation_manifest=gate["validation_manifest"],
        input_manifest=gate["input_manifest"],
        manifest_data=gate["manifest_data"],
        result_dir=result_dir,
        timeout_seconds=timeout_seconds,
    )
    report["execution"] = execution
    report["passed"] = execution["status"] == "pass"
    report["self_check_status"] = execution["status"]
    report["status"] = execution["status"]
    if execution["status"] != "pass":
        report["errors"].append(execution.get("failure_code") or f"{depth}_execution_failed")
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


def reviewed_execution_gate(root: Path, *, depth: str, manifest: str | Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    manifest_path = resolve_manifest(root, manifest)
    manifest_data: dict[str, Any] = {}
    manifest_errors: list[str] = []
    input_manifest_path: Path | None = None
    manifest_base = manifest_path.parent if manifest_path else root
    if manifest_path and manifest_path.is_file():
        manifest_data, manifest_errors = read_yaml_mapping(manifest_path)
        if manifest_errors:
            errors.extend(manifest_errors)
        input_manifest_path = resolve_referenced_path(root, manifest_base, manifest_data.get("manifest_path"))
    spec = read_yaml_reference(root / "references" / "adapter_spec.yaml")
    review = read_yaml_reference(root / "references" / "adapter_review.yaml")
    adapter_status = str(spec.get("status") or review.get("status") or "")
    dry_run_status = (review.get("dry_run") or {}).get("status") if isinstance(review.get("dry_run"), dict) else None
    output_validation = review.get("output_validation") if isinstance(review.get("output_validation"), dict) else {}
    expected_outputs = manifest_data.get("expected_outputs") if isinstance(manifest_data.get("expected_outputs"), list) else []
    expected_output_values = manifest_data.get("expected_output_values")

    data_kind = str(manifest_data.get("data_kind") or "")
    add_gate_check(checks, errors, "validation_manifest_present", manifest_path is not None and manifest_path.is_file(), "validation_manifest_required")
    if manifest_path is not None and manifest_path.is_file():
        add_gate_check(checks, errors, "validation_manifest_loadable", not manifest_errors, "validation_manifest_invalid")
        if not manifest_errors:
            add_gate_check(checks, errors, "validation_type_build_time", manifest_data.get("validation_type") == BUILD_VALIDATION_TYPE, "validation_manifest.validation_type_invalid")
            add_gate_check(checks, errors, "reviewed_manifest", manifest_data.get("reviewed") is True, "validation_manifest.reviewed_required")
            add_gate_check(checks, errors, "input_manifest_declared", bool(manifest_data.get("manifest_path")), "validation_manifest.manifest_path_required")
            add_gate_check(checks, errors, "input_manifest_present", input_manifest_path is not None and input_manifest_path.is_file(), "validation_manifest.manifest_path_not_found")
            add_gate_check(checks, errors, "expected_outputs_declared", bool(expected_outputs), "validation_manifest.expected_outputs_required")
            if expected_output_values is not None:
                add_gate_check(checks, errors, "expected_output_values_mapping", isinstance(expected_output_values, dict), "validation_manifest.expected_output_values_must_be_mapping")
            if depth == "data_smoke":
                add_gate_check(checks, errors, "data_kind_minimal", data_kind in DATA_SMOKE_KINDS, "validation_manifest.data_kind_must_be_minimal")
            if depth == "live_execute":
                add_gate_check(checks, errors, "data_kind_official_example", data_kind in LIVE_EXECUTE_KINDS, "validation_manifest.data_kind_must_be_official_example")
                official = manifest_data.get("official_example") if isinstance(manifest_data.get("official_example"), dict) else {}
                add_gate_check(checks, errors, "official_example_reviewed", official.get("reviewed") is True, "validation_manifest.official_example_reviewed_required")
    add_gate_check(checks, errors, "adapter_executable", adapter_status in EXECUTABLE_ADAPTER_STATUSES, "reviewed_adapter_required")
    if adapter_status == "reviewed":
        add_gate_check(checks, errors, "human_approved", review.get("human_approved") is True, "human_approval_required")
    if adapter_status in {"ready", "verified"}:
        add_gate_check(checks, errors, "dry_run_evidence", dry_run_status in READY_DRY_RUN_STATUSES, "passing_dry_run_evidence_required")
    if depth == "live_execute":
        if adapter_status == "verified":
            add_gate_check(checks, errors, "prior_output_validation", output_validation.get("status") == "pass", "verified_output_validation_required")

    return {
        "required": True,
        "passed": not errors,
        "status": "pass" if not errors else "blocked_review_required",
        "validation_manifest": str(manifest_path) if manifest_path else None,
        "input_manifest": str(input_manifest_path) if input_manifest_path else None,
        "manifest_data": public_data(manifest_data, root) if manifest_data else {},
        "data_kind": data_kind or None,
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


def read_yaml_mapping(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"validation_manifest_load_error:{exc}"]
    if not isinstance(data, dict):
        return {}, ["validation_manifest_must_be_mapping"]
    return data, []


def run_reviewed_validation(
    root: Path,
    *,
    depth: str,
    validation_manifest: str | Path | None,
    input_manifest: str | Path | None,
    manifest_data: dict[str, Any],
    result_dir: str | Path | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    if result_dir:
        out = Path(result_dir)
    else:
        out = root / "build_validation" / "execution_result"
    if not out.is_absolute():
        out = root / out
    input_manifest_path = Path(str(input_manifest)) if input_manifest else None
    validation_manifest_path = Path(str(validation_manifest)) if validation_manifest else None
    stages = [
        ("preflight", [sys.executable, str(root / "scripts" / "preflight.py"), "--manifest", str(input_manifest_path), "--out", str(out)]),
        ("plan", [sys.executable, str(root / "scripts" / "plan.py"), "--manifest", str(input_manifest_path), "--out", str(out)]),
        (
            "adapter_smoke" if depth == "data_smoke" else "full_execution",
            [sys.executable, str(root / "scripts" / "run.py"), "--manifest", str(input_manifest_path), "--out", str(out)],
        ),
        (
            "output_validation",
            [
                sys.executable,
                str(root / "scripts" / "validate_outputs.py"),
                "--result",
                str(out),
                "--validation-manifest",
                str(validation_manifest_path),
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
    )


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
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": status,
        "mode": depth,
        "result_dir": str(out),
        "commands": commands,
        "stages": {record["stage"]: {"returncode": record["returncode"]} for record in commands},
        "result_json": load_result_json(out),
        "output_validation": load_json_file(out / "qc" / "output_validation.json"),
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
    return "reviewed_execution_failed"


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
