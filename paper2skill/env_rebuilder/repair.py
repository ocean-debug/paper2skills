from __future__ import annotations

import re
from typing import Any


MESON_RE = re.compile(r"\bmeson\b|metadata-generation-failed|failed building wheel|subprocess-exited-with-error", re.I)
MISSING_R_RE = re.compile(r"there is no package called ['\"](?P<package>[^'\"]+)['\"]|package ['\"](?P<package2>[^'\"]+)['\"] is not available", re.I)
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
        findings.append(
            {
                "failure_mode": "missing_r_package",
                "severity": "high",
                "package": package,
                "repair": "try_bioconda_or_conda_forge_r_package",
                "commands": [["mamba", "install", "-y", "-c", "conda-forge", "-c", "bioconda", conda_r_name(package)]],
            }
        )
    if CUDA_RE.search(text):
        findings.append(
            {
                "failure_mode": "cuda_mismatch",
                "severity": "high",
                "repair": "switch_torch_backend_or_cpu_fallback",
                "commands": [
                    ["uv", "pip", "install", "torch", "--torch-backend=auto"],
                    ["env", "UV_TORCH_BACKEND=cpu", "uv", "pip", "install", "torch"],
                ],
            }
        )
    if PYG_RE.search(text):
        findings.append(
            {
                "failure_mode": "gpu_extension_or_pyg_wheel_failure",
                "severity": "medium",
                "repair": "prefer_official_wheel_or_conda_package_else_manual_block",
                "commands": [["uv", "pip", "install", "<official-wheel-url-or-package>"], ["mamba", "install", "-y", "-c", "pyg", "-c", "conda-forge", "pyg"]],
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
                "commands": [["uv", "pip", "install", "git+<official-repo-url>"], ["uv", "pip", "install", "."]],
            }
        )
    if GITHUB_RE.search(text):
        findings.append(
            {
                "failure_mode": "github_network_or_ssl_failure",
                "severity": "medium",
                "repair": "try_git_clone_or_archive_fallback",
                "commands": [["git", "clone", "<official-repo-url>"], ["python", "-m", "paper2skill.collectors.github_archive_fallback"]],
            }
        )
    return {
        "status": "repair_plan_available" if findings else "no_known_repair",
        "finding_count": len(findings),
        "findings": findings,
        "manual_block": not findings,
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


def conda_r_name(package: str) -> str:
    lowered = package.lower()
    bioc = {"deseq2": "bioconductor-deseq2", "apeglm": "bioconductor-apeglm", "sparsematrixstats": "bioconductor-sparsematrixstats"}
    return bioc.get(lowered, f"r-{lowered}")
