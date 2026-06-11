from __future__ import annotations

import re
from typing import Any

from paper2skill.env_rebuilder.routes import route_cli_executables, route_r_packages, safe_executable_name, safe_package_name


MESON_RE = re.compile(r"\bmeson\b|metadata-generation-failed|failed building wheel|subprocess-exited-with-error", re.I)
MISSING_R_RE = re.compile(r"there is no package called ['\"](?P<package>[^'\"]+)['\"]|package ['\"](?P<package2>[^'\"]+)['\"] is not available", re.I)
MISSING_EXEC_RE = re.compile(r"(?P<executable>[A-Za-z0-9_.+-]+): command not found|executable not found: (?P<executable2>[A-Za-z0-9_.+-]+)", re.I)
CUDA_RE = re.compile(r"cuda|cudart|driver version|torch.*compiled|no kernel image|nvidia", re.I)
PYG_RE = re.compile(r"torch_geometric|pyg|flash-attn|flash_attn|xformers", re.I)
PYTHON_VERSION_RE = re.compile(r"requires python (?P<constraint>[^;\n]+)|python_requires", re.I)
PYPI_UNAVAILABLE_RE = re.compile(r"no matching distribution found|could not find a version that satisfies", re.I)
GITHUB_RE = re.compile(r"github|ssl|eof occurred in violation of protocol|connection reset", re.I)


def diagnose_failure(failure: dict[str, Any] | str) -> dict[str, Any]:
    text = failure_text(failure)
    findings: list[dict[str, Any]] = []
    if MESON_RE.search(text):
        findings.append(
            {
                "failure_mode": "python_source_build_failure",
                "severity": "high",
                "repair": "try_conda_forge_binary_first",
                "commands": [["mamba", "install", "-y", "-c", "conda-forge", "<package>"]],
                "notes": ["Common for scipy/h5py/scikit-misc compiled dependencies when pip falls back to source build."],
            }
        )
    for package in missing_r_packages(text):
        routed = route_r_packages([package])
        manual = not routed.get("conda_packages")
        findings.append(
            {
                "failure_mode": "missing_r_package",
                "severity": "high",
                "package": package,
                "repair": "try_bioconda_or_conda_forge_r_package" if not manual else "manual_block_unknown_r_package",
                "commands": [["mamba", "install", "-y", "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", routed["conda_packages"][0]]] if not manual else [],
                "manual_block": manual,
                "repair_patch_type": "additive",
            }
        )
    for executable in missing_executables(text):
        routed_cli = route_cli_executables([executable])
        manual = not routed_cli.get("conda_packages")
        findings.append(
            {
                "failure_mode": "missing_executable",
                "severity": "high",
                "executable": executable,
                "repair": "try_conda_cli_package" if not manual else "manual_block_unknown_executable",
                "commands": [["mamba", "install", "-y", "--strict-channel-priority", "-c", "conda-forge", "-c", "bioconda", routed_cli["conda_packages"][0]]] if not manual else [],
                "manual_block": manual,
                "repair_patch_type": "additive",
            }
        )
    if CUDA_RE.search(text):
        findings.append(
            {
                "failure_mode": "cuda_mismatch",
                "severity": "high",
                "repair": "switch_torch_backend_or_cpu_fallback",
                "commands": [],
                "manual_block": True,
                "notes": ["CUDA driver/profile repair requires explicit reviewed CPU/GPU profile."],
            }
        )
    if PYG_RE.search(text):
        findings.append(
            {
                "failure_mode": "gpu_extension_or_pyg_wheel_failure",
                "severity": "medium",
                "repair": "prefer_official_wheel_or_conda_package_else_manual_block",
                "commands": [],
                "manual_block": True,
                "notes": ["PyG repair requires torch ABI compatibility check."],
            }
        )
    if PYTHON_VERSION_RE.search(text):
        findings.append(
            {
                "failure_mode": "python_version_conflict",
                "severity": "high",
                "repair": "recreate_environment_with_compatible_python",
                "commands": [["uv", "venv", "--python", "<compatible-python>", "<env>"]],
            }
        )
    if PYPI_UNAVAILABLE_RE.search(text):
        findings.append(
            {
                "failure_mode": "pypi_package_unavailable",
                "severity": "medium",
                "repair": "try_git_url_then_local_install",
                "commands": [],
                "manual_block": True,
            }
        )
    if GITHUB_RE.search(text):
        findings.append(
            {
                "failure_mode": "github_network_or_ssl_failure",
                "severity": "medium",
                "repair": "try_git_clone_or_archive_fallback",
                "commands": [],
                "manual_block": True,
            }
        )
    return {
        "status": "repair_plan_available" if findings else "no_known_repair",
        "finding_count": len(findings),
        "findings": findings,
        "manual_block": not findings or all(item.get("manual_block") for item in findings),
    }


def failure_text(failure: dict[str, Any] | str) -> str:
    if isinstance(failure, str):
        return failure
    chunks: list[str] = []
    for key in ["stdout", "stderr", "error", "traceback", "message"]:
        value = failure.get(key) if isinstance(failure, dict) else None
        if value:
            chunks.append(str(value))
    for item in failure.get("execution_results") or [] if isinstance(failure, dict) else []:
        if isinstance(item, dict):
            chunks.extend(str(item.get(key) or "") for key in ["stdout", "stderr"])
    return "\n".join(chunks)


def missing_r_packages(text: str) -> list[str]:
    packages = []
    for match in MISSING_R_RE.finditer(text):
        packages.append(match.group("package") or match.group("package2"))
    return sorted(dict.fromkeys(item for item in packages if item))


def missing_executables(text: str) -> list[str]:
    executables = []
    for match in MISSING_EXEC_RE.finditer(text):
        value = match.group("executable") or match.group("executable2")
        if value and safe_executable_name(value):
            executables.append(value)
    return sorted(dict.fromkeys(executables))


def conda_r_name(package: str) -> str:
    if not safe_package_name(package):
        return package
    routed = route_r_packages([package])
    return (routed.get("conda_packages") or [package])[0]
