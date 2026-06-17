from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from paper2skill.build_validation import validate_build
from paper2skill.collectors.path_sanitizer import public_data
from paper2skill.common import ensure_dir, write_json, write_text
from paper2skill.compiler import annotate_run_trace_promotion, build_empty_run_trace
from paper2skill.generators.codex_skill_generator import generate_skill


AGENTIC_PHASES = [
    "catalog",
    "build_l1",
    "env_probe",
    "data_probe",
    "adapter_materialize",
    "smoke_run",
    "error_classify",
    "repair",
    "rerun",
    "promote",
    "emit_skill",
]


@dataclass
class ReproduceConfig:
    confirm_run: bool = False
    install_policy: str = "never"
    repair_budget: int = 2
    smoke_timeout: int = 600
    data_cache_dir: str | None = None
    target_maturity: str = "L2"
    validation_python: str | None = None
    validation_env_prefix: str | None = None
    example_id: str | None = None


def run_agentic_reproduction(context: dict[str, Any], out_dir: str | Path, config: ReproduceConfig) -> dict[str, Any]:
    skill_dir = generate_skill(context, out_dir).resolve()
    agentic_dir = ensure_dir(skill_dir / "agentic_run")
    repair_log = agentic_dir / "repair_log.jsonl"
    write_text(repair_log, "")
    write_json(agentic_dir / "phase_plan.json", {"phases": AGENTIC_PHASES, "config": asdict(config)})

    catalog_summary = tutorial_catalog_summary(context.get("tutorial_catalog") or {})
    append_repair_log(repair_log, "catalog", "pass", catalog_summary)

    build_validation = validate_build(skill_dir, validation_depth="dry_run", example_id=config.example_id)
    write_json(agentic_dir / "initial_build_validation.json", build_validation)
    append_repair_log(repair_log, "build_l1", "pass" if build_validation.get("passed") else "fail", build_validation)
    if not build_validation.get("passed"):
        result = finalize_agentic_result(
            skill_dir,
            agentic_dir,
            status="fail",
            config=config,
            message="L1 package validation failed before reproduction could run.",
            validation=build_validation,
        )
        write_json(agentic_dir / "promotion_report.json", result["promotion_report"])
        return result

    env_delta = environment_delta(skill_dir, context, config)
    write_json(agentic_dir / "env_delta.json", env_delta)
    append_repair_log(repair_log, "env_probe", env_delta.get("status", "recorded"), env_delta)

    data_report = data_probe(config.data_cache_dir)
    write_json(agentic_dir / "data_probe.json", data_report)
    append_repair_log(repair_log, "data_probe", data_report.get("status", "recorded"), data_report)

    adapter_report = adapter_materialization_report(skill_dir, context.get("tutorial_catalog") or {}, config.example_id)
    write_json(agentic_dir / "adapter_materialize.json", adapter_report)
    append_repair_log(repair_log, "adapter_materialize", adapter_report.get("status", "recorded"), adapter_report)

    if not config.confirm_run:
        trace = build_empty_run_trace(skill_dir=skill_dir, example_id=selected_example_id(context.get("tutorial_catalog") or {}, config.example_id), status="blocked_confirmation_required")
        trace["message"] = "paper2skill reproduce requires --confirm-run yes before executing generated skill code."
        trace = annotate_run_trace_promotion(trace)
        promotion = blocked_promotion_report("confirm_run_required", trace)
        write_json(agentic_dir / "run_trace.json", trace)
        write_json(agentic_dir / "promotion_report.json", promotion)
        append_repair_log(repair_log, "smoke_run", "blocked_confirmation_required", {"message": trace["message"]})
        return finalize_agentic_result(
            skill_dir,
            agentic_dir,
            status="blocked_confirmation_required",
            config=config,
            message=trace["message"],
            run_trace=trace,
            promotion_report=promotion,
        )

    final_validation: dict[str, Any] = {}
    final_failure: dict[str, Any] = {}
    max_attempts = max(0, config.repair_budget) + 1
    for attempt in range(max_attempts):
        stage = "smoke_run" if attempt == 0 else "rerun"
        attempt_dir = ensure_dir(agentic_dir / "attempts" / f"attempt_{attempt:02d}")
        validation = validate_build(
            skill_dir,
            validation_depth="data_smoke",
            result_dir=attempt_dir / "result",
            timeout_seconds=config.smoke_timeout,
            example_id=config.example_id,
            env_prefix=config.validation_env_prefix,
            python_executable=config.validation_python,
            example_data_cache_dir=config.data_cache_dir,
        )
        final_validation = validation
        write_json(attempt_dir / "validation.json", validation)
        write_json(skill_dir / "build_validation" / "build_validation.json", validation)
        append_repair_log(repair_log, stage, "pass" if validation.get("passed") else "fail", {"attempt": attempt, "validation": validation})
        if validation.get("passed"):
            trace = load_json_mapping(skill_dir / "debug" / "build_validation_run_trace.promoted.json")
            promotion = load_json_mapping(skill_dir / "build_validation" / "promotion_report.json")
            if not trace:
                trace = build_empty_run_trace(skill_dir=skill_dir, example_id=selected_example_id(context.get("tutorial_catalog") or {}, config.example_id), status="fail")
                trace["message"] = "validation passed but no promoted run trace was emitted"
                trace = annotate_run_trace_promotion(trace)
            if not promotion:
                promotion = blocked_promotion_report("promotion_report_missing", trace)
            write_json(agentic_dir / "run_trace.json", trace)
            write_json(agentic_dir / "promotion_report.json", promotion)
            append_repair_log(repair_log, "promote", "pass" if promotion.get("promoted") else "fail", promotion)
            result_status = "pass" if promotion.get("promoted") and maturity_satisfies(promotion.get("maturity") or {}, config.target_maturity) else "partial"
            message = "Agentic reproduction reached verified maturity." if result_status == "pass" else "Reproduction passed smoke but did not reach requested target maturity."
            result = finalize_agentic_result(
                skill_dir,
                agentic_dir,
                status=result_status,
                config=config,
                message=message,
                validation=validation,
                run_trace=trace,
                promotion_report=promotion,
            )
            append_repair_log(repair_log, "emit_skill", result_status, result)
            return result

        failure = classify_agentic_failure(validation)
        final_failure = failure
        write_json(attempt_dir / "failure_classification.json", failure)
        append_repair_log(repair_log, "error_classify", failure["code"], {"attempt": attempt, "failure": failure})
        if attempt >= max_attempts - 1:
            break
        repair = apply_agentic_repair(skill_dir, failure, attempt=attempt + 1, config=config)
        write_json(attempt_dir / "repair_action.json", repair)
        append_repair_log(repair_log, "repair", repair.get("status", "recorded"), repair)
        if repair.get("status") == "not_repairable":
            break

    trace = build_empty_run_trace(skill_dir=skill_dir, example_id=selected_example_id(context.get("tutorial_catalog") or {}, config.example_id), status="fail")
    trace["failure_repairs"] = read_jsonl(repair_log)
    trace["message"] = "Agentic reproduction failed before promotion."
    trace = annotate_run_trace_promotion(trace)
    promotion = blocked_promotion_report(final_failure.get("code") or "smoke_failed", trace)
    write_json(agentic_dir / "run_trace.json", trace)
    write_json(agentic_dir / "promotion_report.json", promotion)
    result = finalize_agentic_result(
        skill_dir,
        agentic_dir,
        status="fail",
        config=config,
        message="Agentic reproduction failed before promotion.",
        validation=final_validation,
        run_trace=trace,
        promotion_report=promotion,
        failure=final_failure,
    )
    append_repair_log(repair_log, "emit_skill", "fail", result)
    return result


def tutorial_catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    return {
        "status": "pass" if examples else "fail",
        "default_example_id": catalog.get("default_example_id"),
        "example_count": len(examples),
        "examples": [
            {
                "example_id": item.get("example_id"),
                "source": item.get("source"),
                "data_kind": item.get("data_kind"),
                "entrypoint_type": item.get("entrypoint_type"),
                "verification": item.get("verification"),
            }
            for item in examples
            if isinstance(item, dict)
        ],
        "warnings": catalog.get("warnings") or [],
    }


def environment_delta(skill_dir: Path, context: dict[str, Any], config: ReproduceConfig) -> dict[str, Any]:
    runner = validation_runner(config)
    report: dict[str, Any] = {
        "status": "recorded",
        "install_policy": config.install_policy,
        "runner": runner,
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "before": {},
        "import_probe": {},
        "install": {"status": "not_requested"},
        "after": {},
    }
    if not config.confirm_run:
        report["status"] = "blocked_confirmation_required"
        report["message"] = "External environment probes require --confirm-run yes."
        return public_data(report, skill_dir)
    report["before"] = pip_snapshot(runner, cwd=skill_dir)
    packages = python_import_candidates(context.get("environment_spec") or {})
    report["import_probe"] = import_probe(runner, packages, cwd=skill_dir)
    if config.install_policy in {"plan", "yes"}:
        report["install"] = install_probe_or_apply(skill_dir, runner, config.install_policy)
    report["after"] = pip_snapshot(runner, cwd=skill_dir) if config.install_policy == "yes" else {}
    install_ok = report["install"].get("status") not in {"dry_run_failed", "install_failed"}
    import_ok = report["import_probe"].get("status") in {"pass", "skipped"}
    report["status"] = "pass" if install_ok and import_ok else "fail"
    return public_data(report, skill_dir)


def validation_runner(config: ReproduceConfig) -> list[str]:
    if config.validation_python:
        return [str(config.validation_python)]
    if config.validation_env_prefix:
        return ["conda", "run", "-p", str(config.validation_env_prefix), "python"]
    return [sys.executable]


def pip_snapshot(runner: list[str], *, cwd: Path) -> dict[str, Any]:
    return {
        "pip_freeze": run_command([*runner, "-m", "pip", "freeze"], cwd=cwd, timeout=120),
        "pip_check": run_command([*runner, "-m", "pip", "check"], cwd=cwd, timeout=120),
    }


def install_probe_or_apply(skill_dir: Path, runner: list[str], policy: str) -> dict[str, Any]:
    requirements = skill_dir / "assets" / "requirements.txt"
    if not requirements.is_file() or not requirements.read_text(encoding="utf-8").strip():
        return {"status": "no_requirements", "path": "assets/requirements.txt"}
    dry_run = run_command([*runner, "-m", "pip", "install", "--dry-run", "-r", str(requirements)], cwd=skill_dir, timeout=600)
    result: dict[str, Any] = {"status": "planned" if dry_run["returncode"] == 0 else "dry_run_failed", "dry_run": dry_run}
    if policy == "yes" and dry_run["returncode"] == 0:
        install = run_command([*runner, "-m", "pip", "install", "-r", str(requirements)], cwd=skill_dir, timeout=1200)
        result["install"] = install
        result["status"] = "installed" if install["returncode"] == 0 else "install_failed"
    return result


def import_probe(runner: list[str], packages: list[str], *, cwd: Path) -> dict[str, Any]:
    if not packages:
        return {"status": "skipped", "packages": []}
    script = (
        "import importlib, json;"
        f"packages={json.dumps(packages)};"
        "rows=[];"
        "\nfor name in packages:\n"
        "    try:\n"
        "        importlib.import_module(name); rows.append({'name': name, 'status': 'pass'})\n"
        "    except Exception as exc:\n"
        "        rows.append({'name': name, 'status': 'fail', 'error_type': type(exc).__name__, 'error': repr(exc)})\n"
        "print(json.dumps(rows))"
    )
    completed = run_command([*runner, "-c", script], cwd=cwd, timeout=120)
    rows: list[dict[str, Any]] = []
    try:
        loaded = json.loads(completed.get("stdout", "[]"))
        if isinstance(loaded, list):
            rows = [item for item in loaded if isinstance(item, dict)]
    except json.JSONDecodeError:
        rows = []
    status = "pass" if completed["returncode"] == 0 and all(item.get("status") == "pass" for item in rows) else "fail"
    return {"status": status, "packages": rows, "command": completed}


def python_import_candidates(environment_spec: dict[str, Any]) -> list[str]:
    packages = ((environment_spec.get("python") or {}).get("packages") or [])
    names: list[str] = []
    aliases = {"scvi-tools": "scvi", "pyyaml": "yaml", "scikit-learn": "sklearn"}
    for item in packages:
        if isinstance(item, dict):
            spec = str(item.get("import_name") or item.get("spec") or item.get("name") or "")
        else:
            spec = str(item)
        name = normalize_import_name(spec)
        if not name:
            continue
        names.append(aliases.get(name, name).replace("-", "_"))
    return sorted(dict.fromkeys(names))


def normalize_import_name(spec: str) -> str:
    spec = spec.strip()
    if not spec or spec.startswith(("-", "git+", "http://", "https://")):
        return ""
    spec = spec.split(";", 1)[0]
    spec = re.split(r"\s+@\s+", spec, maxsplit=1)[0]
    spec = re.split(r"\s*(?:[<>=!~]=?)", spec, maxsplit=1)[0]
    spec = spec.split("[", 1)[0]
    return spec.strip()


def data_probe(data_cache_dir: str | None) -> dict[str, Any]:
    if not data_cache_dir:
        return {"status": "skipped", "message": "No --data-cache-dir provided."}
    cache = Path(data_cache_dir)
    if not cache.is_dir():
        return {"status": "missing", "data_cache_dir": str(cache)}
    files = []
    for path in sorted(item for item in cache.iterdir() if item.is_file())[:200]:
        files.append({"name": path.name, "suffix": path.suffix.lower(), "size_bytes": path.stat().st_size})
    return {"status": "pass", "data_cache_dir": str(cache), "file_count": len(files), "files": files}


def adapter_materialization_report(skill_dir: Path, catalog: dict[str, Any], example_id: str | None) -> dict[str, Any]:
    selected = selected_example(catalog, example_id)
    spec = load_yaml_mapping(skill_dir / "references" / "adapter_spec.yaml")
    return {
        "status": "pass" if selected else "blocked",
        "example_id": selected.get("example_id") if selected else example_id,
        "example_source": selected.get("source") if selected else None,
        "adapter_type": spec.get("adapter_type"),
        "adapter_status": spec.get("status"),
        "entrypoint": spec.get("entrypoint"),
        "expected_outputs": selected.get("expected_outputs") or ((selected.get("output_contract") or {}).get("required_files") if selected else []),
    }


def selected_example(catalog: dict[str, Any], example_id: str | None) -> dict[str, Any]:
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    target = example_id or catalog.get("default_example_id")
    for item in examples:
        if isinstance(item, dict) and item.get("example_id") == target:
            return item
    return examples[0] if examples and isinstance(examples[0], dict) else {}


def selected_example_id(catalog: dict[str, Any], example_id: str | None) -> str | None:
    selected = selected_example(catalog, example_id)
    return str(selected.get("example_id")) if selected.get("example_id") else example_id


def classify_agentic_failure(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    failed_stage = execution.get("failed_stage") or payload.get("failed_stage")
    if any(token in text for token in ["resolutionimpossible", "cannot install", "no matching distribution", "pkgutil.impimporter", "ml-dtypes", "numpy==1.23", "python 3.12"]):
        return failure("dependency_conflict_legacy_python", "Legacy dependency pins appear incompatible with the active Python environment.", errors, failed_stage, text)
    if any(token in text for token in ["modulenotfounderror", "importerror", "no module named", "blocked_dependencies_missing"]):
        return failure("dependencies_missing", "A required import or dependency is missing.", errors, failed_stage, text)
    if any(token in text for token in ["filenotfounderror", "no such file or directory", "missing_cache_dir", "data path", "path does not exist"]):
        return failure("data_path_missing", "The selected tutorial data or expected output path is missing.", errors, failed_stage, text)
    if any(token in text for token in ["attributeerror", "unexpected keyword", "unexpected argument", "signature", "api drift", "get_latent", "qz", ".predict("]):
        return failure("api_signature_drift", "The installed API differs from the tutorial code or inferred adapter.", errors, failed_stage, text)
    if any(token in text for token in ["output_contract_mismatch", "expected_outputs_missing", "required_outputs_missing", "output_validation_failed", "output missing"]):
        return failure("output_missing", "Adapter ran but did not satisfy the output contract.", errors, failed_stage, text)
    return failure("unknown_execution_failure", "The smoke run failed without a known repair class.", errors, failed_stage, text)


def failure(code: str, summary: str, errors: list[Any], failed_stage: Any, text: str) -> dict[str, Any]:
    return {
        "code": code,
        "summary": summary,
        "failed_stage": failed_stage,
        "errors": errors,
        "evidence_tail": tail_text(text, max_chars=4000),
    }


def apply_agentic_repair(skill_dir: Path, failure_info: dict[str, Any], *, attempt: int, config: ReproduceConfig) -> dict[str, Any]:
    code = failure_info.get("code")
    if code == "api_signature_drift":
        repair_config_path = skill_dir / "references" / "agentic_repair_config.json"
        repair_config = load_json_mapping(repair_config_path)
        repairs = repair_config.get("repairs") if isinstance(repair_config.get("repairs"), dict) else {}
        repairs["scgen_latent_arithmetic_fallback"] = True
        repair_config.update(
            {
                "schema_version": 1,
                "repairs": repairs,
                "last_attempt": attempt,
                "reason": failure_info,
                "policy": "adapter_compatibility_repair_only",
            }
        )
        write_json(repair_config_path, repair_config)
        append_repair_note(skill_dir, attempt, "api_signature_drift", "Enabled generated adapter compatibility fallback for scGen-style predict/API drift.")
        return {
            "status": "applied",
            "action": "enable_adapter_compatibility_fallback",
            "files_changed": ["references/agentic_repair_config.json", "references/agentic_repair_notes.md"],
            "hypothesis": "The official tutorial API drift can be handled inside the generated adapter without modifying upstream source.",
        }
    if code == "dependency_conflict_legacy_python":
        changed = relax_legacy_requirement_pins(skill_dir / "assets" / "requirements.txt")
        append_repair_note(skill_dir, attempt, "dependency_conflict_legacy_python", "Relaxed legacy exact pins where present and recorded Python 3.12 compatibility repair guidance.")
        return {
            "status": "applied" if changed else "recorded",
            "action": "relax_legacy_requirement_pins",
            "files_changed": ["assets/requirements.txt", "references/agentic_repair_notes.md"] if changed else ["references/agentic_repair_notes.md"],
            "hypothesis": "Legacy exact pins are blocking dependency resolution in the current Python runtime.",
        }
    if code == "output_missing":
        append_repair_note(skill_dir, attempt, "output_missing", "Recorded output-contract failure for adapter refinement; no upstream source files were modified.")
        return {"status": "recorded", "action": "record_output_contract_repair_needed", "files_changed": ["references/agentic_repair_notes.md"]}
    if code in {"dependencies_missing", "data_path_missing"}:
        append_repair_note(skill_dir, attempt, str(code), "Recorded missing dependency/data evidence; automatic repair requires user-approved install policy or matching data cache files.")
        return {"status": "recorded", "action": f"record_{code}", "files_changed": ["references/agentic_repair_notes.md"]}
    append_repair_note(skill_dir, attempt, str(code or "unknown"), "No deterministic adapter-only repair is available.")
    return {"status": "not_repairable", "action": "stop_no_deterministic_repair", "files_changed": ["references/agentic_repair_notes.md"]}


def relax_legacy_requirement_pins(path: Path) -> bool:
    if not path.is_file():
        return False
    legacy = {"numpy", "pandas", "scipy", "scanpy", "anndata", "scvi-tools", "scgen", "torch", "tensorflow", "ml-dtypes"}
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        name = normalize_import_name(stripped).lower()
        if "==" in stripped and name in legacy:
            next_lines.append(stripped.replace("==", ">=", 1))
            changed = True
        else:
            next_lines.append(line)
    if changed:
        backup = path.with_suffix(path.suffix + ".before_agentic_repair")
        if not backup.exists():
            backup.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    return changed


def append_repair_note(skill_dir: Path, attempt: int, code: str, message: str) -> None:
    path = skill_dir / "references" / "agentic_repair_notes.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Agentic Repair Notes\n\n"
    entry = f"## Attempt {attempt}: {code}\n\n{message}\n\n"
    write_text(path, existing + entry)


def finalize_agentic_result(
    skill_dir: Path,
    agentic_dir: Path,
    *,
    status: str,
    config: ReproduceConfig,
    message: str,
    validation: dict[str, Any] | None = None,
    run_trace: dict[str, Any] | None = None,
    promotion_report: dict[str, Any] | None = None,
    failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    promotion = promotion_report or blocked_promotion_report("not_promoted", run_trace or {})
    result = {
        "status": status,
        "message": message,
        "skill_dir": str(skill_dir),
        "agentic_run_dir": str(agentic_dir),
        "target_maturity": config.target_maturity,
        "maturity": (promotion.get("maturity") if isinstance(promotion, dict) else None) or {},
        "promoted": bool(promotion.get("promoted")) if isinstance(promotion, dict) else False,
        "artifacts": {
            "repair_log": str(agentic_dir / "repair_log.jsonl"),
            "env_delta": str(agentic_dir / "env_delta.json"),
            "run_trace": str(agentic_dir / "run_trace.json"),
            "promotion_report": str(agentic_dir / "promotion_report.json"),
        },
        "validation": validation or {},
        "failure": failure or {},
        "promotion_report": promotion,
    }
    return public_data(result, skill_dir)


def blocked_promotion_report(reason: str, trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "promoted": False,
        "reason": reason,
        "promotion_rejections": trace.get("promotion_rejections") or ["run_trace_output_validation_not_passed"],
        "maturity": {"level": "L1", "status": "contract_only"},
    }


def maturity_satisfies(maturity: dict[str, Any], target: str) -> bool:
    ranks = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    level = str(maturity.get("level") or "L1")
    return ranks.get(level, 0) >= ranks.get(target, 2)


def run_command(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout)
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": tail_text(completed.stdout),
            "stderr": tail_text(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "status": "timeout",
            "stdout": tail_text(exc.stdout or ""),
            "stderr": tail_text(exc.stderr or ""),
        }
    except OSError as exc:
        return {
            "command": command,
            "returncode": 127,
            "status": "os_error",
            "stdout": "",
            "stderr": repr(exc),
        }


def append_repair_log(path: Path, phase: str, status: str, payload: dict[str, Any]) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "status": status,
        "payload": public_data(payload, path.parent.parent),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def load_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def tail_text(value: object, *, max_chars: int = 8000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value or "")
    return text[-max_chars:] if len(text) > max_chars else text
