from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from paper2skill.env_rebuilder.routes import (
    approved_url_requirement,
    direct_url_requirement_type,
    manual_url_requirement,
    normalize_channels,
    parse_python_requirement,
    route_cli_executables,
    route_python_packages,
    route_r_packages,
    safe_python_requirement,
)

CANONICAL_ENV_RELATIVE_PATH = "assets/env/paper2skill.environment.yml"
SUPPORTED_LOCK_PLATFORMS = {"linux-64", "noarch"}


def trust_lockfiles(scan: dict[str, Any], *, platform: str = "linux-64", r_mode: str = "conda", allow_renv: bool = False) -> dict[str, Any]:
    trusted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in scan.get("lockfiles") or []:
        name = str(item.get("name") or "")
        if name.startswith("conda-lock"):
            record = trust_conda_lock(item, platform=platform)
        elif name == "uv.lock":
            record = {**item, "trusted": True, "scope": "pip_uv_segment", "reason": "uv.lock constrains only pip/uv segment"}
        elif name == "renv.lock":
            trusted_renv = r_mode == "renv" and allow_renv
            record = {
                **item,
                "trusted": trusted_renv,
                "scope": "r_renv_segment",
                "reason": "renv restore requires r_mode=renv and explicit case gold approval" if not trusted_renv else "renv explicitly allowed",
            }
        else:
            record = {**item, "trusted": False, "scope": "unknown", "reason": "unsupported lockfile type"}
        if record.get("trusted") and not lockfile_path_safe(record):
            record = {
                **record,
                "trusted": False,
                "reason": f"{record.get('reason', '')}; lockfile path is not safe".strip("; "),
            }
        (trusted if record.get("trusted") else blocked).append(record)
    return {"trusted": trusted, "blocked": blocked, "platform": platform, "r_mode": r_mode, "allow_renv": allow_renv}


def trust_conda_lock(item: dict[str, Any], *, platform: str) -> dict[str, Any]:
    platforms = item.get("platforms") or []
    channels = item.get("channels") or []
    trusted = True
    reasons = []
    if item.get("lock_parse_status") != "parsed":
        trusted = False
        reasons.append("conda-lock metadata could not be parsed")
    if not lockfile_path_safe(item):
        trusted = False
        reasons.append("conda-lock path is not a safe repository-relative path")
    if not platforms:
        trusted = False
        reasons.append("conda-lock platforms could not be verified")
    if platforms and platform not in platforms:
        trusted = False
        reasons.append(f"platform {platform} not in lockfile platforms")
    if any(item not in SUPPORTED_LOCK_PLATFORMS for item in platforms):
        reasons.append("conda-lock includes non-linux/noarch platforms; restore remains platform-scoped")
    if not channels:
        trusted = False
        reasons.append("conda-lock channels could not be verified")
    if channels and not {"conda-forge", "bioconda"}.issubset(set(channels)):
        trusted = False
        reasons.append("conda-lock channels do not include conda-forge and bioconda")
    return {**item, "trusted": trusted, "scope": "full_conda_environment", "reason": "; ".join(reasons) if reasons else "trusted conda-lock full environment"}


def lockfile_path_safe(item: dict[str, Any]) -> bool:
    path = str(item.get("path") or item.get("name") or "")
    if not path:
        return False
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts and "\0" not in path


def derive_canonical_environment(
    scan: dict[str, Any],
    *,
    env_name: str,
    python_version: str,
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    install_approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    upstream = first_environment_file(scan)
    parsed = parse_upstream_environment(upstream, repo=scan.get("repo"))
    upstream_channels = list(parsed.get("channels") or [])
    dependencies = list(parsed.get("conda_dependencies") or [])
    pip_dependencies = list(parsed.get("pip_dependencies") or [])
    report: dict[str, Any] = {
        "status": "derived",
        "upstream": upstream,
        "canonical_path": CANONICAL_ENV_RELATIVE_PATH,
        "channel_changes": [],
        "route_migrations": [],
        "additive_dependencies": [],
        "conflicts": [],
        "retained_upstream_dependencies": list(dependencies),
        "retained_upstream_pip_dependencies": list(pip_dependencies),
    }
    report["conflicts"].extend(version_conflicts(dependencies, python_version))
    py_routes = route_python_packages(pip_dependencies + setup_python_dependencies(scan), gpu_policy=gpu_policy, torch_backend=torch_backend, install_approval=install_approval)
    generated_pip_routes = route_generated_pip_segment(generated_skill_pip_segment(scan), install_approval=install_approval)
    dependencies.extend(py_routes["conda"])
    dependencies.extend(str(item) for item in scan.get("generated_requirements_conda_segment") or [])
    special_pip_segment: list[str] = []
    for route in py_routes["special"]:
        if route.get("manual_approval_required"):
            continue
        dependencies.extend(str(item) for item in route.get("conda_packages") or [])
        special_pip_segment.extend(str(item) for item in route.get("pip_packages") or [])
        upstream_channels.extend(str(item) for item in route.get("channels") or [])
    report["route_migrations"].extend(migration_with_source(item, "upstream_pip_or_python_metadata") for item in py_routes["migrations"])
    report["route_migrations"].extend(migration_with_source(item, "generated_skill_requirements") for item in scan.get("generated_requirements_route_migrations") or [])
    pip_segment = [*py_routes["uv"], *generated_pip_routes["uv"], *special_pip_segment]
    r_routes = route_r_packages(r_dependencies(scan))
    dependencies.extend(r_routes["conda_packages"])
    report["additive_dependencies"].extend(additive_records(r_routes["routes"], source="r_dependency_evidence"))
    cli_routes = route_cli_executables(cli_dependencies(scan))
    dependencies.extend(cli_routes["conda_packages"])
    report["additive_dependencies"].extend(additive_records(cli_routes["routes"], source="cli_or_workflow_evidence"))
    channels, channel_notes = normalize_channels(upstream_channels)
    report["channel_changes"] = channel_notes
    dependencies = canonical_dependencies(dependencies, python_version=python_version, include_uv=True)
    report["channel_priority"] = "strict"
    env = {"name": env_name, "channels": channels, "dependencies": dependencies}
    report["pip_segment"] = sorted(dict.fromkeys(pip_segment))
    if scan.get("pip_segment_sources"):
        report["pip_segment_sources"] = scan.get("pip_segment_sources")
    report["manual_blocks"] = [*py_routes["manual"], *generated_pip_routes["manual"], *(scan.get("generated_requirements_manual_blocks") or []), *r_routes["manual"], *cli_routes["manual"]]
    report["special_routes"] = py_routes["special"]
    return {"environment": env, "report": report}


def first_environment_file(scan: dict[str, Any]) -> dict[str, Any] | None:
    for item in scan.get("environment_files") or []:
        if item.get("name") in {"environment.yml", "environment.yaml"}:
            return item
    return None


def parse_upstream_environment(item: dict[str, Any] | None, *, repo: Any = None) -> dict[str, Any]:
    if not item:
        return {"channels": [], "conda_dependencies": [], "pip_dependencies": []}
    path = Path(str(item.get("path") or ""))
    if not path.is_absolute() and repo:
        path = Path(str(repo)) / path
    data: dict[str, Any] = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    conda_deps: list[str] = []
    pip_deps: list[str] = []
    for dep in data.get("dependencies") or []:
        if isinstance(dep, str):
            conda_deps.append(dep)
        elif isinstance(dep, dict) and isinstance(dep.get("pip"), list):
            pip_deps.extend(str(value) for value in dep.get("pip") or [])
    return {"channels": list(data.get("channels") or []), "conda_dependencies": conda_deps, "pip_dependencies": pip_deps}


def setup_python_dependencies(scan: dict[str, Any]) -> list[str]:
    python = scan.get("python") or {}
    deps: list[str] = []
    for item in python.get("setup_cfg_install_requires") or []:
        deps.append(str(item))
    project_name = python.get("project_name")
    if project_name:
        deps.append(str(project_name))
    return deps


def generated_skill_pip_segment(scan: dict[str, Any]) -> list[str]:
    return [str(item) for item in scan.get("pip_segment") or []]


def route_generated_pip_segment(packages: list[str], *, install_approval: dict[str, Any] | None) -> dict[str, Any]:
    uv: list[str] = []
    manual: list[dict[str, Any]] = []
    for package in packages:
        direct = direct_url_requirement_type(str(package or ""))
        parsed = {"raw": str(package), "url": str(package), "direct_url_type": direct} if direct else parse_python_requirement(package)
        if parsed.get("direct_url_type"):
            if approved_url_requirement(parsed, install_approval):
                uv.append(str(package))
            else:
                manual.append(manual_url_requirement(parsed))
            continue
        if not parsed.get("valid") or not safe_python_requirement(package):
            manual.append({"name": str(package), "reason": parsed.get("reason") or "unsafe_package_name"})
            continue
        uv.append(str(package))
    return {"uv": sorted(dict.fromkeys(uv)), "manual": manual}


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


def canonical_dependencies(dependencies: list[str], *, python_version: str, include_uv: bool) -> list[Any]:
    cleaned: list[str] = []
    saw_python = False
    saw_pip = False
    saw_uv = False
    for dep in dependencies:
        value = str(dep).strip()
        if not value:
            continue
        key = re.split(r"[=<>!~ ]", value, maxsplit=1)[0].lower()
        if key == "python":
            saw_python = True
            cleaned.append(value)
        elif key == "pip":
            saw_pip = True
            cleaned.append("pip")
        elif key == "uv":
            saw_uv = True
            cleaned.append("uv")
        else:
            cleaned.append(value)
    if not saw_python:
        cleaned.insert(0, f"python={python_version}")
    if not saw_pip:
        cleaned.append("pip")
    if include_uv and not saw_uv:
        cleaned.append("uv")
    return sorted(dict.fromkeys(cleaned), key=dependency_sort_key)


def dependency_sort_key(value: Any) -> tuple[int, str]:
    text = str(value)
    if text.startswith("python"):
        return (0, text)
    if text == "pip":
        return (1, text)
    if text == "uv":
        return (2, text)
    if text.startswith("r-base"):
        return (3, text)
    return (4, text)


def version_conflicts(dependencies: list[str], selected_python: str) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for dep in dependencies:
        lowered = dep.lower()
        if lowered.startswith("python="):
            version = dep.split("=", 1)[1].strip()
            if version and not version.startswith(selected_python):
                conflicts.append(
                    {
                        "type": "python_version_conflict",
                        "upstream": dep,
                        "selected": f"python={selected_python}",
                        "action": "record_only",
                        "reason": "do not silently upgrade upstream Python version",
                    }
                )
        if lowered.startswith("r-base="):
            conflicts.append({"type": "r_version_pinned_upstream", "upstream": dep, "action": "record_only", "reason": "R pin is preserved as upstream evidence"})
    return conflicts


def migration_with_source(record: dict[str, Any], source: str) -> dict[str, Any]:
    updated = dict(record)
    updated.setdefault("source", source)
    return updated


def additive_records(routes: list[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
    records = []
    for route in routes:
        if route.get("package"):
            records.append(
                {
                    "package": route["package"],
                    "evidence": route.get("name"),
                    "chosen_route": route.get("chosen_route"),
                    "reason": "dependency required by scanned project evidence",
                    "source": source,
                    "patch_type": "additive",
                }
            )
    return records
