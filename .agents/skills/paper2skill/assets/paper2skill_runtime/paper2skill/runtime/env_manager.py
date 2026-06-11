from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH, public_data
from paper2skill.common import ensure_dir, write_json, write_text
from paper2skill.runtime.install_planner import build_install_plan, render_install_plan_markdown
from paper2skill.runtime.python_probe import probe_python
from paper2skill.runtime.r_probe import forced_missing_executables, probe_r

ALLOWED_VERSION_ARGS = {("--version",), ("-V",), ("version",)}


def load_environment_spec(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path)
    text = spec_path.read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def effective_install_policy(policy: str, non_interactive: bool | None = None) -> str:
    if non_interactive is None:
        non_interactive = bool(os.environ.get("CI")) or not sys.stdin.isatty()
    if policy == "ask" and non_interactive:
        return "never"
    return policy


def probe_executables(executables: list[dict[str, Any] | str] | None = None) -> list[dict[str, Any]]:
    forced = forced_missing_executables()
    records = []
    for item in executables or []:
        if isinstance(item, str):
            name = item
            required = True
            version_command = None
        else:
            name = item["name"]
            required = item.get("required", True)
            version_command = item.get("version_command")
        path = None if name in forced else shutil.which(name)
        version = None
        if path and version_command:
            try:
                version_args = normalize_version_command(name, path, version_command)
                proc = subprocess.run(version_args, text=True, capture_output=True, check=False)
                version = (proc.stdout or proc.stderr).strip().splitlines()[0]
            except Exception:
                version = None
        records.append({"name": name, "path": path, "available": path is not None, "version": version, "required": required})
    return records


def normalize_version_command(name: str, path: str, version_command: Any) -> list[str]:
    if isinstance(version_command, str):
        args = [version_command]
    else:
        args = list(version_command)
    if not args:
        raise ValueError("empty version command")
    if Path(args[0]).name == name:
        args = args[1:]
    if tuple(args) not in ALLOWED_VERSION_ARGS:
        raise ValueError("unsupported version command")
    return [path, *args]


def inspect_environment(spec: dict[str, Any], non_interactive: bool | None = None) -> dict[str, Any]:
    policy = spec.get("install_policy", "ask")
    python_spec = spec.get("python", {}) or {}
    r_spec = spec.get("r", {}) or {}
    report = {
        "status": "pass",
        "python": probe_python(python_spec.get("packages", [])),
        "r": probe_r(r_spec.get("packages", []), r_spec.get("required", False)),
        "executables": probe_executables(spec.get("executables", [])),
        "install_policy": policy,
        "effective_install_policy": effective_install_policy(policy, non_interactive),
    }
    missing_python = [pkg for pkg in report["python"]["packages"] if pkg.get("required") and not pkg.get("installed")]
    missing_r = [pkg for pkg in report["r"]["packages"] if pkg.get("required") and not pkg.get("installed")]
    missing_execs = [item for item in report["executables"] if item.get("required") and not item.get("available")]
    if report["r"].get("required") and not report["r"].get("rscript_available"):
        report["status"] = "blocked_runtime_missing"
    elif missing_python or missing_r or missing_execs:
        report["status"] = "blocked_dependencies_missing"
    return report


def public_environment_report(report: dict[str, Any], base_dir: str | Path | None = None) -> dict[str, Any]:
    public = json.loads(json.dumps(public_data(report, Path(base_dir) if base_dir else Path.cwd())))
    if public.get("python", {}).get("executable"):
        public["python"]["executable"] = REDACTED_LOCAL_PATH
    if public.get("r", {}).get("rscript"):
        public["r"]["rscript"] = REDACTED_LOCAL_PATH
    for item in public.get("executables", []):
        if item.get("path"):
            item["path"] = REDACTED_LOCAL_PATH
    return public


def write_environment_outputs(spec: dict[str, Any], out_dir: str | Path, non_interactive: bool | None = None) -> dict[str, Any]:
    out = ensure_dir(Path(out_dir))
    qc = ensure_dir(out / "qc")
    references = ensure_dir(out / "references")
    report = inspect_environment(spec, non_interactive)
    plan = build_install_plan(report, spec)
    public_plan = public_data(plan, out)
    missing = public_plan["missing"]
    write_json(qc / "environment_report.json", public_environment_report(report, out))
    write_json(qc / "missing_dependencies.json", missing)
    write_json(qc / "install_plan.json", public_plan)
    write_text(references / "install_plan.md", render_install_plan_markdown(public_plan))
    return report
