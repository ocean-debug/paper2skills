from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml

from paper2skill.env_rebuilder.env_paths import is_path_env


EXECUTABLE_COMMAND_KINDS = {
    "uv_venv_create",
    "conda_env_create",
    "derived_conda_environment",
    "derived_conda_environment_update",
    "conda_packages",
    "conda_python_packages",
    "case_dependency_conda_packages",
    "r_bioc_conda_packages",
    "r_runtime_conda_packages",
    "setup_cfg_conda_python_packages",
    "special_torch_conda_packages",
    "workflow_engine_conda_packages",
    "official_conda_environment",
    "uv_requirements",
    "uv_pypi_project",
    "uv_python_packages",
    "readme_conda_install",
    "readme_uv_pip_install",
    "lockfile_restore",
    "restore_conda_lock",
    "uv_lock_segment_restore",
    "r_github_packages",
    "environment_probe",
    "environment_inventory_probe",
}


def apply_install_plan(plan: dict[str, Any], *, yes: bool) -> dict[str, Any]:
    if not yes:
        raise ValueError("--yes is required with apply")
    diagnostic_only = is_diagnostic_probe_plan(plan)
    if plan.get("status") != "ready" and not diagnostic_only:
        raise ValueError("install plan is not executable")
    results = []
    env_create_blocked = False
    for command in plan.get("commands") or []:
        materialize_command_inputs(command, plan)
        if not is_executable_command(command):
            results.append(skipped_result(command, "command kind requires manual approval or is not executable"))
            continue
        if env_create_blocked and environment_create_dependent(command):
            results.append(blocked_result(command, "target=new environment creation was skipped because the target exists; refusing to install dependencies into an uncreated existing environment. Use target=existing with a package inventory probe, or explicitly replace/overwrite the environment."))
            continue
        if should_skip_existing_environment(command, plan):
            reason = "target environment already exists"
            results.append(skipped_result(command, reason))
            if plan.get("target") == "new" and command.get("creates_env") and command.get("blocks_dependents_on_skip"):
                env_create_blocked = True
            continue
        result = run_command_with_fallback(command)
        if command.get("kind") in PROBE_COMMAND_KINDS and result.get("exit_code") != 0:
            if plan.get("mode") == "lockfile_restore" or command.get("frozen"):
                result["repair_suggestion"] = "Probe failed after frozen lockfile restore; keep the restored lock environment unchanged and build a derived canonical environment in a separate retry."
            else:
                result["repair_suggestion"] = "Probe failed after environment install; inspect activation evidence and apply an additive repair in a separate retry."
        results.append(result)
        if result.get("exit_code") != 0:
            break
    executed = dict(plan)
    executed["dry_run"] = False
    executed["auto_install_performed"] = bool(results)
    executed["execution_results"] = results
    executed["env_create_blocked"] = env_create_blocked
    if diagnostic_only:
        executed["status"] = "diagnostic_executed" if all(item.get("exit_code") == 0 or item.get("skipped") for item in results) else "blocked_diagnostic"
    elif env_create_blocked:
        executed["status"] = "blocked"
        executed["reason"] = "target=new skipped environment creation"
    elif any(item.get("blocked") for item in results):
        executed["status"] = "blocked"
    else:
        executed["status"] = "executed" if all(item.get("exit_code") == 0 or item.get("skipped") for item in results) else "failed"
    return executed


def is_diagnostic_probe_plan(plan: dict[str, Any]) -> bool:
    if plan.get("status") != "blocked_diagnostic":
        return False
    commands = plan.get("commands") or []
    if not commands:
        return False
    return all(command.get("kind") in PROBE_COMMAND_KINDS for command in commands)


def is_executable_command(command: dict[str, Any]) -> bool:
    if command.get("kind") not in EXECUTABLE_COMMAND_KINDS:
        return False
    if command.get("approved_for_execution") is False:
        return False
    return isinstance(command.get("command"), list) and bool(command.get("command"))


def materialize_command_inputs(command: dict[str, Any], plan: dict[str, Any]) -> None:
    if command.get("kind") not in {"derived_conda_environment", "derived_conda_environment_update"}:
        return
    source = command_source_path(command, plan)
    if source.exists():
        return
    canonical = (plan.get("canonical_environment") or {}).get("environment")
    if not isinstance(canonical, dict):
        return
    canonical = executable_conda_environment(canonical)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(yaml.safe_dump(canonical, sort_keys=False), encoding="utf-8", newline="\n")


def executable_conda_environment(environment: dict[str, Any]) -> dict[str, Any]:
    allowed = {"name", "channels", "dependencies", "variables", "prefix"}
    return {key: value for key, value in environment.items() if key in allowed}


def run_command_with_fallback(command: dict[str, Any]) -> dict[str, Any]:
    primary = run_command(command.get("command") or [], cwd=command.get("cwd"), extra_env=command.get("environment"))
    primary = finalize_command_result(command, primary)
    if primary.get("exit_code") == 0:
        return primary
    fallback = command.get("fallback_command")
    if isinstance(fallback, list) and fallback:
        secondary = run_command(fallback, cwd=command.get("cwd"), extra_env=command.get("environment"))
        secondary = finalize_command_result(command, secondary)
        secondary["primary_failed"] = primary
        secondary["used_fallback"] = True
        return secondary
    return primary


def finalize_command_result(command: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    result.update(command_metadata(command))
    if command.get("kind") in PROBE_COMMAND_KINDS:
        attach_probe_payload(result, probe_kind=str(command.get("kind") or "probe"))
    return result


PROBE_COMMAND_KINDS = {"environment_probe", "environment_inventory_probe"}


def attach_probe_payload(result: dict[str, Any], *, probe_kind: str) -> None:
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        result["probe_parse_error"] = f"{probe_kind} produced no stdout"
        if result.get("exit_code") != 0:
            result.setdefault("error_type", "probe_failure")
        return
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        result["probe_parse_error"] = f"{probe_kind} stdout was not JSON: {exc}"
        if result.get("exit_code") != 0:
            result.setdefault("error_type", "probe_failure")
        return
    if not isinstance(payload, dict):
        result["probe_parse_error"] = f"{probe_kind} JSON payload was not an object"
        if result.get("exit_code") != 0:
            result.setdefault("error_type", "probe_failure")
        return
    result["probe"] = payload
    if payload.get("error_type"):
        result.setdefault("error_type", payload["error_type"])
    if payload.get("probe_failure"):
        result.setdefault("probe_failure", payload["probe_failure"])


def run_command(command: list[Any], *, cwd: Any = None, extra_env: Any = None) -> dict[str, Any]:
    normalized = [str(item) for item in command]
    cwd_text = str(cwd) if cwd else None
    env = os.environ.copy()
    command_env = normalize_extra_env(extra_env)
    env.update(command_env)
    try:
        completed = subprocess.run(normalized, text=True, capture_output=True, check=False, cwd=cwd_text, env=env)
    except FileNotFoundError as exc:
        return {
            "command": normalized,
            "cwd": cwd_text,
            "environment": command_env,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"executable not found: {exc.filename or normalized[0]}",
            "skipped": False,
            "error_type": "executable_not_found",
        }
    return {
        "command": normalized,
        "cwd": cwd_text,
        "environment": command_env,
        "exit_code": completed.returncode,
        "stdout": truncate(completed.stdout),
        "stderr": truncate(completed.stderr),
        "skipped": False,
    }


def normalize_extra_env(extra_env: Any) -> dict[str, str]:
    if not isinstance(extra_env, dict):
        return {}
    return {str(key): str(value) for key, value in extra_env.items() if key and value is not None}


def should_skip_existing_environment(command: dict[str, Any], plan: dict[str, Any]) -> bool:
    if not command.get("skip_if_env_exists"):
        return False
    kind = str(command.get("kind") or "")
    if kind == "uv_venv_create":
        env_path = Path(str(plan.get("resolved_env_path") or plan.get("env") or ""))
        return bool(env_path and env_path.exists())
    if kind in {"conda_env_create", "derived_conda_environment"}:
        env = str(plan.get("env") or "")
        if is_path_env(env):
            return Path(env).exists()
        return conda_named_env_exists(env)
    return False


def environment_create_dependent(command: dict[str, Any]) -> bool:
    if command.get("kind") in PROBE_COMMAND_KINDS:
        return False
    if command.get("creates_env"):
        return False
    return bool(command.get("depends_on_env_create") or command.get("installer") in {"uv", "mamba_or_conda", "conda-lock", "remotes"})


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


def blocked_result(command: dict[str, Any], reason: str) -> dict[str, Any]:
    result = command_metadata(command)
    result.update({"exit_code": 1, "stdout": "", "stderr": "", "skipped": False, "blocked": True, "reason": reason})
    return result


def command_metadata(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": command.get("kind"),
        "tier": command.get("tier"),
        "installer": command.get("installer"),
        "packages": command.get("packages"),
    }


def command_source_path(command: dict[str, Any], plan: dict[str, Any]) -> Path:
    source = Path(str(command.get("source") or ""))
    if source.is_absolute():
        return source
    workdir = plan.get("workdir")
    if workdir:
        return Path(str(workdir)) / source
    return source


def truncate(value: Any, limit: int = 4000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
