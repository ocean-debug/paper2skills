from __future__ import annotations

import re
import subprocess
import sys
import shutil
import json
from pathlib import Path
from typing import Any

import yaml

from paper2skill.common import write_json
from paper2skill.evaluation.execution.data_manager import prepare_download
from paper2skill.evaluation.execution.install_approved_plan import build_install_plan, execute_install_plan
from paper2skill.evaluation.execution.input_validator import validate_input_manifest
from paper2skill.evaluation.execution.output_validator import validate_expected_outputs
from paper2skill.evaluation.load_gold import evaluation_result, field_value, finish_result
from paper2skill.evaluation.schemas import BENCHMARK_L2_MODE, EXECUTABLE_ADAPTER_STATUSES, L2_MODE_RANK
from paper2skill.env_rebuilder.executor import apply_install_plan as apply_bio_install_plan
from paper2skill.env_rebuilder.env_paths import conda_env_args, resolve_env_path, uv_python_executable
from paper2skill.env_rebuilder.lockfile import export_lock_artifacts
from paper2skill.env_rebuilder.planner import build_bio_env_plan, plan_from_install_request
from paper2skill.env_rebuilder.repair import diagnose_failure


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
    l2_mode: str = BENCHMARK_L2_MODE,
    allow_install: str = "none",
    install_env: str | None = None,
    create_conda_env: bool = False,
    python_version: str = "3.11",
    env_rebuilder: str = "legacy",
    target_env_mode: str = "new",
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    repair_attempts: int = 3,
    export_lock: bool = False,
) -> dict[str, Any]:
    result = evaluation_result("official_example_execution")
    official_examples = gold.get("official_examples") or []
    diagnostic_only = l2_mode != BENCHMARK_L2_MODE
    if not official_examples:
        return missing_l2_gold_result(
            result,
            missing_item="level2_official_examples.official_examples",
            reason="missing_official_example_gold" if diagnostic_only else "missing_live_official_example_gold",
            diagnostic_only=diagnostic_only,
        )
    live_examples = live_execute_examples(official_examples)
    if not live_examples and not diagnostic_only:
        return missing_l2_gold_result(
            result,
            missing_item="level2_official_examples.live_execute",
            reason="missing_live_official_example_gold",
            diagnostic_only=False,
        )
    examples = selected_examples(official_examples, l2_mode)
    if not examples:
        return missing_l2_gold_result(
            result,
            missing_item="level2_official_examples.selected_examples",
            reason="missing_selected_official_example_gold",
            diagnostic_only=diagnostic_only,
        )
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
            create_conda_env=create_conda_env,
            python_version=python_version,
            env_rebuilder=env_rebuilder,
            target_env_mode=target_env_mode,
            allow_github_install=allow_github_install,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            repair_attempts=repair_attempts,
            export_lock=export_lock,
            diagnostic_only=diagnostic_only,
        )
        reports.append(report)
        scores.append(float(report.get("score", 0.0)))
        result["warnings"].extend(report.get("warnings", []))
        result["mismatched_items"].extend(report.get("mismatched_items", []))
    result["examples"] = reports
    result["l2_summary"] = summarize_l2_reports(reports)
    result["l2_summary"]["diagnostic_only"] = diagnostic_only
    result["l2_summary"]["benchmark_policy"] = "diagnostic_only" if diagnostic_only else "live_execute_required"
    finished = finish_result(result, {"official_live_execute_score": sum(scores) / len(scores)})
    finished["diagnostic_only"] = diagnostic_only
    finished["metrics"].update(l2_report_metrics(reports))
    return finished


def missing_l2_gold_result(
    result: dict[str, Any],
    *,
    missing_item: str,
    reason: str,
    diagnostic_only: bool,
) -> dict[str, Any]:
    result["missing_items"].append(missing_item)
    result["l2_summary"] = {
        "example_count": 0,
        "status_counts": {reason: 1},
        "execution_depth_counts": {},
        "score_reasons": {reason: 1},
        "average_example_score": 0.0,
        "diagnostic_only": diagnostic_only,
        "benchmark_policy": "diagnostic_only" if diagnostic_only else "live_execute_required",
    }
    finished = finish_result(result, {"official_examples_defined": 0.0})
    finished["diagnostic_only"] = diagnostic_only
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
    create_conda_env: bool,
    python_version: str,
    env_rebuilder: str,
    target_env_mode: str,
    allow_github_install: str,
    gpu_policy: str,
    torch_backend: str,
    repair_attempts: int,
    export_lock: bool,
    diagnostic_only: bool = False,
) -> dict[str, Any]:
    expected_status = str((example.get("expected_run") or {}).get("expected_status") or "")
    mode = str(example.get("execution_mode") or "blocked_expected")
    if not mode_allowed(mode, l2_mode):
        score, reason, depth = score_l2_example(
            actual_status="skipped_by_l2_mode",
            expected_status=expected_status,
            mode=mode,
            requested_l2_mode=l2_mode,
            diagnostic_only=diagnostic_only,
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
            "diagnostic_only": diagnostic_only,
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
            "passed": False,
            "execution_passed": False,
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
        execution_example = dict(example)
        if case_dir is not None:
            execution_example["_case_dir"] = str(case_dir)
        execution_report = run_generated_skill(
            execution_example,
            skill_dir,
            l2_mode=l2_mode,
            allow_install=allow_install,
            install_env=install_env,
            create_conda_env=create_conda_env,
            python_version=python_version,
            env_rebuilder=env_rebuilder,
            target_env_mode=target_env_mode,
            allow_github_install=allow_github_install,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            repair_attempts=repair_attempts,
            export_lock=export_lock,
        )
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
        diagnostic_only=diagnostic_only,
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
        "diagnostic_only": diagnostic_only,
        "adapter_status": adapter_status,
        "download": download_report,
        "fixtures": fixture_report,
        "reviewed_adapter": overlay_report,
        "input_validation": input_validation,
        "execution": locals().get("execution_report"),
        "passed": bool(passed and score >= 1.0),
        "execution_passed": bool(passed and actual_status == "success"),
        "warnings": warnings,
        "mismatched_items": mismatches,
    }


def selected_examples(examples: list[dict[str, Any]], l2_mode: str) -> list[dict[str, Any]]:
    if l2_mode == "live_execute":
        live = [example for example in examples if str(example.get("execution_mode") or "") in {"live_execute", "full"}]
        return live or examples
    if l2_mode == "data_smoke":
        smoke = [example for example in examples if str(example.get("execution_mode") or "") in {"smoke", "data_smoke"}]
        return smoke or examples
    return examples


def live_execute_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [example for example in examples if str(example.get("execution_mode") or "") in {"live_execute", "full"}]


def score_l2_example(*, actual_status: str, expected_status: str, mode: str, requested_l2_mode: str, diagnostic_only: bool = False) -> tuple[float, str, str]:
    if actual_status == "success":
        if mode in {"full", "live_execute"}:
            return 1.0, "live_execute_success", "live_execute"
        if diagnostic_only:
            return 0.0, "diagnostic_data_smoke_success_not_benchmark_scoring", "data_smoke"
        if requested_l2_mode == "live_execute":
            return 0.0, "data_smoke_success_is_not_live_execute", "data_smoke"
        return 0.0, "diagnostic_data_smoke_success_not_benchmark_scoring", "data_smoke"
    if actual_status == "blocked_by_policy" and expects_policy_block(expected_status):
        return 0.0, "expected_policy_block_is_l4_not_l2", "dry_run_policy_block"
    if actual_status == "skipped_by_l2_mode":
        return 0.0, "dry_run_skip_no_example_execution", "dry_run_skip"
    if actual_status == "install_approval_required":
        return 0.0, "install_approval_required_before_execution", "install_approval_required"
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
        "benchmark_pass_rate": sum(1.0 for report in reports if report.get("passed")) / count,
        "execution_success_rate": sum(1.0 for report in reports if report.get("execution_passed")) / count,
        "dry_run_skip_rate": sum(1.0 for report in reports if report.get("actual_status") == "skipped_by_l2_mode") / count,
        "data_smoke_diagnostic_rate": sum(1.0 for report in reports if report.get("execution_depth") == "data_smoke") / count,
        "live_execute_success_rate": sum(1.0 for report in reports if report.get("execution_depth") == "live_execute") / count,
        "policy_block_rate": sum(1.0 for report in reports if report.get("execution_depth") == "dry_run_policy_block") / count,
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
    create_conda_env: bool,
    python_version: str,
    env_rebuilder: str = "legacy",
    target_env_mode: str = "new",
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    repair_attempts: int = 3,
    export_lock: bool = False,
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
        install_report = None
        if allow_install == "approved":
            declared_request = declared_install_request(example, install_env, case_dir=example.get("_case_dir"))
            install_report = install_approved_dependencies(
                declared_request,
                install_env=install_env,
                skill_dir=skill_path,
                run_dir=run_dir,
                create_conda_env=create_conda_env,
                python_version=python_version,
                env_rebuilder=env_rebuilder,
                target_env_mode=target_env_mode,
                allow_install=allow_install,
                allow_github_install=allow_github_install,
                gpu_policy=gpu_policy,
                torch_backend=torch_backend,
                repair_attempts=repair_attempts,
                export_lock=export_lock,
            )
            if install_report.get("status") in {"approval_required", "blocked_manual"}:
                return {
                    "status": "install_approval_required",
                    "run_dir": str(run_dir),
                    "install_report": install_report,
                }
            if install_report.get("status") != "executed":
                return {
                    "status": "install_failed",
                    "run_dir": str(run_dir),
                    "install_report": install_report,
                }
        runner = command_runner(allow_install=allow_install, install_env=install_env, install_report=install_report)
        preflight_report = run_preflight(skill_path, manifest_path, run_dir, runner=runner)
        install_request = build_install_request(preflight_report, example, l2_mode, allow_install, install_env)
        if install_request:
            return {
                "status": "install_approval_required",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
                "install_request": install_request,
            }
        if preflight_report and preflight_report.get("status") == "blocked_by_policy":
            payload = parse_preflight_stdout(preflight_report.get("stdout"))
            if allow_install == "approved" and payload.get("status") == "blocked_dependencies_missing":
                return {
                    "status": "dependencies_missing_after_install",
                    "run_dir": str(run_dir),
                    "preflight": preflight_report,
                    "install_report": install_report,
                    "missing_dependencies": dependency_summary(payload),
                }
            return {
                "status": "blocked_by_policy",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
                "install_report": install_report,
            }
        if preflight_report and preflight_report.get("status") != "success":
            return {
                "status": "preflight_failed",
                "run_dir": str(run_dir),
                "preflight": preflight_report,
                "install_report": install_report,
            }
        command = runner([str(run_script), "--manifest", str(manifest_path), "--out", str(run_dir)])
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
    if install_report:
        report["install_report"] = install_report
    validator_report = run_output_validator(skill_path, run_dir, runner=runner)
    if validator_report:
        report["output_validator"] = validator_report
        if report["status"] == "success" and validator_report.get("status") != "success":
            report["status"] = "output_validation_failed"
    return report


def command_runner(*, allow_install: str, install_env: str | None, install_report: dict[str, Any] | None = None):
    if allow_install == "approved" and install_env:
        if (install_report or {}).get("env_rebuilder") == "bio":
            manager = str((install_report or {}).get("manager") or "")
            python_executable = (install_report or {}).get("python_executable")
            if manager == "uv" and python_executable:
                def run_in_uv_env(args: list[str]) -> list[str]:
                    return [str(python_executable), *args]

                return run_in_uv_env

        def run_in_env(args: list[str]) -> list[str]:
            return ["conda", "run", *conda_env_args(install_env), "python", *args]

        return run_in_env

    def run_current(args: list[str]) -> list[str]:
        return [sys.executable, *args]

    return run_current

def install_approved_dependencies(
    install_request: dict[str, Any],
    *,
    install_env: str | None,
    skill_dir: Path | None = None,
    run_dir: Path | None = None,
    create_conda_env: bool,
    python_version: str,
    env_rebuilder: str = "legacy",
    target_env_mode: str = "new",
    allow_install: str = "approved",
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    repair_attempts: int = 3,
    export_lock: bool = False,
) -> dict[str, Any]:
    if not install_env:
        return {"status": "invalid", "errors": ["install_env is required for approved installation"]}
    if env_rebuilder == "bio":
        try:
            resolved_env_path = resolve_env_path(install_env, skill_dir)
            plan = build_bio_env_plan(
                case_dir=install_request.get("case_dir"),
                skill_dir=skill_dir,
                repo_dir=install_request.get("repo_dir"),
                source_dir=install_request.get("source_dir"),
                install_request=install_request,
                target=target_env_mode,
                env=install_env,
                env_path=resolved_env_path,
                allow_github_install=allow_github_install,
                gpu_policy=gpu_policy,
                torch_backend=torch_backend,
                python_version=python_version,
                allow_install=allow_install,
            )
            add_bio_plan_report_paths(plan, run_dir)
            plan["env_rebuilder"] = "bio"
            if plan.get("status") not in {"ready", "blocked_manual"}:
                write_bio_install_reports(run_dir, plan=plan, report=plan, repair_attempts=[])
                return plan
            if plan.get("status") == "blocked_manual":
                report = {
                    "status": "approval_required",
                    "env_rebuilder": "bio",
                    "plan_source": plan.get("plan_source") or plan.get("mode") or "canonical_env",
                    "scanned_artifacts": plan.get("scanned_artifacts") or [],
                    "lockfile_status": plan.get("lockfile_status") or plan.get("lock_trust"),
                    "canonical_env_path": plan.get("canonical_env_path"),
                    "install_plan_path": plan.get("install_plan_path"),
                    "env_rebuild_report_path": plan.get("env_rebuild_report_path"),
                    "manager": plan.get("manager"),
                    "allow_install": plan.get("allow_install"),
                    "resolved_env_path": resolved_env_path,
                    "python_executable": bio_python_executable(plan, resolved_env_path, install_env),
                    "install_plan": plan,
                    "manual_approval_required": True,
                    "errors": ["BioEnvRebuilder plan contains manual/GitHub steps that are not approved for execution"],
                }
                write_bio_install_reports(run_dir, plan=plan, report=report, repair_attempts=[])
                return report
            report = apply_bio_install_plan(plan, yes=True)
            report["env_rebuilder"] = "bio"
            report["plan_source"] = plan.get("plan_source") or plan.get("mode") or "canonical_env"
            report["scanned_artifacts"] = plan.get("scanned_artifacts") or []
            report["lockfile_status"] = plan.get("lockfile_status") or plan.get("lock_trust")
            report["canonical_env_path"] = plan.get("canonical_env_path")
            report["install_plan_path"] = plan.get("install_plan_path")
            report["env_rebuild_report_path"] = plan.get("env_rebuild_report_path")
            report["manager"] = plan.get("manager")
            report["allow_install"] = plan.get("allow_install")
            report["resolved_env_path"] = resolved_env_path
            report["python_executable"] = bio_python_executable(plan, resolved_env_path, install_env)
            report["install_plan"] = plan
            report["manual_approval_required"] = False
            report["repair_attempts_requested"] = repair_attempts
            report["export_lock_requested"] = export_lock
            report["repair_attempts"] = []
            if report.get("status") == "failed":
                report["repair_attempts"] = run_repair_attempts(
                    report,
                    plan=plan,
                    requested_attempts=repair_attempts,
                )
                successful_retry = next((item for item in reversed(report["repair_attempts"]) if item.get("status_after_retry") == "executed"), None)
                if successful_retry:
                    repair_history = report["repair_attempts"]
                    report.update(successful_retry["retry_report"])
                    report["repair_attempts"] = repair_history
            if export_lock:
                lock_dir = (run_dir or Path(resolved_env_path)) / "lock"
                report["lock_outputs"] = export_lock_artifacts(
                    install_env,
                    lock_dir,
                    manager=str(plan.get("manager") or ""),
                    resolved_env_path=resolved_env_path,
                    python_executable=report.get("python_executable"),
                )
            write_bio_install_reports(run_dir, plan=plan, report=report, repair_attempts=report.get("repair_attempts") or [])
            return report
        except Exception as exc:  # noqa: BLE001 - evaluator should report structured install failure.
            report = {
                "status": "invalid",
                "errors": [str(exc)],
                "auto_install_performed": False,
                "env_rebuilder": "bio",
                "plan_source": None,
                "scanned_artifacts": [],
                "lockfile_status": None,
                "canonical_env_path": None,
                "install_plan_path": str(run_dir / "install_plan.json") if run_dir else None,
                "env_rebuild_report_path": str(run_dir / "env_rebuild_report.json") if run_dir else None,
                "manual_approval_required": False,
            }
            write_bio_install_reports(run_dir, plan=report, report=report, repair_attempts=[])
            return report
    evaluation_stub = {"execution": {"install_request": install_request}}
    try:
        plan = build_install_plan(
            evaluation_stub,
            install_env=install_env,
            create_conda_env=create_conda_env,
            python_version=python_version,
            override_request_env=True,
        )
        if plan.get("status") != "ready":
            return plan
        return execute_install_plan(plan, yes=True)
    except Exception as exc:  # noqa: BLE001 - evaluator should report structured install failure.
        return {"status": "invalid", "errors": [str(exc)], "auto_install_performed": False}


def declared_install_request(example: dict[str, Any], install_env: str | None, *, case_dir: str | Path | None = None) -> dict[str, Any]:
    spec = example.get("dependencies") if isinstance(example.get("dependencies"), dict) else {}
    python = list(spec.get("pip") or spec.get("python") or spec.get("required_python_packages") or [])
    conda = list(spec.get("conda") or [])
    r_packages = list(spec.get("r") or spec.get("cran") or spec.get("bioconductor") or [])
    r_github = list(spec.get("r_github") or [])
    allowed = list(spec.get("allowed_installers") or ["conda", "pip", "BiocManager", "install.packages"])
    return {
        "status": "approval_required",
        "target_environment": install_env,
        "case_dir": str(case_dir) if case_dir else None,
        "repo_dir": spec.get("repo_dir") or spec.get("source_repo_dir"),
        "source_dir": spec.get("source_dir"),
        "allowed_installers": allowed,
        "conda_channels": list(spec.get("conda_channels") or spec.get("channels") or []),
        "conda_packages": sorted(dict.fromkeys(str(item) for item in conda if str(item).strip())),
        "missing_python_packages": sorted(dict.fromkeys(str(item) for item in python if str(item).strip())),
        "missing_r_packages": sorted(dict.fromkeys(str(item) for item in r_packages if str(item).strip())),
        "r_github_packages": sorted(dict.fromkeys(str(item) for item in r_github if str(item).strip())),
        "repair_allowlist": sorted(dict.fromkeys(str(item) for item in (spec.get("repair_allowlist") or spec.get("allowed_repair_packages") or []) if str(item).strip())),
        "install_approval": dict(spec.get("install_approval") or spec.get("install_allowlist") or spec.get("approved_install_sources") or {}),
        "missing_executables": list(spec.get("executables") or []),
        "required_packages": sorted(dict.fromkeys(str(item) for item in [*conda, *python, *r_packages] if str(item).strip())),
        "safety": {
            "auto_install_performed": False,
            "notebook_execution_performed": False,
            "requires_explicit_user_approval": False,
            "approved_by_cli": True,
        },
    }


def bio_python_executable(plan: dict[str, Any], resolved_env_path: str, install_env: str) -> str:
    manager = str(plan.get("manager") or "")
    if manager == "uv":
        return uv_python_executable(resolved_env_path)
    return "python"


def add_bio_plan_report_paths(plan: dict[str, Any], run_dir: Path | None) -> None:
    if run_dir is None:
        return
    plan["install_plan_path"] = str(run_dir / "install_plan.json")
    plan["env_rebuild_report_path"] = str(run_dir / "env_rebuild_report.json")
    plan["repair_attempts_path"] = str(run_dir / "repair_attempts.json")


def run_repair_attempts(report: dict[str, Any], *, plan: dict[str, Any], requested_attempts: int) -> list[dict[str, Any]]:
    if plan.get("frozen") is True or plan.get("mode") == "lockfile_restore" or plan.get("repair_policy") == "suggestion_only":
        diagnosis = diagnose_failure(report)
        return [
            {
                "attempt": 0,
                "status": "diagnosed_only_frozen_lockfile",
                "diagnosis": diagnosis,
                "repair_suggestion": "Do not mutate the restored lockfile environment; retry in a separate derived canonical environment if probe fails.",
            }
        ]
    if requested_attempts <= 0:
        diagnosis = diagnose_failure(report)
        return [{"attempt": 0, "status": "diagnosed_only", "diagnosis": diagnosis}]
    attempts: list[dict[str, Any]] = []
    current_report = report
    failure_mode_counts: dict[str, int] = {}
    for attempt_index in range(1, requested_attempts + 1):
        diagnosis = diagnose_failure(current_report)
        repair_plan = safe_repair_plan(diagnosis, plan, failure_mode_counts=failure_mode_counts)
        if not repair_plan.get("commands"):
            attempts.append({"attempt": attempt_index, "status": "no_safe_auto_repair", "diagnosis": diagnosis, "repair_plan": repair_plan})
            break
        repair_report = apply_bio_install_plan(repair_plan, yes=True)
        retry_report = apply_bio_install_plan(plan, yes=True) if repair_report.get("status") == "executed" else repair_report
        attempts.append(
            {
                "attempt": attempt_index,
                "status": "retried_safe_repair",
                "diagnosis": diagnosis,
                "repair_plan": repair_plan,
                "repair_report": repair_report,
                "retry_report": retry_report,
                "status_after_retry": retry_report.get("status"),
            }
        )
        current_report = retry_report
        if retry_report.get("status") == "executed":
            break
    return attempts


def safe_repair_plan(diagnosis: dict[str, Any], original_plan: dict[str, Any], *, failure_mode_counts: dict[str, int] | None = None) -> dict[str, Any]:
    commands = []
    env = str(original_plan.get("env") or "")
    failure_mode_counts = failure_mode_counts if failure_mode_counts is not None else {}
    blocked: list[dict[str, Any]] = []
    allowlist = set(str(item) for item in original_plan.get("repair_allowlist") or [])
    for finding in diagnosis.get("findings") or []:
        mode = finding.get("failure_mode")
        repair_key = repair_attempt_key(finding)
        failure_mode_counts[repair_key] = failure_mode_counts.get(repair_key, 0) + 1
        if failure_mode_counts[repair_key] > 2:
            blocked.append({"failure_mode": mode, "repair_key": repair_key, "reason": "same failure repair limit exceeded"})
            continue
        if mode == "missing_r_package" and finding.get("package"):
            from paper2skill.env_rebuilder.planner import resolve_r_packages

            resolved = resolve_r_packages([str(finding["package"])])
            packages = resolved.get("conda_packages") or []
            repair_filter = "route_table"
            if not packages:
                packages = allowlisted_repair_packages(str(finding["package"]), allowlist)
                repair_filter = "case_gold_allowlist" if packages else repair_filter
            if packages:
                commands.append(
                    {
                        "kind": "conda_packages",
                        "tier": 3,
                        "installer": "mamba_or_conda",
                        "packages": packages,
                        "repair_patch_type": "additive",
                        "repair_filter": repair_filter,
                        "command": ["mamba", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", *packages],
                        "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", *packages],
                    }
                )
            else:
                blocked.append({"failure_mode": mode, "reason": "R package not in known route table", "package": finding.get("package")})
        elif mode == "missing_executable" and finding.get("executable"):
            from paper2skill.env_rebuilder.routes import route_cli_executables

            resolved = route_cli_executables([str(finding["executable"])])
            packages = resolved.get("conda_packages") or []
            repair_filter = "route_table"
            if not packages:
                packages = allowlisted_repair_packages(str(finding["executable"]), allowlist)
                repair_filter = "case_gold_allowlist" if packages else repair_filter
            if packages:
                commands.append(
                    {
                        "kind": "conda_packages",
                        "tier": 3,
                        "installer": "mamba_or_conda",
                        "packages": packages,
                        "repair_patch_type": "additive",
                        "repair_filter": repair_filter,
                        "command": ["mamba", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", *packages],
                        "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", *packages],
                    }
                )
            else:
                blocked.append({"failure_mode": mode, "reason": "executable not in known route table", "executable": finding.get("executable")})
        elif mode == "python_source_build_failure":
            packages = conda_binary_repair_packages(original_plan)
            if packages and "conda" in str(original_plan.get("manager") or ""):
                commands.append(
                    {
                        "kind": "conda_packages",
                        "tier": 3,
                        "installer": "mamba_or_conda",
                        "packages": packages,
                        "repair_patch_type": "route_migration",
                        "repair_filter": "route_table",
                        "command": ["mamba", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", *packages],
                        "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "--strict-channel-priority", "-c", "conda-forge", *packages],
                    }
                )
            else:
                blocked.append({"failure_mode": mode, "reason": "no conda binary repair package found in original plan"})
        elif finding.get("manual_block"):
            blocked.append({"failure_mode": mode, "reason": "finding requires manual review", "finding": finding})
    repair_plan = dict(original_plan)
    repair_plan["status"] = "ready" if commands else "blocked_manual"
    repair_plan["commands"] = commands
    repair_plan["repair_of"] = "install_failure"
    repair_plan["blocked_repairs"] = blocked
    repair_plan["manual_approval_required"] = not bool(commands)
    return repair_plan


def repair_attempt_key(finding: dict[str, Any]) -> str:
    mode = str(finding.get("failure_mode") or "unknown")
    subject = finding.get("package") or finding.get("executable") or finding.get("requirement") or ""
    return f"{mode}:{subject}" if subject else mode


def allowlisted_repair_packages(name: str, allowlist: set[str]) -> list[str]:
    from paper2skill.env_rebuilder.routes import package_key, safe_package_name

    key = package_key(name)
    packages = []
    for item in allowlist:
        if not safe_package_name(item):
            continue
        item_key = package_key(item)
        if item == name or item_key == key or item_key.endswith(key):
            packages.append(item)
    return sorted(dict.fromkeys(packages))


def conda_binary_repair_packages(plan: dict[str, Any]) -> list[str]:
    from paper2skill.env_rebuilder.routes import CONDA_BINARY_PYTHON

    packages: list[str] = []
    for command in plan.get("commands") or []:
        if command.get("installer") != "uv":
            continue
        for package in command.get("packages") or []:
            name = re.split(r"[<>=!~]", str(package), maxsplit=1)[0].strip().lower()
            if name in CONDA_BINARY_PYTHON:
                packages.append(str(package))
    return sorted(dict.fromkeys(packages))


def write_bio_install_reports(run_dir: Path | None, *, plan: dict[str, Any], report: dict[str, Any], repair_attempts: list[dict[str, Any]]) -> None:
    if run_dir is None:
        return
    try:
        write_json(run_dir / "install_plan.json", plan)
        write_json(run_dir / "env_rebuild_report.json", report)
        write_json(run_dir / "repair_attempts.json", {"status": "recorded", "attempts": repair_attempts})
    except OSError:
        return


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


def run_preflight(skill_path: Path, manifest_path: Path, run_dir: Path, *, runner=None) -> dict[str, Any] | None:
    preflight = skill_path / "scripts" / "preflight.py"
    if not preflight.exists():
        return None
    runner = runner or (lambda args: [sys.executable, *args])
    try:
        completed = subprocess.run(
            runner([str(preflight), "--manifest", str(manifest_path), "--out", str(run_dir)]),
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


def run_output_validator(skill_path: Path, run_dir: Path, *, runner=None) -> dict[str, Any] | None:
    validator = skill_path / "scripts" / "validate_outputs.py"
    if not validator.exists():
        return None
    runner = runner or (lambda args: [sys.executable, *args])
    try:
        completed = subprocess.run(
            runner([str(validator), "--result", str(run_dir)]),
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
