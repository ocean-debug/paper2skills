from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from paper2skill.env_rebuilder.env_paths import conda_env_args, uv_python_executable


def export_lock_plan(env: str, out: str | Path, *, manager: str = "conda", resolved_env_path: str | None = None, python_executable: str | None = None) -> dict[str, Any]:
    out_path = Path(out)
    commands = lock_commands(env, out_path, manager=manager, resolved_env_path=resolved_env_path, python_executable=python_executable)
    return {
        "status": "ready",
        "env": env,
        "resolved_env_path": resolved_env_path,
        "python_executable": python_executable,
        "manager": manager,
        "out": str(out_path),
        "dry_run": True,
        "auto_export_performed": False,
        "commands": commands,
        "optional_outputs": ["conda-lock.yml", "uv.lock", "renv.lock", "wheelhouse/"],
    }


def export_lock_artifacts(
    env: str,
    out: str | Path,
    *,
    manager: str = "conda",
    resolved_env_path: str | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    plan = export_lock_plan(env, out, manager=manager, resolved_env_path=resolved_env_path, python_executable=python_executable)
    out_path = Path(out)
    out_path.mkdir(parents=True, exist_ok=True)
    results = []
    for command in plan["commands"]:
        result = run_export_command(command)
        results.append(result)
    report = dict(plan)
    report["dry_run"] = False
    report["auto_export_performed"] = True
    report["results"] = results
    report["lock_outputs"] = [item["out"] for item in results if item.get("written")]
    report["status"] = "exported" if results and all(item.get("exit_code") == 0 for item in results) else "partial"
    (out_path / "lock_export_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return report


def lock_commands(
    env: str,
    out_path: Path,
    *,
    manager: str,
    resolved_env_path: str | None,
    python_executable: str | None,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if "conda" in manager:
        commands.extend(
            [
                {"kind": "conda_env_export", "command": ["conda", "env", "export", *conda_env_args(env)], "out": str(out_path / "environment.yml")},
                {"kind": "conda_explicit", "command": ["conda", "list", "--explicit", *conda_env_args(env)], "out": str(out_path / "conda-explicit.txt")},
                {"kind": "r_session_info", "command": ["conda", "run", *conda_env_args(env), "Rscript", "-e", "sessionInfo()"], "out": str(out_path / "R-sessionInfo.txt"), "optional": True},
            ]
        )
        if "uv" in manager:
            commands.append({"kind": "uv_pip_freeze", "command": ["conda", "run", *conda_env_args(env), "uv", "pip", "freeze"], "out": str(out_path / "uv-pip-freeze.txt"), "optional": True})
    elif "uv" in manager:
        python = python_executable or (uv_python_executable(resolved_env_path) if resolved_env_path else "python")
        commands.append({"kind": "uv_pip_freeze", "command": [python, "-m", "pip", "freeze"], "out": str(out_path / "uv-pip-freeze.txt")})
    return commands


def run_export_command(command: dict[str, Any]) -> dict[str, Any]:
    normalized = [str(item) for item in command.get("command") or []]
    out_path = Path(str(command.get("out")))
    try:
        completed = subprocess.run(normalized, text=True, capture_output=True, check=False)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except FileNotFoundError as exc:
        stdout = ""
        stderr = f"executable not found: {exc.filename or normalized[0]}"
        exit_code = 127
    if exit_code == 0:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(stdout, encoding="utf-8", newline="\n")
    return {
        "kind": command.get("kind"),
        "command": normalized,
        "out": str(out_path),
        "exit_code": exit_code,
        "stdout": truncate(stdout),
        "stderr": truncate(stderr),
        "written": exit_code == 0,
        "optional": bool(command.get("optional")),
    }


def truncate(value: Any, limit: int = 4000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
