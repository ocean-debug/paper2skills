from __future__ import annotations

import subprocess
import sys
import shutil
import json
from pathlib import Path
from typing import Any

import yaml

from paper2skill.evaluation.execution.data_manager import prepare_download
from paper2skill.evaluation.execution.input_validator import validate_input_manifest
from paper2skill.evaluation.execution.output_validator import validate_expected_outputs
from paper2skill.evaluation.load_gold import evaluation_result, field_value, finish_result
from paper2skill.evaluation.schemas import EXECUTABLE_ADAPTER_STATUSES, L2_MODE_RANK


def evaluate_official_examples(
    gold: dict[str, Any],
    generated: dict[str, Any],
    *,
    skill_dir: str | Path | None = None,
    case_dir: str | Path | None = None,
    allow_download: bool = False,
    download_cache: str | Path = "benchmarks/data_cache",
    max_download_mb: float = 0.0,
    allow_execution: str = "reviewed_only",
    l2_mode: str = "dry_run",
    allow_install: str = "none",
    install_env: str | None = None,
) -> dict[str, Any]:
    result = evaluation_result("official_example_execution")
    examples = gold.get("official_examples") or []
    if not examples:
        return finish_result(result, {"official_examples_defined": 1.0})
    adapter_status = adapter_status_value(generated)
    reports = []
    scores = []
    for example in examples:
        report = evaluate_one_example(
            example,
            adapter_status=adapter_status,
            io_contract=generated_io_contract(generated),
            skill_dir=skill_dir,
            case_dir=case_dir,
            allow_download=allow_download,
            download_cache=download_cache,
            max_download_mb=max_download_mb,
            allow_execution=allow_execution,
            l2_mode=l2_mode,
            allow_install=allow_install,
            install_env=install_env,
        )
        reports.append(report)
        scores.append(float(report.get("score", 0.0)))
        result["warnings"].extend(report.get("warnings", []))
        result["mismatched_items"].extend(report.get("mismatched_items", []))
    result["examples"] = reports
    result["l2_summary"] = summarize_l2_reports(reports)
    finished = finish_result(result, {"official_example_score": sum(scores) / len(scores)})
    finished["metrics"].update(l2_report_metrics(reports))
    return finished


def evaluate_one_example(
    example: dict[str, Any],
    *,
    adapter_status: str,
    io_contract: dict[str, Any],
    skill_dir: str | Path | None,
    case_dir: str | Path | None,
    allow_download: bool,
    download_cache: str | Path,
    max_download_mb: float,
    allow_execution: str,
    l2_mode: str,
    allow_install: str,
    install_env: str | None,
) -> dict[str, Any]:
    expected_status = str((example.get("expected_run") or {}).get("expected_status") or "")
    mode = str(example.get("execution_mode") or "blocked_expected")
    if not mode_allowed(mode, l2_mode):
        score, reason, depth = score_l2_example(
            actual_status="skipped_by_l2_mode",
            expected_status=expected_status,
            mode=mode,
            requested_l2_mode=l2_mode,
        )
        return {
            "example_id": example.get("example_id"),
            "mode": mode,
            "requested_l2_mode": l2_mode,
            "expected_status": expected_status,
            "actual_status": "skipped_by_l2_mode",
            "execution_depth": depth,
            "score": score,
            "score_reason": reason,
            "adapter_status": adapter_status,
            "download": {"status": "not_applicable", "path": None, "warnings": []},
            "fixtures": {"status": "not_applicable", "copied_files": []},
            "reviewed_adapter": {"status": "not_applicable"},
            "input_validation": {"passed": True, "errors": [], "warnings": []},
            "execution": {
                "status": "not_applicable",
                "requested_l2_mode": l2_mode,
                "example_execution_mode": mode,
                "message": "Example requires a deeper L2 mode than requested.",
            },
            "passed": True,
            "warnings": [],
            "mismatched_items": [],
        }
    effective_download = allow_download and mode_allowed(mode, l2_mode)
    download_report = prepare_download(example.get("download"), allow_download=effective_download, cache_dir=download_cache, max_download_mb=max_download_mb)
    warnings = list(download_report.get("warnings") or [])
    mismatches = []
    overlay_report = apply_reviewed_adapter_overlay(example.get("reviewed_adapter"), skill_dir, case_dir)
    fixture_report = prepare_fixture_files(example.get("fixture_files"), skill_dir, case_dir)
    warnings.extend(overlay_report.get("warnings") or [])
    warnings.extend(fixture_report.get("warnings") or [])
    if overlay_report.get("adapter_status"):
        adapter_status = str(overlay_report["adapter_status"])
    executable = adapter_status in EXECUTABLE_ADAPTER_STATUSES and allow_execution in {"reviewed_only", "all"}
    input_validation = validate_input_manifest(example.get("input_manifest"), io_contract.get("input_contract") or io_contract)
    should_require_valid_manifest = executable or expected_status == "success"
    if download_report.get("status") == "skipped" and example.get("download"):
        passed = False
        actual_status = "download_required"
        mismatches.append({"field": "download", "status": "skipped", "message": "Set --allow-download for data_smoke/live_execute examples."})
    elif mode == "blocked_expected" or expected_status == "blocked_by_policy":
        passed = not executable
        actual_status = "blocked_by_policy" if not executable else "would_execute"
    elif not executable:
        passed = expected_status in {"blocked_by_policy_or_success", "success_or_blocked_by_policy"}
        actual_status = "blocked_by_policy"
    elif should_require_valid_manifest and not input_validation["passed"]:
        passed = False
        actual_status = "input_validation_failed"
        mismatches.append({"field": "input_manifest", "errors": input_validation["errors"]})
    else:
        execution_report = run_generated_skill(example, skill_dir, l2_mode=l2_mode, allow_install=allow_install, install_env=install_env)
        if expected_status in {"blocked_by_policy_or_success", "success_or_blocked_by_policy"} and execution_report["status"] == "blocked_by_policy":
            output_report = {"passed": True, "missing": []}
            passed = download_report.get("status") != "failed"
            actual_status = "blocked_by_policy"
        elif execution_report["status"] == "success":
            output_report = validate_expected_outputs(example.get("expected_outputs"), execution_report.get("run_dir") or skill_dir)
            passed = output_report["passed"] and download_report.get("status") != "failed"
            actual_status = "success" if passed else "output_validation_failed"
        elif execution_report["status"] == "install_approval_required":
            output_report = {"passed": True, "missing": []}
            passed = False
            actual_status = "install_approval_required"
        else:
            output_report = {"passed": False, "missing": []}
            passed = False
            actual_status = execution_report["status"]
        if not output_report["passed"]:
            mismatches.append({"field": "expected_outputs", "missing": output_report["missing"]})
        if execution_report["status"] not in {"success", "blocked_by_policy"}:
            mismatches.append({"field": "execution", "status": execution_report["status"], "exit_code": execution_report.get("exit_code")})
    if download_report.get("status") == "failed":
        passed = False
    score, reason, depth = score_l2_example(
        actual_status=actual_status,
        expected_status=expected_status,
        mode=mode,
        requested_l2_mode=l2_mode,
    )
    return {
        "example_id": example.get("example_id"),
        "mode": mode,
        "requested_l2_mode": l2_mode,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "execution_depth": depth,
        "score": score,
        "score_reason": reason,
        "adapter_status": adapter_status,
        "download": download_report,
        "fixtures": fixture_report,
        "reviewed_adapter": overlay_report,
        "input_validation": input_validation,
        "execution": locals().get("execution_report"),
        "passed": passed,
        "warnings": warnings,
        "mismatched_items": mismatches,
    }


def score_l2_example(*, actual_status: str, expected_status: str, mode: str, requested_l2_mode: str) -> tuple[float, str, str]:
    if actual_status == "success":
        if requested_l2_mode == "live_execute" or mode in {"full", "live_execute"}:
            return 1.0, "live_execute_success", "live_execute"
        return 1.0, "data_smoke_success", "data_smoke"
    if actual_status == "blocked_by_policy" and expects_policy_block(expected_status):
        return 1.0, "expected_policy_block", "dry_run_policy_block"
    if actual_status == "skipped_by_l2_mode":
        return 0.25, "dry_run_skip_no_example_execution", "dry_run_skip"
    if actual_status == "install_approval_required":
        return 0.5, "install_approval_required_before_execution", "install_approval_required"
    return 0.0, f"{actual_status}_is_not_success", "not_successful"


def expects_policy_block(expected_status: str) -> bool:
    return expected_status in {"blocked_by_policy", "blocked_by_policy_or_success", "success_or_blocked_by_policy"}


def summarize_l2_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    depth_counts: dict[str, int] = {}
    score_reasons: dict[str, int] = {}
    for report in reports:
        increment(status_counts, str(report.get("actual_status") or "unknown"))
        increment(depth_counts, str(report.get("execution_depth") or "unknown"))
        increment(score_reasons, str(report.get("score_reason") or "unknown"))
    return {
        "example_count": len(reports),
        "status_counts": status_counts,
        "execution_depth_counts": depth_counts,
        "score_reasons": score_reasons,
        "average_example_score": round(sum(float(report.get("score", 0.0)) for report in reports) / len(reports), 4) if reports else 1.0,
    }


def l2_report_metrics(reports: list[dict[str, Any]]) -> dict[str, float]:
    if not reports:
        return {}
    count = float(len(reports))
    return {
        "example_pass_rate": sum(1.0 for report in reports if report.get("passed")) / count,
        "dry_run_skip_rate": sum(1.0 for report in reports if report.get("actual_status") == "skipped_by_l2_mode") / count,
        "data_smoke_success_rate": sum(1.0 for report in reports if report.get("execution_depth") == "data_smoke") / count,
        "live_execute_success_rate": sum(1.0 for report in reports if report.get("execution_depth") == "live_execute") / count,
        "expected_policy_block_rate": sum(1.0 for report in reports if report.get("score_reason") == "expected_policy_block") / count,
        "install_approval_request_rate": sum(1.0 for report in reports if report.get("actual_status") == "install_approval_required") / count,
    }


def increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def adapter_status_value(generated: dict[str, Any]) -> str:
    adapter_review = generated.get("adapter_review") or {}
    adapter_spec = generated.get("adapter_spec") or {}
    for source in [adapter_review, adapter_spec]:
        for key in ["status", "adapter_status", "initial_status"]:
            value = field_value(source.get(key) if isinstance(source, dict) else None)
            if value:
                return str(value)
    return "candidate"


def generated_io_contract(generated: dict[str, Any]) -> dict[str, Any]:
    io_contract = generated.get("io_contract")
    return io_contract if isinstance(io_contract, dict) else {}


def apply_reviewed_adapter_overlay(spec: Any, skill_dir: str | Path | None, case_dir: str | Path | None) -> dict[str, Any]:
    if not isinstance(spec, dict):
        return {"status": "not_requested"}
    if skill_dir is None or case_dir is None:
        return {"status": "failed", "warnings": ["reviewed_adapter requested but skill_dir or case_dir is missing"]}
    skill_path = Path(skill_dir).resolve()
    case_path = Path(case_dir)
    warnings: list[str] = []
    copied = copy_declared_files(spec.get("files"), skill_path, case_path, warnings)
    adapter_spec = dict(spec.get("adapter_spec") or {})
    adapter_review = dict(spec.get("adapter_review") or {})
    status = str(spec.get("status") or adapter_spec.get("status") or adapter_review.get("status") or "")
    adapter_type = str(spec.get("adapter_type") or adapter_spec.get("adapter_type") or adapter_review.get("adapter_type") or "")
    if status:
        adapter_spec["status"] = status
        adapter_review["status"] = status
    if adapter_type:
        adapter_spec["adapter_type"] = adapter_type
        adapter_review["adapter_type"] = adapter_type
    if adapter_spec:
        write_yaml(skill_path / "references" / "adapter_spec.yaml", adapter_spec)
    if adapter_review:
        write_yaml(skill_path / "references" / "adapter_review.yaml", adapter_review)
    effective_status = status if not warnings else None
    return {
        "status": "applied" if not warnings else "partial",
        "adapter_status": effective_status,
        "adapter_type": adapter_type or None,
        "copied_files": copied,
        "warnings": warnings,
    }


def prepare_fixture_files(files: Any, skill_dir: str | Path | None, case_dir: str | Path | None) -> dict[str, Any]:
    if not files:
        return {"status": "not_requested", "copied_files": []}
    if skill_dir is None or case_dir is None:
        return {"status": "failed", "copied_files": [], "warnings": ["fixture_files requested but skill_dir or case_dir is missing"]}
    warnings: list[str] = []
    copied = copy_declared_files(files, Path(skill_dir), Path(case_dir), warnings)
    return {"status": "ready" if not warnings else "partial", "copied_files": copied, "warnings": warnings}


def copy_declared_files(files: Any, skill_path: Path, case_path: Path, warnings: list[str]) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for item in files or []:
        if not isinstance(item, dict):
            warnings.append(f"invalid file declaration: {item!r}")
            continue
        source_value = item.get("source")
        target_value = item.get("target")
        if not source_value or not target_value:
            warnings.append(f"file declaration missing source or target: {item!r}")
            continue
        source = Path(str(source_value))
        if not source.is_absolute():
            source = case_path / source
        target = Path(str(target_value))
        if target.is_absolute():
            warnings.append(f"absolute overlay target is not allowed: {target}")
            continue
        target = skill_path / target
        if not source.exists():
            warnings.append(f"overlay source not found: {source}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append({"source": str(source), "target": str(target)})
    return copied


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run_generated_skill(
    example: dict[str, Any],
    skill_dir: str | Path | None,
    *,
    l2_mode: str,
    allow_install: str,
    install_env: str | None,
) -> dict[str, Any]:
    if skill_dir is None:
        return {"status": "execution_failed", "reason": "skill_dir missing"}
    skill_path = Path(skill_dir).resolve()
    run_script = skill_path / "scripts" / "run.py"
    if not run_script.exists():
        return {"status": "execution_failed", "reason": "scripts/run.py missing"}
    run_dir = skill_path / ".benchmark" / "l2" / str(example.get("example_id") or "example")
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        manifest_path = materialize_input_manifest(example.get("input_manifest"), skill_path, run_dir)
        preflight_report = run_preflight(skill_path, manifest_path, run_dir)
        install_request = build_install_request(preflight_report, example, l2_mode, allow_install, install_env)
        if install_request:
            return {
                "status": "install_approval_required",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
                "install_request": install_request,
            }
        if preflight_report and preflight_report.get("status") == "blocked_by_policy":
            return {
                "status": "blocked_by_policy",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
            }
        if preflight_report and preflight_report.get("status") != "success":
            return {
                "status": "preflight_failed",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
            }
        command = [sys.executable, str(run_script), "--manifest", str(manifest_path), "--out", str(run_dir)]
        completed = subprocess.run(command, cwd=skill_path, text=True, capture_output=True, timeout=float(example.get("timeout_seconds") or 600), check=False)
    except subprocess.TimeoutExpired as exc:
        return {"status": "execution_timeout", "run_dir": str(run_dir), "stdout": truncate(exc.stdout), "stderr": truncate(exc.stderr)}
    except Exception as exc:  # noqa: BLE001 - evaluator must report failure instead of traceback.
        return {"status": "execution_failed", "run_dir": str(run_dir), "reason": str(exc)}
    report = {
        "status": "success" if completed.returncode == 0 else ("blocked_by_policy" if completed.returncode == 2 else "execution_failed"),
        "exit_code": completed.returncode,
        "run_dir": str(run_dir),
        "stdout": truncate(completed.stdout),
        "stderr": truncate(completed.stderr),
    }
    if preflight_report:
        report["preflight"] = preflight_report
    validator_report = run_output_validator(skill_path, run_dir)
    if validator_report:
        report["output_validator"] = validator_report
        if report["status"] == "success" and validator_report.get("status") != "success":
            report["status"] = "output_validation_failed"
    return report


def mode_allowed(example_mode: str, requested_mode: str) -> bool:
    return L2_MODE_RANK.get(example_mode, 1) <= L2_MODE_RANK.get(requested_mode, 0)


def build_install_request(
    preflight_report: dict[str, Any] | None,
    example: dict[str, Any],
    l2_mode: str,
    allow_install: str,
    install_env: str | None,
) -> dict[str, Any] | None:
    if not preflight_report or preflight_report.get("status") != "blocked_by_policy":
        return None
    payload = parse_preflight_stdout(preflight_report.get("stdout"))
    if payload.get("status") != "blocked_dependencies_missing":
        return None
    if allow_install != "ask":
        return None
    dependencies = dependency_summary(payload)
    install_spec = example.get("dependencies") if isinstance(example.get("dependencies"), dict) else {}
    return {
        "status": "approval_required",
        "requested_l2_mode": l2_mode,
        "target_environment": install_env,
        "preferred_environment": install_spec.get("preferred_environment") or "isolated_conda",
        "allowed_installers": install_spec.get("allowed_installers") or ["conda", "pip", "BiocManager", "install.packages"],
        "required_packages": install_spec.get("required_packages") or dependencies.get("required_packages", []),
        "missing_python_packages": dependencies.get("missing_python_packages", []),
        "missing_r_packages": dependencies.get("missing_r_packages", []),
        "missing_executables": dependencies.get("missing_executables", []),
        "question": "Dependencies are missing. Approve installation and provide the target environment before live execution.",
        "safety": {
            "auto_install_performed": False,
            "notebook_execution_performed": False,
            "requires_explicit_user_approval": True,
        },
    }


def parse_preflight_stdout(stdout: Any) -> dict[str, Any]:
    if not stdout:
        return {}
    text = str(stdout)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def dependency_summary(payload: dict[str, Any]) -> dict[str, list[str]]:
    environment = payload.get("environment") if isinstance(payload, dict) else {}
    python = environment.get("python") if isinstance(environment, dict) else {}
    r = environment.get("r") if isinstance(environment, dict) else {}
    executables = environment.get("executables") if isinstance(environment, dict) else []
    missing_python = missing_package_names(python.get("packages") if isinstance(python, dict) else [])
    missing_r = missing_package_names(r.get("packages") if isinstance(r, dict) else [])
    missing_exec = [str(item.get("name")) for item in executables or [] if isinstance(item, dict) and item.get("required") and not item.get("available")]
    return {
        "missing_python_packages": missing_python,
        "missing_r_packages": missing_r,
        "missing_executables": missing_exec,
        "required_packages": sorted(dict.fromkeys(missing_python + missing_r + missing_exec)),
    }


def missing_package_names(packages: Any) -> list[str]:
    return sorted(
        dict.fromkeys(
            str(item.get("name"))
            for item in packages or []
            if isinstance(item, dict) and item.get("required") and item.get("installed") is False and item.get("name")
        )
    )


def run_preflight(skill_path: Path, manifest_path: Path, run_dir: Path) -> dict[str, Any] | None:
    preflight = skill_path / "scripts" / "preflight.py"
    if not preflight.exists():
        return None
    try:
        completed = subprocess.run(
            [sys.executable, str(preflight), "--manifest", str(manifest_path), "--out", str(run_dir)],
            cwd=skill_path,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - evaluator must report failure instead of traceback.
        return {"status": "preflight_failed", "reason": str(exc)}
    return {
        "status": "success" if completed.returncode == 0 else ("blocked_by_policy" if completed.returncode == 2 else "preflight_failed"),
        "exit_code": completed.returncode,
        "stdout": truncate(completed.stdout),
        "stderr": truncate(completed.stderr),
    }


def materialize_input_manifest(input_manifest: Any, skill_path: Path, run_dir: Path) -> Path:
    if isinstance(input_manifest, str) and input_manifest.strip():
        manifest_path = Path(input_manifest)
        if not manifest_path.is_absolute():
            manifest_path = skill_path / manifest_path
        if not manifest_path.exists():
            raise FileNotFoundError(f"input manifest not found: {manifest_path}")
        return manifest_path
    if isinstance(input_manifest, dict):
        manifest_path = run_dir / "input_manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(input_manifest, sort_keys=False), encoding="utf-8")
        return manifest_path
    manifest_path = run_dir / "input_manifest.yaml"
    manifest_path.write_text("{}\n", encoding="utf-8")
    return manifest_path


def run_output_validator(skill_path: Path, run_dir: Path) -> dict[str, Any] | None:
    validator = skill_path / "scripts" / "validate_outputs.py"
    if not validator.exists():
        return None
    try:
        completed = subprocess.run(
            [sys.executable, str(validator), "--result", str(run_dir)],
            cwd=skill_path,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - evaluator must report failure instead of traceback.
        return {"status": "validator_failed", "reason": str(exc)}
    return {
        "status": "success" if completed.returncode == 0 else "validator_failed",
        "exit_code": completed.returncode,
        "stdout": truncate(completed.stdout),
        "stderr": truncate(completed.stderr),
    }


def truncate(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
