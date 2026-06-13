from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

DEFAULT_BIOCONDA_CHANNELS = ["conda-forge", "bioconda"]
STRICT_CHANNEL_PRIORITY_ARG = "--strict-channel-priority"

SAFE_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.:/@+!=<>,~\[\]-]+$")
SAFE_REQUIREMENT_RE = re.compile(r"^[A-Za-z0-9_.:/@+!=<>,~\[\]'\"; -]+$")
SAFE_EXECUTABLE_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
URL_SCHEMES = {"http", "https", "file", "ftp"}
VCS_PREFIXES = ("git+", "hg+", "svn+", "bzr+")

BIOCONDA_R_PREFIX = {
    "deseq2": "bioconductor-deseq2",
    "apeglm": "bioconductor-apeglm",
    "biobase": "bioconductor-biobase",
    "biocgenerics": "bioconductor-biocgenerics",
    "singlecellexperiment": "bioconductor-singlecellexperiment",
    "summarizedexperiment": "bioconductor-summarizedexperiment",
    "sparsematrixstats": "bioconductor-sparsematrixstats",
}
CRAN_CONDA_PACKAGES = {
    "dplyr",
    "ggplot2",
    "ggrepel",
    "glmnet",
    "lmtest",
    "magrittr",
    "matrix",
    "pals",
    "parsnip",
    "pbmcapply",
    "purrr",
    "randomforest",
    "recipes",
    "rdpack",
    "remotes",
    "rlang",
    "rsample",
    "scales",
    "tester",
    "tibble",
    "tidyr",
    "tidyselect",
    "viridis",
    "yardstick",
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
    "adjusttext",
    "anndata",
    "faiss-cpu",
    "h5py",
    "importlib-metadata",
    "matplotlib",
    "networkx",
    "numpy",
    "pandas",
    "requests",
    "rich",
    "scanpy",
    "scikit-misc",
    "scipy",
    "seaborn",
    "sklearn",
    "scikit-learn",
    "tqdm",
    "typing-extensions",
    "wandb",
}
PIP_FIRST_PYTHON = {
    "scvi-tools",
}
PIP_FIRST_CONDA_PREREQUISITES = {
    "scvi-tools": ["tensorstore"],
}
PIP_FIRST_EXTRA_CONSTRAINTS = {
    "scvi-tools": [
        "jax<0.4.24,>=0.4.18",
        "jaxlib<0.4.24,>=0.4.18",
        "ml-dtypes<0.3,>=0.2.0",
        "flax<0.7.1,>=0.6.11",
        "optax<0.2",
        "chex<0.1.8",
        "numpyro<0.13",
        "scipy<1.13",
        "pandas<2",
    ],
}
SPECIAL_TORCH_PACKAGES = {"torch", "pytorch", "torchvision", "torchaudio"}
TORCH_CONDA_PACKAGE_BY_KEY = {
    "torch": "pytorch",
    "pytorch": "pytorch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
}
TORCH_PIP_PACKAGE_BY_KEY = {
    "torch": "torch",
    "pytorch": "torch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
}
SPECIAL_PYG_PACKAGES = {"torch-geometric", "torch_geometric", "pyg"}
PYG_PIP_PACKAGE_BY_KEY = {
    "torch-geometric": "torch-geometric",
    "torch_geometric": "torch-geometric",
    "pyg": "torch-geometric",
}


def normalize_install_approval(install_approval: dict[str, Any] | None = None, install_allowlist: dict[str, Any] | None = None) -> dict[str, Any]:
    sources = [source for source in [install_approval, install_allowlist] if isinstance(source, dict)]
    approval_source = None
    reason = None
    direct_urls: list[dict[str, Any]] = []
    vcs_urls: list[dict[str, Any]] = []
    for source in sources:
        approval_source = source.get("approval_source") or source.get("source") or approval_source
        reason = source.get("reason") or reason
        direct_urls.extend(approved_url_records(source.get("python_direct_urls"), approval_source=approval_source, reason=source.get("reason")))
        vcs_urls.extend(approved_url_records(source.get("python_vcs_urls"), approval_source=approval_source, reason=source.get("reason")))
    return {
        "python_direct_urls": dedupe_url_records(direct_urls),
        "python_vcs_urls": dedupe_url_records(vcs_urls),
        "approval_source": approval_source,
        "reason": reason,
    }


def approved_url_records(values: Any, *, approval_source: Any = None, reason: Any = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in values or []:
        if isinstance(item, str):
            records.append({"url": item, "approval_source": approval_source, "reason": reason})
        elif isinstance(item, dict) and item.get("url"):
            record = dict(item)
            record.setdefault("approval_source", approval_source)
            record.setdefault("reason", reason)
            records.append(record)
    return records


def dedupe_url_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = (str(record.get("url") or ""), str(record.get("approval_source") or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def approved_url_requirement(parsed: dict[str, Any], approval: dict[str, Any] | None) -> dict[str, Any] | None:
    approval = normalize_install_approval(approval)
    requirement_type = str(parsed.get("direct_url_type") or "direct_url_requirement")
    url = str(parsed.get("url") or parsed.get("raw") or "")
    candidates = approval["python_vcs_urls"] if requirement_type == "vcs_requirement" else approval["python_direct_urls"]
    for record in candidates:
        if str(record.get("url") or "") == url:
            return {
                "url": url,
                "type": requirement_type,
                "approval_source": record.get("approval_source") or approval.get("approval_source"),
                "reason": record.get("reason") or approval.get("reason"),
                "hashes": record.get("hashes") or record.get("hash"),
            }
    return None


def package_key(value: Any) -> str:
    parsed = parse_python_requirement(value)
    if parsed.get("name"):
        return str(canonicalize_name(str(parsed["name"])))
    return str(canonicalize_name(re.split(r"[<>=!~ ;\[]", str(value), maxsplit=1)[0].strip()))


def safe_package_name(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and SAFE_PACKAGE_RE.match(text))


def safe_python_requirement(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and SAFE_REQUIREMENT_RE.match(text))


def parse_python_requirement(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {"raw": text, "valid": False, "reason": "empty_requirement"}
    direct = direct_url_requirement_type(text)
    if direct:
        return {"raw": text, "valid": False, "direct_url_type": direct}
    try:
        requirement = Requirement(text)
    except InvalidRequirement:
        return {"raw": text, "valid": False, "reason": "invalid_requirement"}
    if requirement.url:
        return {
            "raw": text,
            "valid": True,
            "name": requirement.name,
            "url": requirement.url,
            "direct_url_type": direct_url_requirement_type(requirement.url) or "direct_url_requirement",
        }
    return {
        "raw": text,
        "valid": True,
        "name": requirement.name,
        "specifier": str(requirement.specifier),
        "marker": str(requirement.marker) if requirement.marker else None,
        "extras": sorted(requirement.extras),
    }


def direct_url_requirement_type(value: str) -> str | None:
    lowered = value.strip().lower()
    if lowered.startswith(VCS_PREFIXES):
        return "vcs_requirement"
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    if scheme in URL_SCHEMES:
        return "direct_url_requirement"
    if "+" in scheme and scheme.split("+", 1)[0] in {"git", "hg", "svn", "bzr"}:
        return "vcs_requirement"
    return None


def manual_url_requirement(parsed: dict[str, Any]) -> dict[str, Any]:
    requirement_type = str(parsed.get("direct_url_type") or "direct_url_requirement")
    reason = "VCS Python requirement requires explicit approval" if requirement_type == "vcs_requirement" else "Direct URL Python requirement requires explicit approval"
    return {
        "name": parsed.get("name") or parsed.get("raw"),
        "requirement": parsed.get("raw"),
        "route": "manual",
        "type": requirement_type,
        "manual_approval_required": True,
        "reason": reason,
    }


def approved_url_route(parsed: dict[str, Any], approval_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": parsed.get("name") or parsed.get("raw"),
        "requirement": parsed.get("raw"),
        "url": approval_record.get("url"),
        "route": "uv",
        "type": approval_record.get("type"),
        "approval_source": approval_record.get("approval_source"),
        "reason": approval_record.get("reason"),
        "hashes": approval_record.get("hashes"),
    }


def conda_requirement_spec(parsed: dict[str, Any]) -> str:
    name = str(canonicalize_name(str(parsed.get("name") or "").strip()))
    specifier = str(parsed.get("specifier") or "").strip()
    return f"{name}{specifier}" if specifier else name


def safe_executable_name(value: Any) -> bool:
    name = Path(str(value or "")).name
    return bool(name and SAFE_EXECUTABLE_RE.match(name))


def normalize_channels(channels: list[Any] | None) -> tuple[list[str], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    normalized: list[str] = []
    for channel in channels or []:
        value = str(channel).strip()
        if not value:
            continue
        if value == "defaults":
            warnings.append({"type": "channel_demoted", "channel": value, "reason": "defaults is not preferred for bioconda environments"})
            continue
        if value not in normalized:
            normalized.append(value)
    for required in DEFAULT_BIOCONDA_CHANNELS:
        if required not in normalized:
            normalized.append(required)
            warnings.append({"type": "channel_added", "channel": required, "reason": "bioconda stack requires explicit conda-forge/bioconda channels"})
    ordered = [channel for channel in DEFAULT_BIOCONDA_CHANNELS if channel in normalized]
    ordered.extend(channel for channel in normalized if channel not in ordered)
    return ordered, warnings


def channel_args(channels: list[str]) -> list[str]:
    args = [STRICT_CHANNEL_PRIORITY_ARG]
    for channel in channels:
        args.extend(["-c", channel])
    return args


def route_python_packages(
    packages: list[str],
    *,
    gpu_policy: str = "optional",
    torch_backend: str = "auto",
    install_approval: dict[str, Any] | None = None,
    install_allowlist: dict[str, Any] | None = None,
) -> dict[str, Any]:
    approval = normalize_install_approval(install_approval, install_allowlist)
    conda: list[str] = []
    uv: list[str] = []
    special: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    migrations: list[dict[str, Any]] = []
    approved_urls: list[dict[str, Any]] = []
    for package in packages:
        direct = direct_url_requirement_type(str(package or ""))
        if direct:
            parsed = {"raw": str(package), "url": str(package), "direct_url_type": direct}
            approval_record = approved_url_requirement(parsed, approval)
            if approval_record:
                uv.append(str(package))
                approved_urls.append(approved_url_route(parsed, approval_record))
            else:
                manual.append(manual_url_requirement(parsed))
            continue
        parsed = parse_python_requirement(package)
        if parsed.get("direct_url_type"):
            approval_record = approved_url_requirement(parsed, approval)
            if approval_record:
                uv.append(str(package))
                approved_urls.append(approved_url_route(parsed, approval_record))
            else:
                manual.append(manual_url_requirement(parsed))
            continue
        if not safe_python_requirement(package):
            manual.append({"name": str(package), "reason": "unsafe_package_name"})
            continue
        if not parsed.get("valid"):
            manual.append({"name": str(package), "reason": parsed.get("reason") or "invalid_requirement"})
            continue
        key = package_key(package)
        if not safe_package_name(key):
            manual.append({"name": str(package), "reason": "unsafe_package_name"})
            continue
        if key in SPECIAL_TORCH_PACKAGES:
            route = torch_route(conda_requirement_spec(parsed), gpu_policy=gpu_policy, torch_backend=torch_backend)
            route["requirement"] = str(package)
            if parsed.get("marker") or parsed.get("extras"):
                route["normalization"] = {"marker": parsed.get("marker"), "extras": parsed.get("extras") or []}
            special.append(route)
            if route.get("manual_approval_required"):
                manual.append(route)
            continue
        if key in SPECIAL_PYG_PACKAGES:
            route = {
                "name": pyg_pip_requirement(parsed),
                "requirement": str(package),
                "route": "special_pyg",
                "profile": "pip_default",
                "pip_packages": [pyg_pip_requirement(parsed)],
                "manual_approval_required": False,
                "reason": "torch-geometric is installed in the pip segment and verified by preflight to avoid fragile conda ABI solves",
            }
            if parsed.get("marker") or parsed.get("extras"):
                route["normalization"] = {"marker": parsed.get("marker"), "extras": parsed.get("extras") or []}
            special.append(route)
            continue
        if key in PIP_FIRST_PYTHON:
            pip_spec = conda_requirement_spec(parsed)
            uv.append(pip_spec)
            extra_constraints = pip_first_extra_constraints(key, parsed)
            uv.extend(extra_constraints)
            prerequisites = pip_first_conda_prerequisites(key, parsed)
            for prerequisite in prerequisites:
                conda.append(prerequisite)
            migrations.append(
                {
                    "package": pip_spec,
                    "requirement": str(package),
                    "evidence": "pip_first_python_stack",
                    "chosen_route": "pip",
                    "reason": "package is pip-native and causes slow or fragile conda solves in mixed deep-learning environments",
                    "source": "route_table",
                    "patch_type": "route_migration",
                    "dropped_marker": parsed.get("marker"),
                    "dropped_extras": parsed.get("extras") or [],
                }
            )
            for prerequisite in prerequisites:
                migrations.append(
                    {
                        "package": prerequisite,
                        "requirement": str(package),
                        "evidence": "pip_first_transitive_prerequisite",
                        "chosen_route": "conda",
                        "reason": "pip source build requires newer system toolchain; preinstall conda binary before pip package resolution",
                        "source": "route_table",
                        "patch_type": "transitive_prerequisite",
                        "dropped_marker": None,
                        "dropped_extras": [],
                    }
                )
            for constraint in extra_constraints:
                migrations.append(
                    {
                        "package": constraint,
                        "requirement": str(package),
                        "evidence": "pip_first_transitive_constraint",
                        "chosen_route": "pip",
                        "reason": "legacy dependency stack needs a bounded transitive dependency to avoid source builds on old system toolchains",
                        "source": "route_table",
                        "patch_type": "transitive_constraint",
                        "dropped_marker": None,
                        "dropped_extras": [],
                    }
                )
            continue
        if key in CONDA_BINARY_PYTHON:
            conda_spec = conda_requirement_spec(parsed)
            conda.append(conda_spec)
            migrations.append(
                {
                    "package": conda_spec,
                    "requirement": str(package),
                    "evidence": "known_compiled_python_stack",
                    "chosen_route": "conda",
                    "reason": "compiled scientific package should be solved before pip/uv",
                    "source": "route_table",
                    "patch_type": "route_migration",
                    "dropped_marker": parsed.get("marker"),
                    "dropped_extras": parsed.get("extras") or [],
                }
            )
        else:
            uv.append(package)
    return {
        "conda": sorted(dict.fromkeys(conda)),
        "uv": sorted(dict.fromkeys(uv)),
        "special": special,
        "manual": manual,
        "migrations": migrations,
        "approved_urls": approved_urls,
    }


def torch_route(package: str, *, gpu_policy: str, torch_backend: str) -> dict[str, Any]:
    key = package_key(package)
    conda_package = TORCH_CONDA_PACKAGE_BY_KEY.get(key, "pytorch")
    conda_packages = [conda_package]
    if "pytorch" not in conda_packages:
        conda_packages.insert(0, "pytorch")
    conda_packages.append("cpuonly")
    if gpu_policy == "required" and not torch_backend.startswith("cu"):
        return {
            "name": package,
            "route": "special_torch",
            "profile": "gpu_requires_explicit_cuda_profile",
            "manual_approval_required": True,
            "reason": "GPU torch install requires explicit CUDA profile",
        }
    if torch_backend.startswith("cu"):
        return {
            "name": package,
            "route": "special_torch",
            "profile": "explicit_cuda",
            "torch_backend": torch_backend,
            "manual_approval_required": True,
            "reason": "CUDA wheel/conda profile requires reviewed ABI and driver compatibility",
        }
    if torch_backend in {"conda", "conda_cpu"}:
        return {
            "name": package,
            "route": "special_torch",
            "profile": "conda_cpu",
            "conda_packages": conda_packages,
            "channels": ["pytorch", "conda-forge"],
            "manual_approval_required": False,
            "reason": "explicit conda CPU torch profile was requested",
        }
    return {
        "name": package,
        "route": "special_torch",
        "profile": "pip_cpu",
        "pip_packages": [torch_pip_requirement(package)],
        "manual_approval_required": False,
        "reason": "default CPU torch route uses pip wheels to avoid slow conda solves on mixed scientific stacks",
    }


def torch_pip_requirement(package: str) -> str:
    parsed = parse_python_requirement(package)
    key = package_key(package)
    name = TORCH_PIP_PACKAGE_BY_KEY.get(key, key)
    specifier = str(parsed.get("specifier") or "").strip() if parsed.get("valid") else ""
    return f"{name}{specifier}" if specifier else name


def pyg_pip_requirement(parsed: dict[str, Any]) -> str:
    key = package_key(parsed.get("raw") or parsed.get("name") or "")
    name = PYG_PIP_PACKAGE_BY_KEY.get(key, "torch-geometric")
    specifier = str(parsed.get("specifier") or "").strip()
    return f"{name}{specifier}" if specifier else name


def pip_first_conda_prerequisites(key: str, parsed: dict[str, Any]) -> list[str]:
    specifier = str(parsed.get("specifier") or "")
    if key == "scvi-tools" and "<1" in specifier.replace(" ", ""):
        return []
    return list(PIP_FIRST_CONDA_PREREQUISITES.get(key, []))


def pip_first_extra_constraints(key: str, parsed: dict[str, Any]) -> list[str]:
    specifier = str(parsed.get("specifier") or "")
    if key == "scvi-tools" and "<1" in specifier.replace(" ", ""):
        return list(PIP_FIRST_EXTRA_CONSTRAINTS.get(key, []))
    return []


def route_r_packages(packages: list[str]) -> dict[str, Any]:
    conda: list[str] = []
    manual: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    for package in packages:
        name = re.split(r"[<>=!~ ]", str(package), maxsplit=1)[0].strip()
        if not name:
            continue
        if not safe_package_name(name):
            manual.append({"name": str(package), "class": "unknown", "reason": "unsafe_package_name"})
            continue
        lowered = name.lower()
        if lowered in R_BASE_PACKAGES:
            routes.append({"name": name, "class": "base", "chosen_route": "base", "package": None})
            continue
        if lowered in BIOCONDA_R_PREFIX:
            conda_name = BIOCONDA_R_PREFIX[lowered]
            conda.append(conda_name)
            routes.append({"name": name, "class": "bioconductor", "chosen_route": "bioconda", "package": conda_name})
            continue
        if lowered.startswith("bioconductor-") or lowered.startswith("r-"):
            conda.append(name)
            routes.append({"name": name, "class": "conda_named", "chosen_route": "conda", "package": name})
            continue
        if lowered in CRAN_CONDA_PACKAGES:
            conda_name = f"r-{lowered}"
            conda.append(conda_name)
            routes.append({"name": name, "class": "cran", "chosen_route": "conda-forge", "package": conda_name})
            continue
        manual.append({"name": name, "class": "unknown", "reason": "no_known_conda_or_bioconda_route"})
    return {"conda_packages": sorted(dict.fromkeys(conda)), "manual_packages": [item["name"] for item in manual], "routes": routes, "manual": manual}


def route_cli_executables(executables: list[str]) -> dict[str, Any]:
    conda: list[str] = []
    manual: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    for executable in executables:
        name = Path(str(executable)).name.lower()
        if not safe_executable_name(name):
            manual.append({"name": str(executable), "reason": "unsafe_executable_name"})
            continue
        package = CLI_CONDA_PACKAGES.get(name)
        if package:
            conda.append(package)
            routes.append({"name": name, "chosen_route": "conda", "package": package})
        else:
            manual.append({"name": name, "reason": "no_known_cli_route"})
    return {"conda_packages": sorted(dict.fromkeys(conda)), "manual": manual, "routes": routes}
