from __future__ import annotations

import json
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

import yaml

from paper2skill.env_rebuilder.canonical_env import CANONICAL_ENV_RELATIVE_PATH, derive_canonical_environment, trust_lockfiles
from paper2skill.env_rebuilder.env_paths import conda_env_args, uv_python_executable
from paper2skill.env_rebuilder.routes import (
    CLI_CONDA_PACKAGES,
    DEFAULT_BIOCONDA_CHANNELS,
    channel_args,
    direct_url_requirement_type,
    normalize_channels,
    normalize_install_approval,
    package_key as route_package_key,
    route_cli_executables,
    route_python_packages,
    route_r_packages,
)
from paper2skill.env_rebuilder.scanner import scan_repo, select_python_version


SHARED_ENV_NAMES = {"base", "skill"}
VALID_TORCH_BACKENDS = {"auto", "cpu", "cu118", "cu121", "cu124", "cu126", "cu128"}
R_GITHUB_RUNTIME_CONDA_PACKAGES = ["r-base", "r-remotes"]


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
    r_mode: str = "conda",
    allow_renv: bool = False,
    install_approval: dict[str, Any] | None = None,
    allow_install: str | None = None,
) -> dict[str, Any]:
    validate_target(target)
    validate_install_env(env, allow_shared_env=allow_shared_env)
    torch_backend = validate_torch_backend(torch_backend)
    warnings: list[str] = []
    errors: list[str] = []
    env_path = env_path or env
    commands: list[dict[str, Any]] = []
    install_approval = normalize_install_approval(install_approval)
    layers = choose_layers(
        scan,
        target=target,
        manager_preference=manager_preference,
        install_approval=install_approval,
        allow_github_install=allow_github_install,
    )
    python_version = selected_python(scan)
    lock_trust = trust_lockfiles(scan, r_mode=r_mode, allow_renv=allow_renv)
    canonical = derive_canonical_environment(scan, env_name=env, python_version=python_version, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
    if target == "existing":
        return plan_existing_environment(
            scan,
            env=env,
            env_path=env_path,
            layers=layers,
            python_version=python_version,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            r_mode=r_mode,
            lock_trust=lock_trust,
            canonical=canonical,
            allow_shared_env=allow_shared_env,
            allow_github_install=allow_github_install,
            install_approval=install_approval,
            allow_install=allow_install,
        )
    if target == "new" and has_trusted_full_conda_lock(lock_trust):
        warnings.append("trusted conda-lock.yml will be used as the frozen full environment entry; no additional solver or pip steps will be appended")
        commands.extend(frozen_conda_lock_commands(scan, layers=layers, env=env, env_path=env_path, lock_trust=lock_trust, allow_github_install=allow_github_install))
        return environment_plan_result(
            env=env,
            env_path=env_path,
            target=target,
            layers=layers,
            python_version=python_version,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            r_mode=r_mode,
            lock_trust=lock_trust,
            canonical=canonical,
            commands=commands,
            warnings=warnings,
            errors=errors,
            mode="lockfile_restore",
            frozen=True,
            workdir=scan.get("repo"),
            allow_shared_env=allow_shared_env,
            allow_github_install=allow_github_install,
            allow_install=allow_install,
        )
    if target == "new":
        commands.extend(create_environment_commands(layers, env=env, env_path=env_path, python_version=python_version, scan=scan, torch_backend=torch_backend, canonical=canonical))
    commands.extend(spec_install_commands(scan, layers, env=env, env_path=env_path, target=target, allow_github_install=allow_github_install, gpu_policy=gpu_policy, torch_backend=torch_backend, lock_trust=lock_trust, canonical=canonical, install_approval=install_approval))
    append_environment_probe(commands, scan=scan, layers=layers, env=env, env_path=env_path, allow_github_install=allow_github_install)
    if gpu_policy == "required" and not (scan.get("gpu") or {}).get("uses_torch") and not (scan.get("gpu") or {}).get("cuda_signal"):
        warnings.append("gpu_policy is required but no GPU dependency signal was found")
    warnings.extend(manual_command_warnings(commands))
    return environment_plan_result(
        env=env,
        env_path=env_path,
        target=target,
        layers=layers,
        python_version=python_version,
        gpu_policy=gpu_policy,
        torch_backend=torch_backend,
        r_mode=r_mode,
        lock_trust=lock_trust,
        canonical=canonical,
        commands=commands,
        warnings=warnings,
        errors=errors,
        mode="canonical_env",
        frozen=False,
        workdir=scan.get("repo"),
        allow_shared_env=allow_shared_env,
        allow_github_install=allow_github_install,
        allow_install=allow_install,
    )


def build_bio_env_plan(
    *,
    case_dir: str | Path | None = None,
    skill_dir: str | Path | None = None,
    repo_dir: str | Path | None = None,
    source_dir: str | Path | None = None,
    install_request: dict[str, Any] | None = None,
    target: str,
    env: str,
    allow_shared_env: bool = False,
    allow_github_install: str = "ask",
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    manager_preference: str = "auto",
    env_path: str | None = None,
    python_version: str = "3.10",
    install_approval: dict[str, Any] | None = None,
    allow_install: str | None = None,
) -> dict[str, Any]:
    approval = merged_install_approval(install_request, skill_dir=skill_dir, explicit=install_approval)
    scan = build_bio_env_scan(
        case_dir=case_dir,
        skill_dir=skill_dir,
        repo_dir=repo_dir,
        source_dir=source_dir,
        install_request=install_request,
        python_version=python_version,
        install_approval=approval,
    )
    plan = plan_environment(
        scan,
        target=target,
        env=env,
        allow_shared_env=allow_shared_env,
        allow_github_install=allow_github_install,
        gpu_policy=gpu_policy,
        torch_backend=torch_backend,
        manager_preference=manager_preference,
        env_path=env_path,
        install_approval=approval,
        allow_install=allow_install,
    )
    plan["plan_source"] = plan.get("mode") or "canonical_env"
    plan["allow_install"] = allow_install
    plan["scanned_artifacts"] = scan.get("scanned_artifacts") or []
    plan["lockfile_status"] = plan.get("lock_trust")
    plan["canonical_env_path"] = canonical_env_path_for_plan(plan, skill_dir=skill_dir)
    plan["install_approval"] = approval
    plan["repair_allowlist"] = unique_strings((install_request or {}).get("repair_allowlist") or (install_request or {}).get("allowed_repair_packages") or [])
    return plan


def build_bio_env_scan(
    *,
    case_dir: str | Path | None,
    skill_dir: str | Path | None,
    repo_dir: str | Path | None,
    source_dir: str | Path | None,
    install_request: dict[str, Any] | None,
    python_version: str,
    install_approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = bio_env_candidate_roots(case_dir=case_dir, skill_dir=skill_dir, repo_dir=repo_dir, source_dir=source_dir)
    work_root = bio_env_scan_work_root(skill_dir, case_dir)
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    scanned_artifacts: list[dict[str, Any]] = []
    for source in candidates:
        copy_bio_env_artifacts(source, work_root, scanned_artifacts)
    materialize_install_request_evidence(install_request or {}, work_root, scanned_artifacts, python_version=python_version)
    scan = scan_repo(work_root)
    merge_generated_skill_pip_segment(scan, work_root, install_approval=install_approval)
    scan["case_install_request"] = install_request or {}
    scan["scanned_artifacts"] = scanned_artifacts
    scan["evidence_roots"] = [str(path) for path in candidates]
    return scan


def bio_env_candidate_roots(*, case_dir: str | Path | None, skill_dir: str | Path | None, repo_dir: str | Path | None, source_dir: str | Path | None) -> list[Path]:
    roots: list[Path] = []
    values = [
        Path(skill_dir) if skill_dir else None,
        Path(skill_dir) / "sources" / "repo" if skill_dir else None,
        Path(skill_dir) / ".paper2skill_collection" if skill_dir else None,
        Path(repo_dir) if repo_dir else None,
        Path(source_dir) if source_dir else None,
        Path(case_dir) if case_dir else None,
    ]
    if skill_dir:
        values.extend(source_manifest_roots(Path(skill_dir)))
    for value in values:
        if value and value.exists() and value not in roots:
            roots.append(value)
    return roots


def source_manifest_roots(skill_dir: Path) -> list[Path]:
    manifest_path = skill_dir / "references" / "source_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    repo = data.get("repo") if isinstance(data, dict) else {}
    roots: list[Path] = []
    for key in ["resolved_path", "local_path", "repo_dir", "source_dir", "path"]:
        value = repo.get(key) if isinstance(repo, dict) else None
        if not value:
            continue
        path = Path(str(value))
        candidates = [path] if path.is_absolute() else [Path.cwd() / path, skill_dir / path, skill_dir.parent / path]
        for candidate in candidates:
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    return roots


def bio_env_scan_work_root(skill_dir: str | Path | None, case_dir: str | Path | None) -> Path:
    if skill_dir:
        return Path(skill_dir) / ".paper2skill" / "env_scan"
    if case_dir:
        return Path(case_dir) / ".paper2skill" / "env_scan"
    return Path(".paper2skill") / "env_scan"


def copy_bio_env_artifacts(source: Path, dest: Path, scanned_artifacts: list[dict[str, Any]]) -> None:
    source = source.resolve()
    for rel in preferred_bio_env_artifact_paths():
        path = source / rel
        if not path.exists() or not path.is_file():
            continue
        target = dest / normalized_artifact_name(path.name, rel)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        scanned_artifacts.append({"source": str(path), "materialized": str(target), "name": target.name, "priority": len(scanned_artifacts) + 1})


def preferred_bio_env_artifact_paths() -> list[Path]:
    return [
        Path("assets/env/conda-lock.yml"),
        Path("assets/env/conda-lock.yaml"),
        Path("assets/env/paper2skill.environment.yml"),
        Path("assets/env/normalization_report.json"),
        Path("assets/requirements.txt"),
        Path("assets/environment.yml"),
        Path("assets/environment_spec.yaml"),
        Path("conda-lock.yml"),
        Path("conda-lock.yaml"),
        Path("environment.yml"),
        Path("environment.yaml"),
        Path("requirements.txt"),
        Path("pyproject.toml"),
        Path("DESCRIPTION"),
        Path("NAMESPACE"),
        Path("renv.lock"),
        Path("install.R"),
    ]


def normalized_artifact_name(name: str, rel: Path) -> str:
    if rel.as_posix() == "assets/env/paper2skill.environment.yml":
        return "environment.yml"
    if rel.as_posix() == "assets/env/normalization_report.json":
        return "normalization_report.json"
    if rel.as_posix() == "assets/requirements.txt":
        return "generated_skill_requirements.txt"
    if rel.as_posix() == "assets/environment.yml":
        return "environment.yml"
    if rel.as_posix() == "assets/environment_spec.yaml":
        return "environment_spec.yaml"
    return name


def merge_generated_skill_pip_segment(scan: dict[str, Any], work_root: Path, *, install_approval: dict[str, Any] | None = None) -> None:
    sources: list[dict[str, Any]] = []
    packages: list[str] = []
    report_path = work_root / "normalization_report.json"
    if report_path.exists():
        report = load_generated_normalization_report(report_path)
        segment = unique_strings(report.get("pip_segment") if isinstance(report, dict) else [])
        if segment:
            packages.extend(segment)
            sources.append({"source": "assets/env/normalization_report.json", "packages": segment})
    requirements_path = work_root / "generated_skill_requirements.txt"
    if requirements_path.exists():
        routed = generated_requirements_routes(parse_generated_requirements(requirements_path), install_approval=install_approval)
        segment = unique_strings(routed.get("uv") or [])
        conda_segment = unique_strings(routed.get("conda") or [])
        if segment:
            packages.extend(segment)
            sources.append({"source": "assets/requirements.txt", "packages": segment})
        if conda_segment:
            scan["generated_requirements_conda_segment"] = unique_strings([*(scan.get("generated_requirements_conda_segment") or []), *conda_segment])
            scan["generated_requirements_route_migrations"] = [*(scan.get("generated_requirements_route_migrations") or []), *(routed.get("migrations") or [])]
        if routed.get("manual"):
            scan["generated_requirements_manual_blocks"] = [*(scan.get("generated_requirements_manual_blocks") or []), *routed["manual"]]
    if not packages:
        return
    merged = unique_strings([*(scan.get("pip_segment") or []), *packages])
    scan["pip_segment"] = merged
    scan["pip_segment_sources"] = [*(scan.get("pip_segment_sources") or []), *sources]


def load_generated_normalization_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_generated_requirements(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    packages: list[str] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or cleaned.startswith("-"):
            continue
        packages.append(cleaned)
    return unique_strings(packages)


def generated_requirements_routes(packages: list[str], *, install_approval: dict[str, Any] | None = None) -> dict[str, Any]:
    return route_python_packages(packages, install_approval=install_approval)


def materialize_install_request_evidence(request: dict[str, Any], dest: Path, scanned_artifacts: list[dict[str, Any]], *, python_version: str) -> None:
    if not request:
        return
    conda_packages = unique_strings(request.get("conda_packages") or [])
    python_packages = unique_strings(request.get("missing_python_packages") or request.get("python_packages") or [])
    r_packages = unique_strings(request.get("missing_r_packages") or request.get("r_packages") or [])
    executables = unique_strings(request.get("missing_executables") or [])
    if conda_packages or executables:
        if not (dest / "environment.yml").exists() and not (dest / "environment.yaml").exists():
            env = {
                "name": "paper2skill-case-evidence",
                "channels": channels_from_request(request),
                "dependencies": [f"python={python_version}", "pip", *conda_packages],
            }
            if any(str(item).lower() == "rscript" for item in executables) and "r-base" not in env["dependencies"]:
                env["dependencies"].append("r-base")
            path = dest / "environment.yml"
            path.write_text(yaml.safe_dump(env, sort_keys=False), encoding="utf-8")
            scanned_artifacts.append({"source": "case_yaml_dependencies", "materialized": str(path), "name": path.name, "priority": len(scanned_artifacts) + 1})
        else:
            scanned_artifacts.append({"source": "case_yaml_dependencies", "materialized": None, "name": "case_install_request", "priority": len(scanned_artifacts) + 1})
    if python_packages:
        path = dest / "requirements.txt"
        if not path.exists():
            path.write_text("\n".join(python_packages) + "\n", encoding="utf-8")
            scanned_artifacts.append({"source": "case_yaml_dependencies", "materialized": str(path), "name": path.name, "priority": len(scanned_artifacts) + 1})
    if r_packages:
        path = dest / "DESCRIPTION"
        if not path.exists():
            path.write_text("Package: paper2skill-case-evidence\nImports:\n    " + ",\n    ".join(r_packages) + "\n", encoding="utf-8")
            scanned_artifacts.append({"source": "case_yaml_dependencies", "materialized": str(path), "name": path.name, "priority": len(scanned_artifacts) + 1})


def merged_install_approval(install_request: dict[str, Any] | None, *, skill_dir: str | Path | None, explicit: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in [load_skill_install_approval(skill_dir), install_request_install_approval(install_request or {}), explicit or {}]:
        merged = merge_install_approval(merged, source)
    return normalize_install_approval(merged)


def load_skill_install_approval(skill_dir: str | Path | None) -> dict[str, Any]:
    if not skill_dir:
        return {}
    path = Path(skill_dir) / "assets" / "env" / "approved_install_sources.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def install_request_install_approval(request: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ["install_approval", "install_allowlist", "approved_install_sources"]:
        value = request.get(key)
        if isinstance(value, dict):
            merged = merge_install_approval(merged, value)
    return merged


def merge_install_approval(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if not right:
        return left
    normalized_right = normalize_install_approval(right)
    merged = dict(left)
    for key in ["python_direct_urls", "python_vcs_urls"]:
        merged[key] = [*(merged.get(key) or []), *(normalized_right.get(key) or [])]
    for key in ["approval_source", "source", "reason"]:
        if right.get(key):
            merged[key] = right[key]
    return merged


def canonical_env_path_for_plan(plan: dict[str, Any], *, skill_dir: str | Path | None) -> str | None:
    canonical_path = (((plan.get("canonical_environment") or {}).get("report") or {}).get("canonical_path")) or CANONICAL_ENV_RELATIVE_PATH
    workdir = plan.get("workdir")
    if workdir:
        return str(Path(str(workdir)) / str(canonical_path))
    if skill_dir:
        return str(Path(skill_dir) / str(canonical_path))
    return str(canonical_path)


def plan_existing_environment(
    scan: dict[str, Any],
    *,
    env: str,
    env_path: str,
    layers: dict[str, Any],
    python_version: str,
    gpu_policy: str,
    torch_backend: str,
    r_mode: str,
    lock_trust: dict[str, Any],
    canonical: dict[str, Any],
    allow_shared_env: bool,
    allow_github_install: str,
    install_approval: dict[str, Any],
    allow_install: str | None,
) -> dict[str, Any]:
    probe = scan.get("environment_probe") if isinstance(scan.get("environment_probe"), dict) else None
    if not package_inventory_probe_complete(probe):
        commands: list[dict[str, Any]] = []
        append_environment_inventory_probe(commands, scan=scan, layers=layers, env=env, env_path=env_path, allow_github_install=allow_github_install)
        return environment_plan_result(
            env=env,
            env_path=env_path,
            target="existing",
            layers=layers,
            python_version=python_version,
            gpu_policy=gpu_policy,
            torch_backend=torch_backend,
            r_mode=r_mode,
            lock_trust=lock_trust,
            canonical=canonical,
            commands=commands,
            warnings=["existing environment mode requires complete package inventory probe evidence before any install diff; returning diagnostic inventory probe only"],
            errors=[],
            mode="existing_inventory_probe_required",
            frozen=False,
            workdir=scan.get("repo"),
            allow_shared_env=allow_shared_env,
            allow_github_install=allow_github_install,
            allow_install=allow_install,
            status_override="blocked_diagnostic",
        )

    request = existing_install_request_from_scan(scan, canonical=canonical, layers=layers, allow_github_install=allow_github_install)
    request["install_approval"] = install_approval
    commands = existing_missing_diff_commands(
        request,
        layers=layers,
        env=env,
        env_path=env_path,
        allow_github_install=allow_github_install,
        gpu_policy=gpu_policy,
        torch_backend=torch_backend,
        install_approval=install_approval,
    )
    append_environment_probe(commands, scan=scan, layers=layers, env=env, env_path=env_path, allow_github_install=allow_github_install)
    result = environment_plan_result(
        env=env,
        env_path=env_path,
        target="existing",
        layers=layers,
        python_version=python_version,
        gpu_policy=gpu_policy,
        torch_backend=torch_backend,
        r_mode=r_mode,
        lock_trust=lock_trust,
        canonical=canonical,
        commands=commands,
        warnings=["existing environment mode uses probe evidence and only installs missing dependencies"],
        errors=[],
        mode="existing_missing_diff",
        frozen=False,
        workdir=scan.get("repo"),
        allow_shared_env=allow_shared_env,
        allow_github_install=allow_github_install,
        allow_install=allow_install,
    )
    result["plan_source"] = "existing_missing_diff"
    result["environment_probe"] = probe
    result["existing_environment_diff"] = existing_environment_diff(request)
    result["install_approval"] = install_approval
    result["repair_allowlist"] = unique_strings(request.get("repair_allowlist") or request.get("allowed_repair_packages") or [])
    result["route_resolution"] = existing_route_resolution(request, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
    command_manual_blocks = [command for command in commands if command.get("manual_approval_required") is True]
    result["manual_blocks"] = command_manual_blocks
    result["manual_approval_required"] = bool(command_manual_blocks)
    if result["status"] == "blocked_manual" and not command_manual_blocks:
        result["status"] = "ready"
    return result


def existing_missing_diff_commands(
    request: dict[str, Any],
    *,
    layers: dict[str, Any],
    env: str,
    env_path: str,
    allow_github_install: str,
    gpu_policy: str,
    torch_backend: str,
    install_approval: dict[str, Any],
) -> list[dict[str, Any]]:
    channels, _channel_notes = normalize_channels(channels_from_request(request))
    conda_packages = subtract_installed(unique_strings(request.get("conda_packages") or []), request.get("installed_conda_packages") or [])
    python_packages = subtract_installed(unique_strings(request.get("missing_python_packages") or request.get("python_packages") or []), request.get("installed_python_packages") or [])
    r_packages = subtract_installed(unique_strings(request.get("missing_r_packages") or request.get("r_packages") or []), request.get("installed_r_packages") or [])
    executables = subtract_installed(unique_strings(request.get("missing_executables") or []), request.get("available_executables") or [])
    r_resolved = resolve_r_packages(r_packages)
    cli_resolved = route_cli_executables(executables)
    python_resolved = route_python_packages(python_packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
    conda_packages = sorted(dict.fromkeys([*conda_packages, *r_resolved["conda_packages"], *cli_resolved["conda_packages"], *python_resolved["conda"]]))
    r_github = unique_strings(request.get("r_github_packages") or [])
    if r_github and allow_github_install == "approved":
        conda_packages = sorted(dict.fromkeys([*conda_packages, *subtract_installed(R_GITHUB_RUNTIME_CONDA_PACKAGES, request.get("installed_conda_packages") or [])]))
    commands: list[dict[str, Any]] = []
    if conda_packages:
        commands.append(
            {
                "kind": "conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": conda_packages,
                "channels": channels,
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(channels), *conda_packages],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(channels), *conda_packages],
            }
        )
    for route in python_resolved.get("special") or []:
        if route.get("manual_approval_required"):
            commands.append(manual_special_route_command(route, source="existing_missing_diff"))
        elif route.get("conda_packages"):
            commands.append(special_conda_route_command(route, env=env, source="existing_missing_diff"))
    if python_resolved["uv"]:
        command_env = env if layers.get("uses_conda") else env_path
        commands.append(uv_pip_command(command_env, python_resolved["uv"], torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    for route in python_resolved.get("manual") or []:
        commands.append(manual_special_route_command(route, source="existing_missing_diff"))
    if r_github:
        commands.append(github_r_command(env, r_github, allow_github_install=allow_github_install))
    commands.extend(manual_r_package_command(package, source="existing_missing_diff") for package in r_resolved["manual_packages"])
    for item in cli_resolved.get("manual") or []:
        commands.append(manual_special_route_command({"name": item.get("name"), "reason": item.get("reason")}, source="existing_missing_diff"))
    return dedupe_commands(commands)


def existing_route_resolution(
    request: dict[str, Any],
    *,
    gpu_policy: str,
    torch_backend: str,
    install_approval: dict[str, Any],
) -> dict[str, Any]:
    python_packages = subtract_installed(unique_strings(request.get("missing_python_packages") or request.get("python_packages") or []), request.get("installed_python_packages") or [])
    r_packages = subtract_installed(unique_strings(request.get("missing_r_packages") or request.get("r_packages") or []), request.get("installed_r_packages") or [])
    executables = subtract_installed(unique_strings(request.get("missing_executables") or []), request.get("available_executables") or [])
    return {
        "python": route_python_packages(python_packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval),
        "r": resolve_r_packages(r_packages),
        "cli": route_cli_executables(executables),
    }


def existing_install_request_from_scan(
    scan: dict[str, Any],
    *,
    canonical: dict[str, Any],
    layers: dict[str, Any],
    allow_github_install: str,
) -> dict[str, Any]:
    request = scan.get("case_install_request") if isinstance(scan.get("case_install_request"), dict) else {}
    probe = scan.get("environment_probe") if isinstance(scan.get("environment_probe"), dict) else {}
    executables = unique_strings(
        [
            *(request.get("missing_executables") or []),
            *cli_dependencies(scan),
        ]
    )
    if needs_r_runtime(scan, layers=layers, allow_github_install=allow_github_install):
        executables.append("Rscript")
    return {
        "conda_channels": channels_from_request(request),
        "conda_packages": unique_strings([*(request.get("conda_packages") or []), *canonical_required_conda_packages(canonical)]),
        "missing_python_packages": unique_strings([*(request.get("missing_python_packages") or request.get("python_packages") or []), *scan_python_packages(scan)]),
        "missing_r_packages": unique_strings([*(request.get("missing_r_packages") or request.get("r_packages") or []), *r_dependencies(scan)]),
        "missing_executables": unique_strings(executables),
        "r_github_packages": unique_strings([*(request.get("r_github_packages") or []), *((scan.get("r") or {}).get("install_r_github") or [])]),
        "installed_conda_packages": installed_probe_values(probe, "conda"),
        "installed_python_packages": installed_probe_values(probe, "python"),
        "installed_r_packages": installed_probe_values(probe, "r"),
        "available_executables": installed_probe_values(probe, "executables"),
        "repair_allowlist": unique_strings(request.get("repair_allowlist") or request.get("allowed_repair_packages") or []),
    }


def package_inventory_probe_complete(probe: dict[str, Any] | None) -> bool:
    if not isinstance(probe, dict):
        return False
    if probe.get("probe_type") != "package_inventory":
        return False
    if probe.get("inventory_complete") is not True:
        return False
    required = ["installed_python_packages", "installed_r_packages", "installed_conda_packages"]
    return all(isinstance(probe.get(key), list) for key in required)


def canonical_required_conda_packages(canonical: dict[str, Any]) -> list[str]:
    dependencies = ((canonical.get("environment") or {}).get("dependencies") or []) if isinstance(canonical, dict) else []
    packages: list[str] = []
    for dep in dependencies:
        if not isinstance(dep, str):
            continue
        key = package_key(dep)
        if key in {"python", "pip", "uv"}:
            continue
        packages.append(dep)
    return unique_strings(packages)


def installed_probe_values(probe: dict[str, Any], category: str) -> list[str]:
    installed = probe.get("installed") if isinstance(probe.get("installed"), dict) else {}
    aliases = {
        "conda": ["installed_conda_packages", "conda_packages"],
        "python": ["installed_python_packages", "python_packages", "pip_packages"],
        "r": ["installed_r_packages", "r_packages"],
        "executables": ["available_executables", "executables"],
    }
    values: list[Any] = []
    for key in aliases.get(category, []):
        values.extend(as_probe_list(probe.get(key)))
        values.extend(as_probe_list(installed.get(key)))
    if category == "executables":
        if probe.get("which_python") or probe.get("sys_executable"):
            values.append("python")
        if probe.get("rscript_path"):
            values.append("Rscript")
    return unique_strings(values)


def as_probe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def environment_plan_result(
    *,
    env: str,
    env_path: str,
    target: str,
    layers: dict[str, Any],
    python_version: str,
    gpu_policy: str,
    torch_backend: str,
    r_mode: str,
    lock_trust: dict[str, Any],
    canonical: dict[str, Any],
    commands: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    mode: str,
    frozen: bool,
    workdir: Any,
    allow_shared_env: bool,
    allow_github_install: str,
    allow_install: str | None = None,
    status_override: str | None = None,
) -> dict[str, Any]:
    canonical_report = canonical.get("report") if isinstance(canonical, dict) else {}
    canonical_manual_blocks = [] if frozen else list((canonical_report or {}).get("manual_blocks") or [])
    command_manual_blocks = [command for command in commands if command.get("manual_approval_required") is True]
    manual_blocks = [*canonical_manual_blocks, *command_manual_blocks]
    manual_approval_required = has_manual_commands(commands) or bool(canonical_manual_blocks)
    status = status_override or ("invalid" if errors else ("blocked_manual" if manual_approval_required else "ready"))
    return {
        "schema_version": 1,
        "status": status,
        "env": env,
        "resolved_env_path": env_path,
        "workdir": workdir,
        "target": target,
        "allow_install": allow_install,
        "mode": mode,
        "frozen": frozen,
        "manager": "conda-lock" if frozen else layers["manager"],
        "python_version": python_version,
        "gpu_policy": gpu_policy,
        "torch_backend": torch_backend,
        "r_mode": r_mode,
        "needs_r_runtime": bool(layers.get("needs_r_runtime")),
        "r_runtime_reason": layers.get("r_runtime_reason"),
        "conda_packages_added": layers.get("conda_packages_added") or [],
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
        "lock_trust": lock_trust,
        "canonical_environment": canonical,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "manual_blocks": manual_blocks,
        "manual_approval_required": manual_approval_required,
        "repair_policy": "suggestion_only" if frozen else "additive_or_route_migration",
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
    install_approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_target(target)
    validate_install_env(env, allow_shared_env=allow_shared_env)
    torch_backend = validate_torch_backend(torch_backend)
    env_path = env_path or env
    install_approval = normalize_install_approval(install_approval or install_request_install_approval(install_request))
    channels, channel_notes = normalize_channels(channels_from_request(install_request))
    conda_packages = unique_strings(install_request.get("conda_packages") or [])
    python_packages = unique_strings(install_request.get("missing_python_packages") or install_request.get("python_packages") or [])
    r_packages = unique_strings(install_request.get("missing_r_packages") or install_request.get("r_packages") or [])
    r_github = unique_strings(install_request.get("r_github_packages") or [])
    executables = unique_strings(install_request.get("missing_executables") or [])
    repair_allowlist = unique_strings(install_request.get("repair_allowlist") or install_request.get("allowed_repair_packages") or [])
    if target == "existing":
        conda_packages = subtract_installed(conda_packages, install_request.get("installed_conda_packages") or [])
        python_packages = subtract_installed(python_packages, install_request.get("installed_python_packages") or [])
        r_packages = subtract_installed(r_packages, install_request.get("installed_r_packages") or [])
        executables = subtract_installed(executables, install_request.get("available_executables") or [])
    r_resolved = resolve_r_packages(r_packages)
    conda_packages.extend(r_resolved["conda_packages"])
    cli_resolved = route_cli_executables(executables)
    conda_packages.extend(cli_resolved["conda_packages"])
    python_resolved = route_python_packages(python_packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
    conda_packages.extend(python_resolved["conda"])
    special_conda_routes = [route for route in python_resolved.get("special") or [] if not route.get("manual_approval_required") and route.get("conda_packages")]
    approved_r_github = bool(r_github and allow_github_install == "approved")
    if approved_r_github:
        conda_packages.extend(R_GITHUB_RUNTIME_CONDA_PACKAGES)
    uv_python = python_resolved["uv"]
    conda_packages = sorted(dict.fromkeys(conda_packages))
    needs_conda = bool(conda_packages or r_packages or approved_r_github or executables or special_conda_routes)
    commands: list[dict[str, Any]] = []
    if target == "new":
        if needs_conda:
            commands.append(conda_create_command(env, python_version, include_r=bool(r_packages or approved_r_github), channels=channels))
        else:
            commands.append(uv_create_command(env_path, python_version))
    if conda_packages:
        commands.append(
            {
                "kind": "conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": conda_packages,
                "channels": channels,
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(channels), *conda_packages],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(channels), *conda_packages],
            }
        )
    if uv_python:
        commands.append(uv_pip_command(env_path if not needs_conda else env, uv_python, torch_backend=torch_backend, inside_conda=needs_conda))
    for route in python_resolved.get("special") or []:
        if route.get("manual_approval_required"):
            commands.append(manual_special_route_command(route, source="install_request"))
        elif route.get("conda_packages"):
            commands.append(special_conda_route_command(route, env=env, source="install_request"))
    for route in python_resolved.get("manual") or []:
        commands.append(manual_special_route_command(route, source="install_request"))
    if r_github:
        commands.append(github_r_command(env, r_github, allow_github_install=allow_github_install))
    commands.extend(manual_r_package_command(package, source="install_request") for package in r_resolved["manual_packages"])
    commands = dedupe_commands(commands)
    manager = "conda+uv" if needs_conda and uv_python else ("conda" if needs_conda else "uv")
    probe_layers = {
        "manager": "conda" if needs_conda else "uv",
        "uses_conda": needs_conda,
        "uses_uv": bool(uv_python) or not needs_conda,
        "needs_r_runtime": approved_r_github or bool(r_packages),
        "r_runtime_reason": "r_github_install" if approved_r_github else ("r_package_install" if r_packages else None),
        "conda_packages_added": R_GITHUB_RUNTIME_CONDA_PACKAGES if approved_r_github else [],
    }
    append_environment_probe(
        commands,
        scan={"case_install_request": install_request},
        layers=probe_layers,
        env=env,
        env_path=env_path,
        allow_github_install=allow_github_install,
    )
    manual_approval_required = has_manual_commands(commands)
    status = "blocked_manual" if manual_approval_required else "ready"
    return {
        "schema_version": 1,
        "status": status,
        "env": env,
        "resolved_env_path": env_path,
        "target": target,
        "manager": "conda+uv" if needs_conda and uv_python else ("conda" if needs_conda else "uv"),
        "needs_r_runtime": approved_r_github or bool(r_packages),
        "r_runtime_reason": "r_github_install" if approved_r_github else ("r_package_install" if r_packages else None),
        "conda_packages_added": R_GITHUB_RUNTIME_CONDA_PACKAGES if approved_r_github else [],
        "python_version": python_version,
        "gpu_policy": gpu_policy,
        "torch_backend": torch_backend,
        "dry_run": True,
        "auto_install_performed": False,
        "commands": commands,
        "errors": [],
        "warnings": [*(item.get("reason", "") for item in channel_notes), *build_plan_warnings(r_github, allow_github_install, r_resolved), *(item.get("reason", "") for item in python_resolved.get("manual") or []), *(item.get("reason", "") for item in cli_resolved.get("manual") or [])],
        "manual_approval_required": manual_approval_required,
        "repair_allowlist": repair_allowlist,
        "install_approval": install_approval,
        "route_resolution": {"python": python_resolved, "r": r_resolved, "cli": cli_resolved},
        "manual_blocks": [*(python_resolved.get("manual") or []), *(r_resolved.get("manual") or []), *(cli_resolved.get("manual") or [])],
        "existing_environment_diff": existing_environment_diff(install_request) if target == "existing" else None,
        "safety": {
            "requires_execute_flag": True,
            "requires_yes_flag": True,
            "shared_env_allowed": allow_shared_env,
            "github_install_default": allow_github_install,
            "unknown_install_scripts_executed": False,
            "notebook_execution_performed": False,
        },
        "lock_outputs": planned_lock_outputs({"manager": manager}),
    }


def choose_layers(
    scan: dict[str, Any],
    *,
    target: str,
    manager_preference: str,
    install_approval: dict[str, Any] | None = None,
    allow_github_install: str = "ask",
) -> dict[str, Any]:
    signals = scan.get("signals") or {}
    gpu = scan.get("gpu") or {}
    has_r = bool(signals.get("has_r_or_bioc"))
    has_conda = bool(signals.get("has_conda_spec"))
    has_workflow = bool(scan.get("workflow_engines"))
    routed_python = route_python_packages(scan_python_packages(scan), install_approval=install_approval)
    generated_requirements_need_conda = bool(scan.get("generated_requirements_conda_segment"))
    python_needs_conda = bool(
        routed_python.get("conda")
        or generated_requirements_need_conda
        or [item for item in routed_python.get("special") or [] if item.get("conda_packages")]
    )
    r_runtime = has_r_runtime_requirement(scan, allow_github_install=allow_github_install)
    needs_conda = has_r or has_conda or has_workflow or python_needs_conda or bool(r_runtime.get("needs_r_runtime"))
    if manager_preference in {"uv", "conda"}:
        manager = manager_preference
    elif needs_conda:
        manager = "conda"
    else:
        manager = "uv"
    if gpu.get("uses_torch") and gpu.get("cuda_signal"):
        pytorch_strategy = "special_torch_requires_explicit_cuda_profile"
    elif gpu.get("uses_torch"):
        pytorch_strategy = "special_torch_conda_cpu_default"
    else:
        pytorch_strategy = "not_applicable"
    return {
        "manager": manager,
        "needs_conda": needs_conda,
        "uses_uv": manager == "uv" or not needs_conda,
        "uses_conda": manager == "conda" or needs_conda,
        "pytorch_strategy": pytorch_strategy,
        "python_needs_conda": python_needs_conda,
        "generated_requirements_need_conda": generated_requirements_need_conda,
        "needs_r_runtime": bool(r_runtime.get("needs_r_runtime")),
        "r_runtime_reason": r_runtime.get("r_runtime_reason"),
        "conda_packages_added": r_runtime.get("conda_packages_added") or [],
        "r_runtime_signals": r_runtime.get("signals") or [],
        "target_mode": target,
    }


def has_r_runtime_requirement(scan: dict[str, Any], *, allow_github_install: str) -> dict[str, Any]:
    r = scan.get("r") or {}
    request = scan.get("case_install_request") or {}
    signals: list[dict[str, Any]] = []

    def add_signal(source: str, key: str, values: Any, *, requires_approval: bool = False) -> None:
        items = unique_strings(values or [])
        if not items:
            return
        signals.append(
            {
                "source": source,
                "key": key,
                "values": items,
                "requires_approval": requires_approval,
                "approved": (allow_github_install == "approved") if requires_approval else True,
            }
        )

    add_signal("case_install_request", "r_github_packages", request.get("r_github_packages"), requires_approval=True)
    add_signal("repo_r_metadata", "install_r_github", r.get("install_r_github"), requires_approval=True)
    add_signal("case_install_request", "r_packages", request.get("r_packages") or request.get("missing_r_packages"))
    add_signal("repo_r_metadata", "cran", r.get("cran"))
    add_signal("repo_r_metadata", "bioconductor", r.get("bioconductor"))
    add_signal("repo_r_metadata", "github", r.get("github"), requires_approval=True)
    add_signal("repo_r_metadata", "install_r_packages", r.get("install_r_packages"))
    add_signal("repo_r_metadata", "description_packages", r.get("description_packages"))
    add_signal("repo_r_metadata", "namespace_packages", r.get("namespace_packages"))

    approved_signals = [item for item in signals if item.get("approved")]
    github_signals = [item for item in approved_signals if item.get("requires_approval")]
    if github_signals:
        return {
            "needs_r_runtime": True,
            "r_runtime_reason": "r_github_install",
            "conda_packages_added": list(R_GITHUB_RUNTIME_CONDA_PACKAGES),
            "signals": signals,
        }
    if approved_signals:
        return {
            "needs_r_runtime": True,
            "r_runtime_reason": "r_package_install",
            "conda_packages_added": [],
            "signals": signals,
        }
    return {
        "needs_r_runtime": False,
        "r_runtime_reason": None,
        "conda_packages_added": [],
        "signals": signals,
    }


def create_environment_commands(layers: dict[str, Any], *, env: str, env_path: str, python_version: str, scan: dict[str, Any], torch_backend: str, canonical: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if layers.get("manager") == "uv":
        commands.append(uv_create_command(env_path, python_version))
    else:
        if canonical and canonical.get("environment"):
            command = derived_conda_env_create_command(env, canonical)
            if scan.get("repo"):
                command["cwd"] = scan.get("repo")
            commands.append(command)
        else:
            include_r = bool((scan.get("r") or {}).get("has_r") or layers.get("needs_r_runtime"))
            commands.append(conda_create_command(env, python_version, include_r=include_r, channels=DEFAULT_BIOCONDA_CHANNELS))
    commands.extend(canonical_pip_segment_commands(canonical, env=env, env_path=env_path, inside_conda=bool(layers.get("uses_conda"))))
    return commands


def canonical_pip_segment_commands(canonical: dict[str, Any] | None, *, env: str, env_path: str, inside_conda: bool) -> list[dict[str, Any]]:
    pip_segment = canonical_pip_segment(canonical)
    if not pip_segment:
        return []
    command_env = env if inside_conda else env_path
    command = uv_pip_command(command_env, pip_segment, torch_backend="auto", inside_conda=inside_conda)
    command["source"] = CANONICAL_ENV_RELATIVE_PATH
    command["scope"] = "pip_uv_segment"
    return [command]


def canonical_pip_segment(canonical: dict[str, Any] | None) -> list[str]:
    report = canonical.get("report") if isinstance(canonical, dict) else {}
    return unique_strings((report or {}).get("pip_segment") or [])


def frozen_conda_lock_commands(scan: dict[str, Any], *, layers: dict[str, Any], env: str, env_path: str, lock_trust: dict[str, Any], allow_github_install: str) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    workdir = scan.get("repo")
    full_lock = next((item for item in lock_trust.get("trusted") or [] if item.get("scope") == "full_conda_environment" and item.get("trusted") is True), None)
    if full_lock:
        command = lockfile_command(env, full_lock, env_path=env_path, inside_conda=True)
        if command:
            command["kind"] = "restore_conda_lock"
            command["mode"] = "lockfile_restore"
            command["frozen"] = True
            if workdir:
                command["cwd"] = workdir
            commands.append(command)
    append_environment_probe(commands, scan=scan, layers=layers, env=env, env_path=env_path, allow_github_install=allow_github_install)
    return commands


def spec_install_commands(scan: dict[str, Any], layers: dict[str, Any], *, env: str, env_path: str, target: str, allow_github_install: str, gpu_policy: str, torch_backend: str, lock_trust: dict[str, Any] | None = None, canonical: dict[str, Any] | None = None, install_approval: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    files = scan.get("environment_files") or []
    commands: list[dict[str, Any]] = []
    trusted_locks = (lock_trust or {}).get("trusted") or []
    workdir = scan.get("repo")
    for item in trusted_locks:
        command = lockfile_command(env, item, env_path=env_path, inside_conda=bool(layers.get("uses_conda")))
        if command:
            if workdir:
                command["cwd"] = workdir
            commands.append(command)
    if target != "new" and canonical and canonical.get("environment") and not has_trusted_full_conda_lock(lock_trust or {}):
        command = derived_conda_env_update_command(env, canonical)
        if workdir:
            command["cwd"] = workdir
        commands.append(command)
    requirements = [item for item in files if str(item.get("name") or "").startswith("requirements")]
    for item in requirements:
        packages = requirement_packages_from_scan(scan, item)
        routed = route_python_packages(packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
        commands.extend(python_route_commands(routed, env=env, env_path=env_path, source=str(item.get("path") or item.get("name")), inside_conda=bool(layers.get("uses_conda"))))
    python = scan.get("python") or {}
    setup_requires = unique_strings(python.get("setup_cfg_install_requires") or [])
    canonical_pip = set(canonical_pip_segment(canonical))
    if setup_requires and not requirements:
        routed_python = route_python_packages(setup_requires, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
        binary_python, uv_python = routed_python["conda"], routed_python["uv"]
        uv_python = [package for package in uv_python if package not in canonical_pip]
        if binary_python and layers.get("uses_conda"):
            commands.append(
                {
                    "kind": "setup_cfg_conda_python_packages",
                    "tier": 3,
                    "installer": "mamba_or_conda",
                    "packages": binary_python,
                    "channels": ["conda-forge"],
                    "route_migrations": routed_python["migrations"],
                    "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(["conda-forge"]), *binary_python],
                    "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(["conda-forge"]), *binary_python],
                }
            )
        elif binary_python:
            uv_python = sorted(dict.fromkeys([*uv_python, *binary_python]))
        for route in routed_python.get("special") or []:
            if route.get("manual_approval_required"):
                commands.append(manual_special_route_command(route, source="setup.cfg"))
            elif route.get("conda_packages"):
                commands.append(special_conda_route_command(route, env=env, source="setup.cfg"))
        for route in routed_python.get("manual") or []:
            if not any(command.get("special_route") == route for command in commands):
                commands.append(manual_special_route_command(route, source="setup.cfg"))
        if uv_python:
            commands.append(uv_pip_command(env if layers.get("uses_conda") else env_path, uv_python, torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda"))))
    if python.get("project_name") and not requirements and str(python["project_name"]) not in canonical_pip:
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
                "r_routes": r_resolved.get("routes", []),
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *conda_r],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *conda_r],
            }
        )
    commands.extend(r_runtime_conda_commands(layers, env=env, source="r_runtime_requirement"))
    commands.extend(readme_install_commands(scan.get("install_commands") or [], env=env if layers.get("uses_conda") else env_path, env_path=env_path, allow_github_install=allow_github_install, gpu_policy=gpu_policy, torch_backend=torch_backend, inside_conda=bool(layers.get("uses_conda")), install_approval=install_approval))
    commands.extend(case_install_request_commands(scan.get("case_install_request") or {}, env=env, env_path=env_path, layers=layers, allow_github_install=allow_github_install, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval))
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
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *workflow_packages],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *workflow_packages],
            }
        )
    for package in r_resolved["manual_packages"]:
        commands.append(manual_r_package_command(package, source="r_package_resolution"))
    return dedupe_commands(commands)


def r_runtime_conda_commands(layers: dict[str, Any], *, env: str, source: str) -> list[dict[str, Any]]:
    packages = unique_strings(layers.get("conda_packages_added") or [])
    if not packages:
        return []
    return [
        {
            "kind": "r_runtime_conda_packages",
            "tier": 3,
            "installer": "mamba_or_conda",
            "packages": packages,
            "channels": ["conda-forge", "bioconda"],
            "source": source,
            "needs_r_runtime": True,
            "r_runtime_reason": layers.get("r_runtime_reason"),
            "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *packages],
            "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *packages],
        }
    ]


def case_install_request_commands(request: dict[str, Any], *, env: str, env_path: str, layers: dict[str, Any], allow_github_install: str, gpu_policy: str, torch_backend: str, install_approval: dict[str, Any] | None) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if not request:
        return commands
    conda_packages = unique_strings(request.get("conda_packages") or [])
    r_packages = unique_strings(request.get("missing_r_packages") or request.get("r_packages") or [])
    executables = unique_strings(request.get("missing_executables") or [])
    python_packages = unique_strings(request.get("missing_python_packages") or request.get("python_packages") or [])
    r_github = unique_strings(request.get("r_github_packages") or [])
    r_resolved = resolve_r_packages(r_packages)
    cli_resolved = route_cli_executables(executables)
    all_conda = sorted(dict.fromkeys([*conda_packages, *r_resolved["conda_packages"], *cli_resolved["conda_packages"]]))
    if all_conda:
        commands.append(
            {
                "kind": "case_dependency_conda_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": all_conda,
                "channels": channels_from_request(request),
                "source": "case_yaml_dependencies",
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(channels_from_request(request)), *all_conda],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(channels_from_request(request)), *all_conda],
            }
        )
    if python_packages:
        routed = route_python_packages(python_packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
        commands.extend(python_route_commands(routed, env=env, env_path=env_path, source="case_yaml_dependencies", inside_conda=bool(layers.get("uses_conda"))))
    if r_github:
        commands.append(github_r_command(env, r_github, allow_github_install=allow_github_install))
    for package in r_resolved["manual_packages"]:
        commands.append(manual_r_package_command(package, source="case_yaml_dependencies"))
    for item in cli_resolved.get("manual") or []:
        commands.append(manual_special_route_command({"name": item.get("name"), "reason": item.get("reason")}, source="case_yaml_dependencies"))
    return commands


def uv_create_command(env: str, python_version: str) -> dict[str, Any]:
    return {
        "kind": "uv_venv_create",
        "tier": 3,
        "installer": "uv",
        "packages": [],
        "skip_if_env_exists": True,
        "creates_env": True,
        "blocks_dependents_on_skip": True,
        "command": ["uv", "venv", "--python", python_version, env],
    }


def conda_create_command(env: str, python_version: str, *, include_r: bool, channels: list[str]) -> dict[str, Any]:
    channels, channel_notes = normalize_channels(channels)
    packages = [f"python={python_version}", "pip", "uv"]
    if include_r:
        packages.append("r-base")
    return {
        "kind": "conda_env_create",
        "tier": 3,
        "installer": "mamba_or_conda",
        "packages": packages,
        "channels": channels,
        "channel_notes": channel_notes,
        "skip_if_env_exists": True,
        "creates_env": True,
        "blocks_dependents_on_skip": True,
        "command": ["mamba", "create", "-y", *conda_env_args(env), *channel_args(channels), *packages],
        "fallback_command": ["conda", "create", "-y", *conda_env_args(env), *channel_args(channels), *packages],
    }


def append_environment_probe(
    commands: list[dict[str, Any]],
    *,
    scan: dict[str, Any],
    layers: dict[str, Any],
    env: str,
    env_path: str,
    allow_github_install: str,
) -> None:
    if any(command.get("kind") == "environment_probe" for command in commands):
        return
    probe = environment_probe_command(
        layers,
        env=env,
        env_path=env_path,
        needs_r_runtime=needs_r_runtime(scan, layers=layers, allow_github_install=allow_github_install),
    )
    if scan.get("repo"):
        probe["cwd"] = scan.get("repo")
    commands.append(probe)


def append_environment_inventory_probe(
    commands: list[dict[str, Any]],
    *,
    scan: dict[str, Any],
    layers: dict[str, Any],
    env: str,
    env_path: str,
    allow_github_install: str,
) -> None:
    if any(command.get("kind") == "environment_inventory_probe" for command in commands):
        return
    probe = environment_inventory_probe_command(
        layers,
        env=env,
        env_path=env_path,
        needs_r_runtime=needs_r_runtime(scan, layers=layers, allow_github_install=allow_github_install),
    )
    if scan.get("repo"):
        probe["cwd"] = scan.get("repo")
    commands.append(probe)


def needs_r_runtime(scan: dict[str, Any], layers: dict[str, Any] | None = None, *, allow_github_install: str = "ask") -> bool:
    if layers and layers.get("needs_r_runtime"):
        return True
    request = scan.get("case_install_request") if isinstance(scan.get("case_install_request"), dict) else {}
    executables = [str(item).lower() for item in request.get("missing_executables") or []]
    if "rscript" in executables:
        return True
    return bool(has_r_runtime_requirement(scan, allow_github_install=allow_github_install).get("needs_r_runtime"))


def environment_probe_command(
    layers: dict[str, Any] | None = None,
    *,
    env: str,
    env_path: str,
    needs_r_runtime: bool = False,
) -> dict[str, Any]:
    layers = layers or {"uses_conda": True, "manager": "conda"}
    uses_conda = bool(layers.get("uses_conda"))
    command = (
        ["conda", "run", *conda_env_args(env), "python", "-c", environment_probe_python(needs_r_runtime)]
        if uses_conda
        else [uv_python_executable(env_path), "-c", environment_probe_python(needs_r_runtime)]
    )
    return {
        "kind": "environment_probe",
        "tier": 1,
        "installer": "probe",
        "packages": [],
        "needs_r_runtime": needs_r_runtime,
        "repair_on_failure": "suggestion_only",
        "command": command,
    }


def environment_inventory_probe_command(
    layers: dict[str, Any] | None = None,
    *,
    env: str,
    env_path: str,
    needs_r_runtime: bool = False,
) -> dict[str, Any]:
    layers = layers or {"uses_conda": True, "manager": "conda"}
    uses_conda = bool(layers.get("uses_conda"))
    command = (
        ["conda", "run", *conda_env_args(env), "python", "-c", environment_inventory_probe_python(needs_r_runtime, uses_conda)]
        if uses_conda
        else [uv_python_executable(env_path), "-c", environment_inventory_probe_python(needs_r_runtime, uses_conda)]
    )
    return {
        "kind": "environment_inventory_probe",
        "tier": 1,
        "installer": "probe",
        "packages": [],
        "needs_r_runtime": needs_r_runtime,
        "repair_on_failure": "suggestion_only",
        "command": command,
    }


def environment_probe_python(needs_r_runtime: bool) -> str:
    return f"""
import json
import shutil
import subprocess
import sys

NEEDS_R_RUNTIME = {str(bool(needs_r_runtime))}

def run(cmd):
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        return {{"exit_code": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}}
    except FileNotFoundError as exc:
        return {{"exit_code": 127, "stdout": "", "stderr": f"executable not found: {{exc.filename or cmd[0]}}"}}

payload = {{
    "sys_executable": sys.executable,
    "sys_version": sys.version,
    "which_python": shutil.which("python"),
    "python_version": run(["python", "-V"]),
    "rscript_path": shutil.which("Rscript"),
    "needs_r_runtime": NEEDS_R_RUNTIME,
}}

if payload["rscript_path"]:
    payload["rscript_version"] = run(["Rscript", "--version"])
else:
    payload["rscript_version"] = {{"exit_code": 127, "stdout": "", "stderr": "Rscript not found"}}

exit_code = 0
if NEEDS_R_RUNTIME and (not payload["rscript_path"] or payload["rscript_version"]["exit_code"] != 0):
    payload["probe_failure"] = "rscript_missing_or_failed"
    payload["error_type"] = "activation_failure"
    exit_code = 3

print(json.dumps(payload, sort_keys=True))
raise SystemExit(exit_code)
""".strip()


def environment_inventory_probe_python(needs_r_runtime: bool, uses_conda: bool) -> str:
    return f"""
import importlib.metadata
import json
import shutil
import subprocess
import sys

NEEDS_R_RUNTIME = {str(bool(needs_r_runtime))}
USES_CONDA = {str(bool(uses_conda))}

def run(cmd):
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        return {{"exit_code": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}}
    except FileNotFoundError as exc:
        return {{"exit_code": 127, "stdout": "", "stderr": f"executable not found: {{exc.filename or cmd[0]}}"}}

def lines(result):
    if result.get("exit_code") != 0:
        return []
    return [line.strip() for line in result.get("stdout", "").splitlines() if line.strip()]

python_packages = sorted({{dist.metadata.get("Name", dist.metadata.get("name", "")).lower() for dist in importlib.metadata.distributions() if dist.metadata.get("Name", dist.metadata.get("name", ""))}})
conda_result = run(["conda", "list", "--json"]) if USES_CONDA else {{"exit_code": 0, "stdout": "[]", "stderr": ""}}
conda_packages = []
if conda_result["exit_code"] == 0:
    try:
        conda_packages = sorted({{str(item.get("name", "")).lower() for item in json.loads(conda_result["stdout"] or "[]") if item.get("name")}})
    except Exception as exc:
        conda_result["exit_code"] = 1
        conda_result["stderr"] = f"could not parse conda list JSON: {{exc}}"

rscript_path = shutil.which("Rscript")
rscript_version = run(["Rscript", "--version"]) if rscript_path else {{"exit_code": 127, "stdout": "", "stderr": "Rscript not found"}}
r_packages_result = run(["Rscript", "-e", "cat(paste(rownames(installed.packages()), collapse='\\\\n'))"]) if rscript_path else {{"exit_code": 0 if not NEEDS_R_RUNTIME else 127, "stdout": "", "stderr": "Rscript not found"}}
r_packages = lines(r_packages_result)

inventory_complete = (
    isinstance(python_packages, list)
    and isinstance(conda_packages, list)
    and isinstance(r_packages, list)
    and conda_result["exit_code"] == 0
    and (not NEEDS_R_RUNTIME or rscript_version["exit_code"] == 0)
    and r_packages_result["exit_code"] == 0
)
payload = {{
    "probe_type": "package_inventory",
    "inventory_complete": inventory_complete,
    "sys_executable": sys.executable,
    "sys_version": sys.version,
    "which_python": shutil.which("python"),
    "python_version": run(["python", "-V"]),
    "rscript_path": rscript_path,
    "rscript_version": rscript_version,
    "needs_r_runtime": NEEDS_R_RUNTIME,
    "installed_python_packages": python_packages,
    "installed_r_packages": r_packages,
    "installed_conda_packages": conda_packages,
    "conda_list": conda_result,
}}
exit_code = 0
if not inventory_complete:
    payload["probe_failure"] = "package_inventory_incomplete"
    payload["error_type"] = "probe_failure"
    exit_code = 4
print(json.dumps(payload, sort_keys=True))
raise SystemExit(exit_code)
""".strip()


def lockfile_command(env: str, item: dict[str, Any], *, env_path: str | None = None, inside_conda: bool = False) -> dict[str, Any] | None:
    name = str(item.get("name") or "")
    path = str(item.get("path") or name)
    if name.startswith("conda-lock"):
        command = ["conda-lock", "install", *conda_env_args(env), path]
        installer = "conda-lock"
    elif name == "uv.lock":
        command = ["conda", "run", *conda_env_args(env), "uv", "sync", "--frozen", "--active"] if inside_conda else ["uv", "sync", "--frozen"]
        installer = "uv"
        record = {
            "kind": "uv_lock_segment_restore",
            "tier": 1,
            "installer": installer,
            "source": path,
            "scope": item.get("scope"),
            "trust": item,
            "requires_base_environment": True,
            "target_env": env,
            "resolved_env_path": env_path,
            "command": command,
        }
        if not inside_conda and env_path:
            record["environment"] = {"UV_PROJECT_ENVIRONMENT": env_path}
        return record
    elif name == "renv.lock":
        if item.get("trusted") is not True:
            return None
        command = ["Rscript", "-e", "renv::restore(prompt=FALSE)"]
        installer = "renv"
    else:
        command = ["uv", "pip", "install", "-r", path]
        installer = "uv"
    return {"kind": "lockfile_restore", "tier": 1, "installer": installer, "source": path, "scope": item.get("scope"), "trust": item, "command": command}


def derived_conda_env_create_command(env: str, canonical: dict[str, Any]) -> dict[str, Any]:
    env_data = canonical.get("environment") or {}
    return {
        "kind": "derived_conda_environment",
        "tier": 2,
        "installer": "mamba_or_conda",
        "source": CANONICAL_ENV_RELATIVE_PATH,
        "packages": env_data.get("dependencies") or [],
        "channels": env_data.get("channels") or DEFAULT_BIOCONDA_CHANNELS,
        "normalization_report": canonical.get("report") or {},
        "skip_if_env_exists": True,
        "creates_env": True,
        "blocks_dependents_on_skip": True,
        "command": ["mamba", "env", "create", *conda_env_args(env), "--strict-channel-priority", "-f", CANONICAL_ENV_RELATIVE_PATH],
        "fallback_command": ["conda", "env", "create", *conda_env_args(env), "--strict-channel-priority", "-f", CANONICAL_ENV_RELATIVE_PATH],
    }


def derived_conda_env_update_command(env: str, canonical: dict[str, Any]) -> dict[str, Any]:
    env_data = canonical.get("environment") or {}
    return {
        "kind": "derived_conda_environment_update",
        "tier": 2,
        "installer": "mamba_or_conda",
        "source": CANONICAL_ENV_RELATIVE_PATH,
        "packages": env_data.get("dependencies") or [],
        "channels": env_data.get("channels") or DEFAULT_BIOCONDA_CHANNELS,
        "normalization_report": canonical.get("report") or {},
        "command": ["mamba", "env", "update", *conda_env_args(env), "--strict-channel-priority", "-f", CANONICAL_ENV_RELATIVE_PATH],
        "fallback_command": ["conda", "env", "update", *conda_env_args(env), "--strict-channel-priority", "-f", CANONICAL_ENV_RELATIVE_PATH],
    }


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
        "depends_on_env_create": True,
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


def readme_install_commands(commands: list[dict[str, Any]], *, env: str, env_path: str, allow_github_install: str, gpu_policy: str, torch_backend: str, inside_conda: bool = False, install_approval: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
                    "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *packages],
                    "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(DEFAULT_BIOCONDA_CHANNELS), *packages],
                }
            )
        else:
            routed = route_python_packages(packages, gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
            planned.extend(python_route_commands(routed, env=env, env_path=env_path, source=str(item.get("source") or "README_install"), inside_conda=inside_conda))
    return planned


def requirement_packages_from_scan(scan: dict[str, Any], item: dict[str, Any]) -> list[str]:
    source = str(item.get("path") or item.get("name") or "")
    packages: list[str] = []
    for record in ((scan.get("python") or {}).get("requirements") or []):
        if source and record.get("source") != source and record.get("name") != item.get("name"):
            continue
        packages.extend(str(package) for package in record.get("packages") or [])
    return unique_strings(packages)


def scan_python_packages(scan: dict[str, Any]) -> list[str]:
    packages: list[str] = []
    python = scan.get("python") or {}
    for record in python.get("requirements") or []:
        packages.extend(str(package) for package in record.get("packages") or [])
    packages.extend(str(item) for item in python.get("setup_cfg_install_requires") or [])
    for command in python.get("readme_pip_installs") or []:
        packages.extend(parse_install_packages(str(command.get("command") or "")))
    if python.get("project_name"):
        packages.append(str(python["project_name"]))
    return unique_strings(packages)


def r_dependencies(scan: dict[str, Any]) -> list[str]:
    r = scan.get("r") or {}
    return [
        *(r.get("description_packages") or []),
        *(r.get("namespace_packages") or []),
        *(r.get("install_r_packages") or []),
    ]


def cli_dependencies(scan: dict[str, Any]) -> list[str]:
    executables = []
    for engine in scan.get("workflow_engines") or []:
        if engine.get("engine"):
            executables.append(str(engine["engine"]))
    return executables


def python_route_commands(routed: dict[str, Any], *, env: str, env_path: str, source: str, inside_conda: bool) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if routed.get("conda"):
        commands.append(
            {
                "kind": "conda_python_packages",
                "tier": 3,
                "installer": "mamba_or_conda",
                "packages": routed["conda"],
                "source": source,
                "scope": "compiled_python_stack",
                "route_migrations": routed.get("migrations") or [],
                "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(["conda-forge"]), *routed["conda"]],
                "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(["conda-forge"]), *routed["conda"]],
            }
        )
    for route in routed.get("special") or []:
        if route.get("manual_approval_required"):
            commands.append(manual_special_route_command(route, source=source))
        elif route.get("conda_packages"):
            commands.append(special_conda_route_command(route, env=env, source=source))
    if routed.get("uv"):
        command_env = env if inside_conda else env_path
        command = uv_pip_command(command_env, list(routed["uv"]), torch_backend="auto", inside_conda=inside_conda)
        command["source"] = source
        command["scope"] = "pip_uv_segment"
        commands.append(command)
    for route in routed.get("manual") or []:
        if not any(command.get("special_route") == route for command in commands):
            commands.append(manual_special_route_command(route, source=source))
    return commands


def manual_special_route_command(route: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "kind": "manual_special_route",
        "tier": 7,
        "installer": "manual",
        "packages": [route.get("name")],
        "source": source,
        "special_route": route,
        "approved_for_execution": False,
        "manual_approval_required": True,
        "reason": route.get("reason") or "special dependency route requires manual review",
    }


def special_conda_route_command(route: dict[str, Any], *, env: str, source: str) -> dict[str, Any]:
    channels = list(route.get("channels") or ["conda-forge"])
    packages = list(route.get("conda_packages") or [])
    return {
        "kind": "special_torch_conda_packages",
        "tier": 3,
        "installer": "mamba_or_conda",
        "packages": packages,
        "source": source,
        "special_route": route,
        "command": ["mamba", "install", "-y", *conda_env_args(env), *channel_args(channels), *packages],
        "fallback_command": ["conda", "install", "-y", *conda_env_args(env), *channel_args(channels), *packages],
    }


def parse_install_packages(command: str) -> list[str]:
    try:
        tokens = shlex.split(command.strip())
    except ValueError:
        tokens = command.strip().split()
    if "install" not in tokens:
        return []
    start = tokens.index("install") + 1
    packages = []
    skip_next = False
    index = start
    while index < len(tokens):
        token = tokens[index]
        if skip_next:
            skip_next = False
            index += 1
            continue
        if token in {"-c", "--channel", "-r", "--requirement", "--index-url", "--extra-index-url"}:
            skip_next = True
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        if index + 2 < len(tokens) and tokens[index + 1] == "@" and direct_url_requirement_type(tokens[index + 2]):
            packages.append(f"{token} @ {tokens[index + 2]}")
            index += 3
            continue
        packages.append(token.strip("'\""))
        index += 1
    return packages


def selected_python(scan: dict[str, Any]) -> str:
    python = scan.get("python") or {}
    return str(python.get("selected_python") or select_python_version(python.get("python_constraint")))


def split_python_packages(packages: list[str]) -> tuple[list[str], list[str]]:
    routed = route_python_packages(packages)
    return routed["conda"], routed["uv"]


def resolve_r_packages(packages: list[str]) -> dict[str, list[str]]:
    return route_r_packages(packages)


def conda_packages_for_r(packages: list[str]) -> list[str]:
    return resolve_r_packages(packages)["conda_packages"]


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
    return route_cli_executables(executables)["conda_packages"]


def workflow_engine_packages(engines: list[dict[str, Any]]) -> list[str]:
    packages: list[str] = []
    for item in engines:
        engine = str(item.get("engine") or "").lower()
        if engine in CLI_CONDA_PACKAGES:
            packages.append(CLI_CONDA_PACKAGES[engine])
        elif engine in {"cwl", "wdl"}:
            packages.append(engine)
    return sorted(dict.fromkeys(packages))


def has_trusted_full_conda_lock(lock_trust: dict[str, Any]) -> bool:
    return any(item.get("scope") == "full_conda_environment" and item.get("trusted") is True for item in lock_trust.get("trusted") or [])


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
    return command


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
    return route_package_key(value)


def installed_package_key(value: Any) -> str:
    if isinstance(value, dict):
        return package_key(value.get("name") or value.get("package") or value.get("dist") or "")
    return package_key(value)


def subtract_installed(values: list[str], installed: list[Any]) -> list[str]:
    installed_keys = {installed_package_key(item) for item in installed}
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
        key = repr((command.get("command"), command.get("environment")))
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
