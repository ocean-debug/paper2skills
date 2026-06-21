from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


RUN_TRACE_SCHEMA_VERSION = 1


def build_empty_run_trace(*, skill_dir: str | Path | None = None, example_id: str | None = None, status: str = "not_run") -> dict[str, Any]:
    return {
        "schema_version": RUN_TRACE_SCHEMA_VERSION,
        "trace_type": "paper2skill_run_trace",
        "status": status,
        "skill_dir": str(skill_dir) if skill_dir else None,
        "example_id": example_id,
        "environment_probe": {},
        "install_plan": {},
        "installed_packages": {},
        "commands": [],
        "api_sequence": [],
        "input_bindings": {},
        "produced_files": [],
        "stdout_tail": "",
        "stderr_tail": "",
        "failure_repairs": [],
        "output_validation": {"status": "not_run"},
        "adapter_report": {},
        "result_json": {},
        "promotion_ready": False,
        "promotion_rejections": [],
        "resource_usage": {},
    }


def ingest_run_directory(run_dir: str | Path, *, skill_dir: str | Path | None = None, example_id: str | None = None) -> dict[str, Any]:
    root = Path(run_dir)
    trace = build_empty_run_trace(skill_dir=skill_dir, example_id=example_id, status="ingested")
    trace["produced_files"] = produced_files(root)
    trace["output_validation"] = load_output_validation(root)
    trace["environment_probe"] = load_first_mapping(
        [
            root / "qc" / "environment_report.json",
            root / "environment_report.json",
            root / "analysis_summary.json",
        ]
    )
    trace["input_bindings"] = load_first_mapping([root / "workflow" / "plan.json", root / "input_manifest.yaml", root / "manifest.yaml"])
    trace["install_plan"] = load_first_mapping([root / "qc" / "missing_dependencies.json", root / "install_plan.json"])
    trace["adapter_report"] = load_first_mapping([root / "workflow" / "adapter_report.json"])
    trace["result_json"] = load_first_mapping([root / "result.json"])
    trace["stdout_tail"] = tail_first_existing([root / "stdout.log", root / "logs" / "stdout.log", root / "logs" / "run.log"])
    trace["stderr_tail"] = tail_first_existing([root / "stderr.log", root / "logs" / "stderr.log"])
    trace["status"] = "pass" if run_trace_passed(trace) else "fail"
    return annotate_run_trace_promotion(trace)


def run_trace_passed(trace: dict[str, Any]) -> bool:
    status = str(trace.get("status") or "").lower()
    if status not in {"pass", "success", "ingested"}:
        return False
    validation = trace.get("output_validation") if isinstance(trace.get("output_validation"), dict) else {}
    if validation.get("status") == "pass":
        return True
    return False


def run_trace_promotion_ready(trace: dict[str, Any]) -> bool:
    return not run_trace_promotion_rejections(trace)


def annotate_run_trace_promotion(trace: dict[str, Any]) -> dict[str, Any]:
    rejections = run_trace_promotion_rejections(trace)
    trace["promotion_ready"] = not rejections
    trace["promotion_rejections"] = rejections
    return trace


def run_trace_promotion_rejections(trace: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    status = str(trace.get("status") or "").lower()
    if status not in {"pass", "success", "ingested"}:
        reasons.append("run_trace_status_not_passed")
    validation = trace.get("output_validation") if isinstance(trace.get("output_validation"), dict) else {}
    if validation.get("status") != "pass":
        reasons.append("run_trace_output_validation_not_passed")
    if run_trace_is_demo(trace):
        reasons.append("demo_trace_not_promotable")
    result = trace.get("result_json") if isinstance(trace.get("result_json"), dict) else {}
    if str(result.get("status") or "").lower() == "dry_run":
        reasons.append("dry_run_trace_not_promotable")
    adapter_report = trace.get("adapter_report") if isinstance(trace.get("adapter_report"), dict) else {}
    if not adapter_report:
        reasons.append("adapter_report_missing")
    elif str(adapter_report.get("status") or "").lower() != "pass":
        reasons.append("adapter_execution_not_passed")
    return reasons


def run_trace_is_demo(trace: dict[str, Any]) -> bool:
    adapter_report = trace.get("adapter_report") if isinstance(trace.get("adapter_report"), dict) else {}
    if adapter_report.get("demo_mode") is True:
        return True
    result = trace.get("result_json") if isinstance(trace.get("result_json"), dict) else {}
    if result.get("demo_mode") is True:
        return True
    for container in [trace.get("input_bindings"), result.get("workflow_summary")]:
        if not isinstance(container, dict):
            continue
        manifest = container.get("manifest") if isinstance(container.get("manifest"), dict) else container
        mode = (((manifest.get("inputs") or {}).get("algorithm") or {}).get("mode"))
        if str(mode).lower() == "demo":
            return True
    return False


def produced_files(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = str(path)
        rows.append({"path": rel, "size_bytes": path.stat().st_size})
    return rows


def load_output_validation(root: Path) -> dict[str, Any]:
    return load_first_mapping(
        [
            root / "qc" / "output_validation.json",
            root / "output_validation.json",
            root / "validation.json",
        ]
    ) or {"status": "not_run"}


def load_first_mapping(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def tail_first_existing(paths: list[Path], *, max_chars: int = 4000) -> str:
    for path in paths:
        if path.exists() and path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            return text[-max_chars:]
    return ""
