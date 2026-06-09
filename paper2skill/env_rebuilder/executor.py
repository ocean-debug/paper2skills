from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from paper2skill.env_rebuilder.env_paths import is_path_env


EXECUTABLE_COMMAND_KINDS = {
    "uv_venv_create",
    "conda_env_create",
    "conda_packages",
    "r_bioc_conda_packages",
    "official_conda_environment",
    "uv_requirements",
    "uv_pypi_project",
    "uv_python_packages",
    "readme_conda_install",
    "readme_uv_pip_install",
    "lockfile_restore",
    "r_github_packages",
}


def apply_install_plan(plan: dict[str, Any], *, yes: bool) -> dict[str, Any]:
    if not yes:
        raise ValueError("--yes is required with apply")
    if plan.get("status") != "ready":
        raise ValueError("install plan is not executable")
    results = []
    for command in plan.get("commands") or []:
        if not is_executable_command(command):
            results.append(skipped_result(command, "command kind requires manual approval or is not executable"))
            continue
        if should_skip_existing_environment(command, plan):
            results.append(skipped_result(command, "target environment already exists"))
            continue
        result = run_command_with_fallback(command)
        results.append(result)
        if result.get("exit_code") != 0:
            break
    executed = dict(plan)
    executed["dry_run"] = False
    executed["auto_install_performed"] = bool(results)
    executed["execution_results"] = results
    executed["status"] = "executed" if all(item.get("exit_code") == 0 or item.get("skipped") for item in results) else "failed"
    return executed


def is_executable_command(command: dict[str, Any]) -> bool:
    if command.get("kind") not in EXECUTABLE_COMMAND_KINDS:
        return False
    if command.get("approved_for_execution") is False:
        return False
    return isinstance(command.get("command"), list) and bool(command.get("command"))


def run_command_with_fallback(command: dict[str, Any]) -> dict[str, Any]:
    primary = run_command(command.get("command") or [])
    if primary.get("exit_code") == 0:
        primary.update(command_metadata(command))
        return primary
    fallback = command.get("fallback_command")
    if isinstance(fallback, list) and fallback:
        secondary = run_command(fallback)
        secondary.update(command_metadata(command))
        secondary["primary_failed"] = primary
        secondary["used_fallback"] = True
        return secondary
    primary.update(command_metadata(command))
    return primary


def run_command(command: list[Any]) -> dict[str, Any]:
    normalized = [str(item) for item in command]
    try:
        completed = subprocess.run(normalized, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        return {
            "command": normalized,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"executable not found: {exc.filename or normalized[0]}",
            "skipped": False,
            "error_type": "executable_not_found",
        }
    return {
        "command": normalized,
        "exit_code": completed.returncode,
        "stdout": truncate(completed.stdout),
        "stderr": truncate(completed.stderr),
        "skipped": False,
    }


def should_skip_existing_environment(command: dict[str, Any], plan: dict[str, Any]) -> bool:
    if not command.get("skip_if_env_exists"):
        return False
    kind = str(command.get("kind") or "")
    if kind == "uv_venv_create":
        env_path = Path(str(plan.get("resolved_env_path") or plan.get("env") or ""))
        return bool(env_path and env_path.exists())
    if kind == "conda_env_create":
        env = str(plan.get("env") or "")
        if is_path_env(env):
            return Path(env).exists()
        return conda_named_env_exists(env)
    return False


def conda_named_env_exists(env: str) -> bool:
    if not env:
        return False
    try:
        completed = subprocess.run(["conda", "env", "list", "--json"], text=True, capture_output=True, check=False)
    except Exception:
        return False
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False
    return any(Path(str(item)).name == env for item in payload.get("envs") or [])


def skipped_result(command: dict[str, Any], reason: str) -> dict[str, Any]:
    result = command_metadata(command)
    result.update({"exit_code": 0, "stdout": "", "stderr": "", "skipped": True, "reason": reason})
    return result


def command_metadata(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": command.get("kind"),
        "tier": command.get("tier"),
        "installer": command.get("installer"),
        "packages": command.get("packages"),
    }


def truncate(value: Any, limit: int = 4000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
