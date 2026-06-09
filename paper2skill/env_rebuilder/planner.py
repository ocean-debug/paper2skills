from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from paper2skill.env_rebuilder.env_paths import conda_env_args
from paper2skill.env_rebuilder.scanner import LOCKFILE_NAMES, select_python_version


SHARED_ENV_NAMES = {"base", "skill"}
VALID_TORCH_BACKENDS = {"auto", "cpu", "cu118", "cu121", "cu124", "cu126", "cu128"}
BIOCONDA_R_PREFIX = {
    "deseq2": "bioconductor-deseq2",
    "apeglm": "bioconductor-apeglm",
    "biobase": "bioconductor-biobase",
    "biocgenerics": "bioconductor-biocgenerics",
    "singlecellexperiment": "bioconductor-singlecellexperiment",
    "summarizedexperiment": "bioconductor-summarizedexperiment",
    "sparsematrixstats": "bioconductor-sparsematrixstats",
}
CLI_CONDA_PACKAGES = {
    "rscript": "r-base",
    "git": "git",
    "snakemake": "snakemake",
    "nextflow": "nextflow",
    "samtools": "samtools",
    "bedtools": "bedtools",
    "salmon": "salmon",
    "star": "star",
}
CONDA_BINARY_PYTHON = {
    "anndata",
    "h5py",
    "numpy",
    "pandas",
    "scanpy",
    "scikit-misc",
    "scipy",
    "sklearn",
    "scikit-learn",
}
R_BASE_PACKAGES = {
    "base",
    "datasets",
    "graphics",
    "grdevices",
    "grid",
    "methods",
    "parallel",
    "splines",
    "stats",
    "stats4",
    "tools",
    "utils",
}


def plan_environment(
    scan: dict[str, Any],
    *,
    target: str,
    env: str,
    allow_shared_env: bool = False,
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    manager_preference: str = "auto",
    env_path: str | None = None,
) -> dict[str, Any]:
    validate_target(target)
    validate_install_env(env, allow_shared_env=allow_shared_env)
    torch_backend = validate_torch_backend(torch_backend)
    warnings: list[str] = []
    errors: list[str] = []
    env_path = env_path or env
    commands: list[dict[str, Any]] = []
    layers = choose_layers(scan, target=target, manager_preference=manager_preference)
    python_version = selected_python(scan)
    if target == "new":
        commands.extend(create_environment_commands(layers, env=env, env_path=env_path, python_version=python_version, scan=scan, torch_backend=torch_backend))
    else:
        warnings.append("existing environment mode: plan contains incremental installs only; no environment recreation")
    commands.extend(spec_install_commands(scan, layers, env=env, env_path=env_path, allow_github_install=allow_github_install, torch_backend=torch_backend))
    if gpu_policy == "required" and not (scan.get("gpu") or {}).get("uses_torch") and not (scan.get("gpu") or {}).get("cuda_signal"):
        warnings.append("gpu_policy is required but no GPU dependency signal was found")
    warnings.extend(manual_command_warnings(commands))
    manual_approval_required = has_manual_commands(commands)
    status = "invalid" if errors else ("blocked_manual" if manual_approval_required else "ready")
    return {
        "schema_version": 1,
        "status": status,
        "env": env,
        "resolved_env_path": env_path,
        "target": target,
        "manager": layers["manager"],
        "python_version": python_version,
        "gpu_policy": gpu_policy,
        "torch_backend": torch_backend,
        "dry_run": True,
        "auto_install_performed": False,
        "source_priority": [
            "lockfile",
            "official_environment_spec",
            "uv_python_resolver",
            "mamba_conda_forge_bioconda",
            "pip_fallback",
            "github_install_plan_only",
            "manual_block",
        ],
        "layers": layers,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "manual_approval_required": manual_approval_required,
        "safety": {
            "requires_execute_flag": True,
            "requires_yes_flag": True,
            "shared_env_allowed": allow_shared_env,
            "github_install_default": allow_github_install,
            "unknown_install_scripts_executed": False,
            "notebook_execution_performed": False,
        },
        "lock_outputs": planned_lock_outputs(layers),
    }


def plan_from_install_request(
    install_request: dict[str, Any],
    *,
    target: str,
    env: str,
    allow_shared_env: bool = False,
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    python_version: str = "3.10",
    env_path: str | None = None,
) -> dict[str, Any]:
    validate_target(target)
    validate_install_env(env, allow_shared_env=allow_shared_env)
    torch_backend = validate_torch_backend(torch_backend)
    env_path = env_path or env
    conda_packages = unique_strings(install_request.get("conda_packages") or [])
    python_packages = unique_strings(install_request.get("missing_python_packages") or install_request.get("python_packages") or [])
    r_packages = unique_strings(install_request.get("missing_r_packages") or install_request.get("r_packages") or [])
    r_github = unique_strings(install_request.get("r_github_packages") or [])
    executables = unique_strings(install_request.get("missing_executables") or [])
    if target == "existing":
        conda_packages = subtract_installed(conda_packages, install_request.get("installed_conda_packages") or [])
        python_packages = subtract_installed(python_packages, install_request.get("installed_python_packages") or [])
        r_packages = subtract_installed(r_packages, install_request.get("installed_r_packages") or [])
        executables = subtract_installed(executables, install_request.get("available_executables") or [])
    r_resolved = resolve_r_packages(r_packages)
    conda_packages.extend(r_resolved["conda_packages"])
    conda_packages.extend(conda_packages_for_executables(executables))
    binary_python, uv_python = split_python_packages(python_packages)
    conda_packages.extend(binary_python)
    conda_packages = sorted(dict.fromkeys(conda_packages))
    needs_conda = bool(conda_packages or r_packages or r_github or executables)
    commands: list[dict[str, Any]] = []
    if target == "new":
        if needs_conda:
            commands.append(conda_create_command(env, python_version, include_r=bool(r_packages or r_github), channels=channels_from_request(install_request)))
        else:
            commands.append(uv_create_command(env_path, python_version))
    if conda_packages:
        commands.append(
            {
                "kind": "conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": conda_packages,
                "channels": channels_from_request(install_request),
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(channels_from_request(install_request)), *conda_packages],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(channels_from_request(install_request)), *conda_packages],
            }
        )
    if uv_python:
        commands.append(uv_pip_command(env_path if not needs_conda else env, uv_python, torch_backend=torch_backend, inside_conda=needs_conda))
    if r_github:
        commands.append(github_r_command(env, r_github, allow_github_install=allow_github_install))
    commands.extend(manual_r_package_command(package, source="install_request") for package in r_resolved["manual_packages"])
    commands = dedupe_commands(commands)
    manual_approval_required = has_manual_commands(commands)
    status = "blocked_manual" if manual_approval_required else "ready"
    return {
        "schema_version": 1,
        "status": status,
        "env": env,
        "resolved_env_path": env_path,
        "target": target,
        "manager": "conda+uv" if needs_conda and uv_python else ("conda" if needs_conda else "uv"),
        "python_version": python_version,
        "gpu_policy": gpu_policy,
        "torch_backend": torch_backend,
        "dry_run": True,
        "auto_install_performed": False,
        "commands": commands,
        "errors": [],
        "warnings": build_plan_warnings(r_github, allow_github_install, r_resolved),
        "manual_approval_required": manual_approval_required,
        "existing_environment_diff": existing_environment_diff(install_request) if target == "existing" else None,
        "safety": {
            "requires_execute_flag": True,
            "requires_yes_flag": True,
            "shared_env_allowed": allow_shared_env,
            "github_install_default": allow_github_install,
            "unknown_install_scripts_executed": False,
            "notebook_execution_performed": False,
        },
        "lock_outputs": planned_lock_outputs({"manager": "conda+uv" if needs_conda and uv_python else ("conda" if needs_conda else "uv")}),
    }


def choose_layers(scan: dict[str, Any], *, target: str, manager_preference: str) -> dict[str, Any]:
    signals = scan.get("signals") or {}
    gpu = scan.get("gpu") or {}
    has_r = bool(signals.get("has_r_or_bioc"))
    has_conda = bool(signals.get("has_conda_spec"))
    has_workflow = bool(scan.get("workflow_engines"))
    needs_conda = has_r or has_conda or has_workflow
    if manager_preference in {"uv", "conda"}:
        manager = manager_preference
    elif needs_conda:
        manager = "conda"
    else:
        manager = "uv"
    if gpu.get("uses_torch") and manager == "uv":
        pytorch_strategy = "uv_cuda_wheel"
    elif gpu.get("uses_torch"):
        pytorch_strategy = "conda_or_uv_inside_conda"
    else:
        pytorch_strategy = "not_applicable"
    return {
        "manager": manager,
        "needs_conda": needs_conda,
        "uses_uv": manager == "uv" or not needs_conda,
        "uses_conda": manager == "conda" or needs_conda,
        "pytorch_strategy": pytorch_strategy,
        "target_mode": target,
    }


def create_environment_commands(layers: dict[str, Any], *, env: str, env_path: str, python_version: str, scan: dict[str, Any], torch_backend: str) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if layers.get("manager") == "uv":
        commands.append(uv_create_command(env_path, python_version))
    else:
        include_r = bool((scan.get("r") or {}).get("has_r"))
        commands.append(conda_create_command(env, python_version, include_r=include_r, channels=["conda-forge", "bioconda"]))
    return commands


def spec_install_commands(scan: dict[str, Any], layers: dict[str, Any], *, env: str, env_path: str, allow_github_install: str, torch_backend: str) -> list[dict[str, Any]]:
    files = scan.get("environment_files") or []
    commands: list[dict[str, Any]] = []
    lockfiles = [item for item in files if item.get("name") in LOCKFILE_NAMES]
    for item in lockfiles:
        commands.append(lockfile_command(env, item))
    env_files = [item for item in files if item.get("name") in {"environment.yml", "environment.yaml"}]
    for item in env_files:
        commands.append(conda_env_update_command(env, item))
    requirements = [item for item in files if str(item.get("name") or "").startswith("requirements")]
    for item in requirements:
        commands.append(uv_requirements_command(env if layers.get("uses_conda") else env_path, item, torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    python = scan.get("python") or {}
    setup_requires = unique_strings(python.get("setup_cfg_install_requires") or [])
    if setup_requires and not requirements:
        binary_python, uv_python = split_python_packages(setup_requires)
        if binary_python and layers.get("uses_conda"):
            commands.append(
                {
                    "kind": "setup_cfg_conda_python_packages",
                    "tier": 3,
                    "installer": "mamba_or_conda",
                    "packages": binary_python,
                    "channels": ["conda-forge"],
                    "command": ["mamba", "install", "-y", *conda_env_args(env), "-c", "conda-forge", *binary_python],
                    "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "-c", "conda-forge", *binary_python],
                }
            )
        elif binary_python:
            uv_python = sorted(dict.fromkeys([*uv_python, *binary_python]))
        if uv_python:
            commands.append(uv_pip_command(env if layers.get("uses_conda") else env_path, uv_python, torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    if python.get("project_name") and not requirements:
        commands.append(uv_pypi_project_command(env if layers.get("uses_conda") else env_path, str(python["project_name"]), torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    r = scan.get("r") or {}
    r_packages = unique_strings(
        [
            *(r.get("description_packages") or []),
            *(r.get("namespace_packages") or []),
            *(r.get("install_r_packages") or []),
        ]
    )
    r_resolved = resolve_r_packages(r_packages)
    conda_r = r_resolved["conda_packages"]
    if conda_r:
        commands.append(
            {
                "kind": "r_bioc_conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": conda_r,
                "channels": ["conda-forge", "bioconda"],
                "command": ["mamba", "install", "-y", *conda_env_args(env), "-c", "conda-forge", "-c", "bioconda", *conda_r],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "-c", "conda-forge", "-c", "bioconda", *conda_r],
            }
        )
    commands.extend(readme_install_commands(scan.get("install_commands") or [], env=env if layers.get("uses_conda") else env_path, allow_github_install=allow_github_install, torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    r_github = unique_strings(r.get("install_r_github") or [])
    if r_github:
        commands.append(github_r_command(env, r_github, allow_github_install=allow_github_install))
    workflow_packages = workflow_engine_packages(scan.get("workflow_engines") or [])
    if workflow_packages and layers.get("uses_conda"):
        commands.append(
            {
                "kind": "workflow_engine_conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": workflow_packages,
                "channels": ["conda-forge", "bioconda"],
                "command": ["mamba", "install", "-y", *conda_env_args(env), "-c", "conda-forge", "-c", "bioconda", *workflow_packages],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), "-c", "conda-forge", "-c", "bioconda", *workflow_packages],
            }
        )
    for package in r_resolved["manual_packages"]:
        commands.append(manual_r_package_command(package, source="r_package_resolution"))
    return dedupe_commands(commands)


def uv_create_command(env: str, python_version: str) -> dict[str, Any]:
    return {
        "kind": "uv_venv_create",
        "tier": 3,
        "installer": "uv",
        "packages": [],
        "skip_if_env_exists": True,
        "command": ["uv", "venv", "--python", python_version, env],
    }


def conda_create_command(env: str, python_version: str, *, include_r: bool, channels: list[str]) -> dict[str, Any]:
    packages = [f"python={python_version}", "pip", "uv"]
    if include_r:
        packages.append("r-base")
    return {
        "kind": "conda_env_create",
        "tier": 3,
        "installer": "mamba_or_conda",
        "packages": packages,
        "channels": channels,
        "skip_if_env_exists": True,
        "command": ["mamba", "create", "-y", *conda_env_args(env), *channel_args(channels), *packages],
        "fallback_command": ["conda", "create", "-y", *conda_env_args(env), *channel_args(channels), *packages],
    }


def lockfile_command(env: str, item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get("name") or "")
    path = str(item.get("path") or name)
    if name.startswith("conda-lock"):
        command = ["conda-lock", "install", *conda_env_args(env), path]
        installer = "conda-lock"
    elif name == "uv.lock":
        command = ["uv", "sync", "--frozen"]
        installer = "uv"
    elif name == "renv.lock":
        command = ["Rscript", "-e", "renv::restore(prompt=FALSE)"]
        installer = "renv"
    else:
        command = ["uv", "pip", "install", "-r", path]
        installer = "uv"
    return {"kind": "lockfile_restore", "tier": 1, "installer": installer, "source": path, "command": command}


def conda_env_update_command(env: str, item: dict[str, Any]) -> dict[str, Any]:
    path = str(item.get("path") or item.get("name"))
    return {
        "kind": "official_conda_environment",
        "tier": 2,
        "installer": "mamba_or_conda",
        "source": path,
        "command": ["mamba", "env", "update", *conda_env_args(env), "-f", path],
        "fallback_command": ["conda", "env", "update", *conda_env_args(env), "-f", path],
    }


def uv_requirements_command(env: str, item: dict[str, Any], *, torch_backend: str, inside_conda: bool = False) -> dict[str, Any]:
    path = str(item.get("path") or item.get("name"))
    command = uv_in_env(env, ["pip", "install", "-r", path], inside_conda=inside_conda)
    if torch_backend != "auto":
        command = ["env", f"UV_TORCH_BACKEND={torch_backend}", *command]
    return {"kind": "uv_requirements", "tier": 3, "installer": "uv", "source": path, "command": command}


def uv_pypi_project_command(env: str, package: str, *, torch_backend: str, inside_conda: bool = False) -> dict[str, Any]:
    return {
        "kind": "uv_pypi_project",
        "tier": 3,
        "installer": "uv",
        "packages": [package],
        "command": uv_torch_command(env, ["pip", "install", package], torch_backend=torch_backend, inside_conda=inside_conda),
        "fallbacks": [
            {"kind": "git_url", "command": uv_in_env(env, ["pip", "install", f"git+<official-repo-url>"], inside_conda=inside_conda)},
            {"kind": "local_install", "command": uv_in_env(env, ["pip", "install", "."], inside_conda=inside_conda)},
        ],
    }


def uv_pip_command(env: str, packages: list[str], *, torch_backend: str, inside_conda: bool = False) -> dict[str, Any]:
    return {
        "kind": "uv_python_packages",
        "tier": 3,
        "installer": "uv",
        "packages": packages,
        "command": uv_torch_command(env, ["pip", "install", *packages], torch_backend=torch_backend, inside_conda=inside_conda),
    }


def github_r_command(env: str, packages: list[str], *, allow_github_install: str) -> dict[str, Any]:
    expression = "if (!requireNamespace('remotes', quietly=TRUE)) install.packages('remotes', repos='https://cloud.r-project.org'); remotes::install_github(c(%s), upgrade='never')" % ", ".join(repr(item) for item in packages)
    return {
        "kind": "r_github_packages",
        "tier": 6,
        "installer": "remotes",
        "packages": packages,
        "approved_for_execution": allow_github_install == "approved",
        "manual_approval_required": allow_github_install != "approved",
        "reason": "GitHub R package installation requires explicit approval.",
        "command": ["conda", "run", *conda_env_args(env), "Rscript", "-e", expression],
    }


def readme_install_commands(commands: list[dict[str, Any]], *, env: str, allow_github_install: str, torch_backend: str, inside_conda: bool = False) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for item in commands:
        command = str(item.get("command") or "")
        packages = parse_install_packages(command)
        if not packages:
            continue
        if item.get("kind") == "conda":
            planned.append(
                {
                    "kind": "readme_conda_install",
                    "tier": 2,
                    "installer": "mamba_or_conda",
                    "packages": packages,
                    "source": item.get("source"),
                    "command": ["mamba", "install", "-y", *conda_env_args(env), *packages],
                    "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *packages],
                }
            )
        else:
            planned.append(
                {
                    "kind": "readme_uv_pip_install",
                    "tier": 3,
                    "installer": "uv",
                    "packages": packages,
                    "source": item.get("source"),
                    "command": uv_torch_command(env, ["pip", "install", *packages], torch_backend=torch_backend, inside_conda=inside_conda),
                    "fallbacks": [
                        {"kind": "git_url", "approved_for_execution": allow_github_install == "approved", "command": uv_in_env(env, ["pip", "install", "git+<official-repo-url>"], inside_conda=inside_conda)},
                        {"kind": "local_install", "command": uv_in_env(env, ["pip", "install", "."], inside_conda=inside_conda)},
                    ],
                }
            )
    return planned


def parse_install_packages(command: str) -> list[str]:
    tokens = command.strip().split()
    if "install" not in tokens:
        return []
    start = tokens.index("install") + 1
    packages = []
    skip_next = False
    for token in tokens[start:]:
        if skip_next:
            skip_next = False
            continue
        if token in {"-c", "--channel", "-r", "--requirement", "--index-url", "--extra-index-url"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        packages.append(token.strip("'\""))
    return packages


def selected_python(scan: dict[str, Any]) -> str:
    python = scan.get("python") or {}
    return str(python.get("selected_python") or select_python_version(python.get("python_constraint")))


def split_python_packages(packages: list[str]) -> tuple[list[str], list[str]]:
    conda: list[str] = []
    uv: list[str] = []
    for item in packages:
        normalized = re.split(r"[<>=!~]", item, maxsplit=1)[0].strip().lower()
        if normalized in CONDA_BINARY_PYTHON:
            conda.append(item)
        else:
            uv.append(item)
    return sorted(dict.fromkeys(conda)), sorted(dict.fromkeys(uv))


def resolve_r_packages(packages: list[str]) -> dict[str, list[str]]:
    conda: list[str] = []
    manual: list[str] = []
    for item in packages:
        name = re.split(r"[<>=!~ ]", str(item), maxsplit=1)[0].strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered in R_BASE_PACKAGES:
            continue
        if lowered in BIOCONDA_R_PREFIX:
            conda.append(BIOCONDA_R_PREFIX[lowered])
        elif name.startswith("r-") or name.startswith("bioconductor-"):
            conda.append(name)
        elif is_known_cran_conda_package(name):
            conda.append(f"r-{lowered}")
        else:
            manual.append(name)
    return {"conda_packages": sorted(dict.fromkeys(conda)), "manual_packages": sorted(dict.fromkeys(manual))}


def conda_packages_for_r(packages: list[str]) -> list[str]:
    return resolve_r_packages(packages)["conda_packages"]


def is_known_cran_conda_package(name: str) -> bool:
    return name.lower() in {
        "dplyr",
        "ggplot2",
        "glmnet",
        "lmtest",
        "magrittr",
        "matrix",
        "parsnip",
        "pbmcapply",
        "purrr",
        "randomforest",
        "recipes",
        "remotes",
        "rlang",
        "rsample",
        "tester",
        "tibble",
        "tidyr",
        "tidyselect",
        "yardstick",
    }


def manual_r_package_command(package: str, *, source: str) -> dict[str, Any]:
    return {
        "kind": "manual_r_package",
        "tier": 7,
        "installer": "manual",
        "packages": [package],
        "source": source,
        "approved_for_execution": False,
        "manual_approval_required": True,
        "reason": "R package source could not be confidently mapped to conda-forge/bioconda.",
    }


def conda_packages_for_executables(executables: list[str]) -> list[str]:
    packages: list[str] = []
    for item in executables:
        key = Path(str(item)).name.lower()
        packages.append(CLI_CONDA_PACKAGES.get(key, key))
    return sorted(dict.fromkeys(packages))


def workflow_engine_packages(engines: list[dict[str, Any]]) -> list[str]:
    packages: list[str] = []
    for item in engines:
        engine = str(item.get("engine") or "").lower()
        if engine in CLI_CONDA_PACKAGES:
            packages.append(CLI_CONDA_PACKAGES[engine])
        elif engine in {"cwl", "wdl"}:
            packages.append(engine)
    return sorted(dict.fromkeys(packages))


def channels_from_request(request: dict[str, Any]) -> list[str]:
    channels = unique_strings(request.get("conda_channels") or request.get("channels") or [])
    return channels or ["conda-forge", "bioconda"]


def uv_in_env(env: str, args: list[str], *, inside_conda: bool = False) -> list[str]:
    if inside_conda:
        return ["conda", "run", *conda_env_args(env), "uv", *args]
    if len(args) >= 2 and args[:2] == ["pip", "install"]:
        return ["uv", "pip", "install", "--python", env, *args[2:]]
    return ["uv", *args]


def uv_torch_command(env: str, args: list[str], *, torch_backend: str, inside_conda: bool = False) -> list[str]:
    command = uv_in_env(env, args, inside_conda=inside_conda)
    if args and any(str(token).split("==")[0].lower() in {"torch", "torchvision", "torchaudio"} for token in args):
        command.append(f"--torch-backend={torch_backend}")
    elif torch_backend != "auto":
        command = ["env", f"UV_TORCH_BACKEND={torch_backend}", *command]
    return command


def channel_args(channels: list[str]) -> list[str]:
    args: list[str] = []
    for channel in channels:
        args.extend(["-c", channel])
    return args


def planned_lock_outputs(layers: dict[str, Any]) -> list[str]:
    manager = str(layers.get("manager") or "")
    outputs = ["env_rebuild_report.json", "install_plan.json", "repair_attempts.json"]
    if "uv" in manager:
        outputs.extend(["lock/uv.lock", "lock/uv-pip-freeze.txt", "lock/wheelhouse/"])
    if "conda" in manager:
        outputs.extend(["lock/environment.yml", "lock/conda-explicit.txt", "lock/conda-lock.yml"])
    outputs.extend(["lock/R-sessionInfo.txt", "lock/renv.lock"])
    return outputs


def build_plan_warnings(r_github: list[str], allow_github_install: str, r_resolved: dict[str, list[str]]) -> list[str]:
    warnings: list[str] = []
    if r_github and allow_github_install == "ask":
        warnings.append("GitHub install is plan-only until explicitly approved")
    for package in r_resolved.get("manual_packages") or []:
        warnings.append(f"R package requires manual resolution: {package}")
    return warnings


def has_manual_commands(commands: list[dict[str, Any]]) -> bool:
    for command in commands:
        if command.get("approved_for_execution") is False:
            return True
        if command.get("manual_approval_required") is True:
            return True
        if str(command.get("kind") or "").startswith("manual_"):
            return True
    return False


def manual_command_warnings(commands: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for command in commands:
        if command.get("approved_for_execution") is False or command.get("manual_approval_required") is True:
            packages = ", ".join(str(item) for item in command.get("packages") or [])
            kind = str(command.get("kind") or "manual_step")
            detail = f": {packages}" if packages else ""
            warnings.append(f"{kind} requires manual approval{detail}")
    return warnings


def validate_install_env(value: str, *, allow_shared_env: bool) -> str:
    env = str(value or "").strip()
    if not env:
        raise ValueError("--env is required")
    if env in SHARED_ENV_NAMES and not allow_shared_env:
        raise ValueError(f"refusing to install into shared environment {env!r}; pass --allow-shared-env to override")
    if any(token in env for token in ["\n", "\r", "\0"]):
        raise ValueError("--env contains invalid control characters")
    return env


def validate_target(value: str) -> str:
    if value not in {"new", "existing"}:
        raise ValueError("--target must be new or existing")
    return value


def validate_torch_backend(value: str) -> str:
    if value not in VALID_TORCH_BACKENDS:
        raise ValueError(f"unknown torch backend: {value}")
    return value


def unique_strings(values: list[Any]) -> list[str]:
    return sorted(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def package_key(value: Any) -> str:
    return re.split(r"[<>=!~ ]", str(value), maxsplit=1)[0].strip().lower()


def subtract_installed(values: list[str], installed: list[Any]) -> list[str]:
    installed_keys = {package_key(item) for item in installed}
    return [item for item in values if package_key(item) not in installed_keys]


def existing_environment_diff(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "preflight_missing_diff",
        "installed_python_packages": unique_strings(request.get("installed_python_packages") or []),
        "installed_r_packages": unique_strings(request.get("installed_r_packages") or []),
        "installed_conda_packages": unique_strings(request.get("installed_conda_packages") or []),
        "available_executables": unique_strings(request.get("available_executables") or []),
    }


def dedupe_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for command in commands:
        key = repr(command.get("command"))
        if command.get("command") is None:
            key = repr(
                (
                    command.get("kind"),
                    tuple(command.get("packages") or []),
                    command.get("source"),
                    command.get("reason"),
                )
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(command)
    return deduped
