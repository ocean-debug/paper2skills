from __future__ import annotations

import argparse
import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Any

from paper2skill.common import read_json, write_json


SHARED_ENV_NAMES = {"base", "skill"}
PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.:/@+!=<>,~\[\]-]+$")
CONDA_CHANNEL_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")


def build_install_plan(
    evaluation: dict[str, Any],
    *,
    install_env: str,
    conda_executable: str = "conda",
    allow_shared_env: bool = False,
    override_request_env: bool = False,
    create_conda_env: bool = False,
    python_version: str = "3.11",
    env_exists: bool | None = None,
) -> dict[str, Any]:
    install_env = validate_install_env(install_env, allow_shared_env=allow_shared_env)
    requests = find_install_requests(evaluation)
    errors: list[str] = []
    warnings: list[str] = []
    if not requests:
        errors.append("no install approval requests found in evaluation JSON")
    commands: list[dict[str, Any]] = []
    conda_channels = collect_conda_channels(requests, errors)
    channel_args = conda_channel_args(conda_channels)
    all_missing_r: list[str] = []
    create_conda_packages: list[str] = []
    for request in requests:
        all_missing_r.extend(str(item) for item in request.get("missing_r_packages") or [])
        all_missing_r.extend(str(item) for item in request.get("r_github_packages") or [])
        create_conda_packages.extend(str(item) for item in request.get("conda_packages") or [])
    if create_conda_env:
        create_packages = [f"python={python_version}", "pip"]
        if all_missing_r or any(str(item).lower() == "r-base" for item in create_conda_packages):
            create_packages.append("r-base")
        commands.append(
            {
                "kind": "conda_env_create",
                "installer": "conda",
                "packages": create_packages,
                "channels": conda_channels,
                "skip_if_env_exists": True,
                "command": [conda_executable, "create", "-y", *conda_env_args(install_env), *channel_args, *create_packages],
            }
        )
    for index, request in enumerate(requests):
        requested_env = request.get("target_environment")
        if requested_env and requested_env != install_env and not override_request_env:
            errors.append(f"install request target_environment {requested_env!r} does not match --install-env {install_env!r}")
            continue
        if requested_env and requested_env != install_env and override_request_env:
            warnings.append(f"overriding install request target_environment {requested_env!r} with {install_env!r}")
        allowed = set(str(item) for item in request.get("allowed_installers") or [])
        conda_packages = validate_packages(request.get("conda_packages") or [], errors, f"request[{index}].conda_packages")
        conda_packages = filter_create_env_packages(conda_packages, create_conda_env=create_conda_env)
        missing_python = validate_packages(request.get("missing_python_packages") or [], errors, f"request[{index}].missing_python_packages")
        missing_r = validate_packages(request.get("missing_r_packages") or [], errors, f"request[{index}].missing_r_packages")
        r_github = validate_packages(request.get("r_github_packages") or [], errors, f"request[{index}].r_github_packages")
        missing_exec = validate_packages(request.get("missing_executables") or [], errors, f"request[{index}].missing_executables")
        if conda_packages:
            if "conda" not in allowed:
                errors.append(f"request[{index}] has conda packages but allowed_installers lacks conda")
            else:
                commands.append(
                    {
                        "kind": "conda_packages",
                        "installer": "conda",
                        "packages": conda_packages,
                        "channels": conda_channels,
                        "command": [conda_executable, "install", "-y", *conda_env_args(install_env), *channel_args, *conda_packages],
                    }
                )
        if missing_python:
            if "pip" not in allowed and "conda" not in allowed:
                errors.append(f"request[{index}] has Python packages but allowed_installers lacks pip/conda")
            else:
                commands.append(
                    {
                        "kind": "python_packages",
                        "installer": "pip",
                        "packages": missing_python,
                        "command": [conda_executable, "run", *conda_env_args(install_env), "python", "-m", "pip", "install", *missing_python],
                    }
                )
        if missing_r:
            installer = "BiocManager" if "BiocManager" in allowed else "install.packages" if "install.packages" in allowed else None
            if not installer:
                errors.append(f"request[{index}] has R packages but allowed_installers lacks BiocManager/install.packages")
            else:
                commands.append(
                    {
                        "kind": "r_packages",
                        "installer": installer,
                        "packages": missing_r,
                        "command": [conda_executable, "run", *conda_env_args(install_env), "Rscript", "-e", r_install_expression(missing_r, installer)],
                    }
                )
        if r_github:
            if "remotes" not in allowed and "devtools" not in allowed:
                errors.append(f"request[{index}] has R GitHub packages but allowed_installers lacks remotes/devtools")
            else:
                commands.append(
                    {
                        "kind": "r_github_packages",
                        "installer": "remotes",
                        "packages": r_github,
                        "command": [conda_executable, "run", *conda_env_args(install_env), "Rscript", "-e", r_github_install_expression(r_github)],
                    }
                )
        if missing_exec:
            warnings.append(f"request[{index}] has missing executables requiring manual installation: {', '.join(missing_exec)}")
    return {
        "status": "ready" if not errors else "invalid",
        "install_env": install_env,
        "dry_run": True,
        "auto_install_performed": False,
        "create_conda_env": create_conda_env,
        "env_exists": env_exists,
        "conda_channels": conda_channels,
        "request_count": len(requests),
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "safety": {
            "requires_execute_flag": True,
            "requires_yes_flag": True,
            "shared_env_allowed": allow_shared_env,
            "notebook_execution_performed": False,
            "unknown_install_scripts_executed": False,
        },
    }


def find_install_requests(data: Any) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if isinstance(data.get("install_request"), dict) and data["install_request"].get("status") == "approval_required":
            requests.append(data["install_request"])
        for value in data.values():
            requests.extend(find_install_requests(value))
    elif isinstance(data, list):
        for item in data:
            requests.extend(find_install_requests(item))
    return requests


def validate_install_env(value: str, *, allow_shared_env: bool) -> str:
    env = str(value or "").strip()
    if not env:
        raise ValueError("--install-env is required")
    if env in SHARED_ENV_NAMES and not allow_shared_env:
        raise ValueError(f"refusing to install into shared environment {env!r}; pass --allow-shared-env to override")
    if any(token in env for token in ["\n", "\r", "\0"]):
        raise ValueError("--install-env contains invalid control characters")
    return env


def conda_env_args(env: str) -> list[str]:
    if "/" in env or "\\" in env:
        return ["-p", env]
    return ["-n", env]


def validate_packages(values: list[Any], errors: list[str], field: str) -> list[str]:
    packages: list[str] = []
    for value in values:
        name = str(value).strip()
        if not name:
            continue
        if not PACKAGE_RE.match(name):
            errors.append(f"{field} contains unsafe package name: {name!r}")
            continue
        packages.append(name)
    return sorted(dict.fromkeys(packages))


def collect_conda_channels(requests: list[dict[str, Any]], errors: list[str]) -> list[str]:
    channels: list[str] = []
    for index, request in enumerate(requests):
        for value in request.get("conda_channels") or request.get("channels") or []:
            channel = str(value).strip()
            if not channel:
                continue
            if not CONDA_CHANNEL_RE.match(channel):
                errors.append(f"request[{index}].conda_channels contains unsafe channel name: {channel!r}")
                continue
            channels.append(channel)
    return list(dict.fromkeys(channels))


def conda_channel_args(channels: list[str]) -> list[str]:
    args: list[str] = []
    for channel in channels:
        args.extend(["-c", channel])
    return args


def filter_create_env_packages(packages: list[str], *, create_conda_env: bool) -> list[str]:
    if not create_conda_env:
        return packages
    create_time = {"python", "pip", "r-base"}
    return [item for item in packages if item.lower() not in create_time and not item.lower().startswith("python=")]


def r_install_expression(packages: list[str], installer: str) -> str:
    quoted = ", ".join(json.dumps(item) for item in packages)
    if installer == "BiocManager":
        return (
            "if (!requireNamespace('BiocManager', quietly=TRUE)) "
            "install.packages('BiocManager', repos='https://cloud.r-project.org'); "
            f"BiocManager::install(c({quoted}), ask=FALSE, update=FALSE)"
        )
    return f"install.packages(c({quoted}), repos='https://cloud.r-project.org')"


def r_github_install_expression(packages: list[str]) -> str:
    quoted = ", ".join(json.dumps(item) for item in packages)
    return (
        "if (!requireNamespace('remotes', quietly=TRUE)) "
        "install.packages('remotes', repos='https://cloud.r-project.org'); "
        f"remotes::install_github(c({quoted}), upgrade='never')"
    )


def execute_install_plan(plan: dict[str, Any], *, yes: bool) -> dict[str, Any]:
    if not yes:
        raise ValueError("--yes is required with --execute")
    if plan.get("status") != "ready":
        raise ValueError("install plan is not ready")
    results = []
    for command in plan.get("commands") or []:
        if command.get("kind") == "conda_env_create" and command.get("skip_if_env_exists") and conda_env_exists(plan["install_env"], command["command"][0]):
            results.append(
                {
                    "kind": command.get("kind"),
                    "installer": command.get("installer"),
                    "packages": command.get("packages"),
                    "exit_code": 0,
                    "stdout": "environment already exists; create skipped",
                    "stderr": "",
                    "skipped": True,
                }
            )
            continue
        completed = subprocess.run(command["command"], text=True, capture_output=True, check=False)
        results.append(
            {
                "kind": command.get("kind"),
                "installer": command.get("installer"),
                "packages": command.get("packages"),
                "exit_code": completed.returncode,
                "stdout": truncate(completed.stdout),
                "stderr": truncate(completed.stderr),
                "skipped": False,
            }
        )
        if completed.returncode != 0:
            break
    executed = dict(plan)
    executed["dry_run"] = False
    executed["auto_install_performed"] = bool(results)
    executed["execution_results"] = results
    executed["status"] = "executed" if all(item["exit_code"] == 0 for item in results) else "failed"
    return executed


def conda_env_exists(env: str, conda_executable: str = "conda") -> bool:
    conda = shutil.which(conda_executable) or conda_executable
    try:
        completed = subprocess.run([conda, "env", "list", "--json"], text=True, capture_output=True, check=False)
    except Exception:
        return False
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False
    envs = [str(item) for item in payload.get("envs") or []]
    if "/" in env or "\\" in env:
        return any(Path(item).resolve() == Path(env).resolve() for item in envs)
    return any(Path(item).name == env for item in envs)


def truncate(value: Any, limit: int = 4000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or execute an approved L2 dependency install plan.")
    parser.add_argument("--evaluation", required=True, help="Evaluation JSON containing execution.install_request entries")
    parser.add_argument("--install-env", required=True, help="Explicit target environment name/path")
    parser.add_argument("--out", help="Path to write the install plan JSON")
    parser.add_argument("--conda-executable", default="conda", help="Conda executable to use when executing")
    parser.add_argument("--execute", action="store_true", help="Execute the generated plan")
    parser.add_argument("--yes", action="store_true", help="Required with --execute")
    parser.add_argument("--allow-shared-env", action="store_true", help="Allow installing into base/skill")
    parser.add_argument("--override-request-env", action="store_true", help="Use --install-env even when request target differs")
    parser.add_argument("--create-conda-env", action="store_true", help="Create the target conda environment before installing packages")
    parser.add_argument("--python-version", default="3.11", help="Python version for --create-conda-env")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evaluation_path = Path(args.evaluation)
    out = Path(args.out) if args.out else evaluation_path.with_name("install_approved_plan.json")
    try:
        plan = build_install_plan(
            read_json(evaluation_path),
            install_env=args.install_env,
            conda_executable=args.conda_executable,
            allow_shared_env=args.allow_shared_env,
            override_request_env=args.override_request_env,
            create_conda_env=args.create_conda_env,
            python_version=args.python_version,
        )
        result = execute_install_plan(plan, yes=args.yes) if args.execute else plan
    except Exception as exc:  # noqa: BLE001 - CLI should return structured JSON.
        result = {"status": "invalid", "errors": [str(exc)], "auto_install_performed": False}
        write_json(out, result)
        print(json.dumps({"status": result["status"], "out": str(out), "errors": result["errors"]}, ensure_ascii=False))
        return 2
    write_json(out, result)
    print(json.dumps({"status": result["status"], "out": str(out), "command_count": len(result.get("commands") or [])}, ensure_ascii=False))
    return 0 if result["status"] in {"ready", "executed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
