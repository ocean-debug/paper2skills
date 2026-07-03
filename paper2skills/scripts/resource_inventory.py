"""Mine model, checkpoint, and external data resource boundaries."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


MAX_RESOURCE_SCAN_BYTES = 250_000
RESOURCE_SUFFIXES = {".md", ".rst", ".txt", ".py", ".r", ".ipynb", ".html", ".htm", ".yaml", ".yml", ".toml", ".json"}
MODEL_LOAD_CALLS = {
    "from_pretrained",
    "load_state_dict",
    "torch.load",
    "load_model",
    "load_weights",
    "snapshot_download",
    "hf_hub_download",
}

HF_MODEL_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?![A-Za-z0-9_.-])")
URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
CHECKPOINT_RE = re.compile(r"\b([A-Za-z0-9_.-]+\.(?:pt|pth|ckpt|safetensors|h5|hdf5|onnx|pkl|joblib|npz))\b", re.IGNORECASE)
DATA_RE = re.compile(r"\b([A-Za-z0-9_.-]+\.(?:h5ad|loom|mtx|csv|tsv|parquet|rds|rda|zip|tar|gz))\b", re.IGNORECASE)


def read_small_text(path: Path) -> str:
    if path.stat().st_size > MAX_RESOURCE_SCAN_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except UnicodeDecodeError:
            return ""


def classify_url(url: str) -> str:
    lowered = url.lower()
    if "huggingface.co" in lowered:
        return "model_registry_url"
    if any(token in lowered for token in ["/releases/download/", "zenodo", "figshare", "drive.google", "dropbox"]):
        return "external_download_url"
    if any(lowered.endswith(suffix) for suffix in [".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5", ".h5ad", ".zip"]):
        return "external_artifact_url"
    return "external_url"


def resource_record(
    resource_type: str,
    identifier: str,
    source_record: dict[str, Any],
    evidence: str,
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "identifier": identifier,
        "source_path": source_record.get("relative_path"),
        "source_evidence_id": source_record.get("evidence_id"),
        "evidence": evidence,
        "risk_flags": sorted(set(risk_flags or [])),
    }


def risk_flags(identifier: str, text: str, resource_type: str) -> list[str]:
    lowered = f"{identifier}\n{text}".lower()
    flags = []
    if any(token in lowered for token in ["login", "token", "gated", "access request", "license", "terms of use"]):
        flags.append("permission_or_license_required")
    if resource_type in {"checkpoint_file", "model_registry_id", "model_registry_url"}:
        flags.append("model_weight_dependency")
    if resource_type.startswith("external"):
        flags.append("external_download_dependency")
    if any(token in lowered for token in ["large", "gb", "download", "snapshot"]):
        flags.append("large_or_implicit_download")
    return flags


def scan_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    path_value = record.get("path")
    if not path_value:
        return []
    path = Path(str(path_value))
    if not path.exists() or not path.is_file() or path.suffix.lower() not in RESOURCE_SUFFIXES:
        return []
    text = read_small_text(path)
    if not text:
        return []

    resources = []
    for match in URL_RE.findall(text):
        resource_type = classify_url(match)
        resources.append(resource_record(resource_type, match, record, "url_pattern", risk_flags(match, text, resource_type)))
    for match in HF_MODEL_RE.findall(text):
        if "." in match.split("/", 1)[0]:
            continue
        resources.append(resource_record("model_registry_id", match, record, "registry_id_pattern", risk_flags(match, text, "model_registry_id")))
    for match in CHECKPOINT_RE.findall(text):
        resources.append(resource_record("checkpoint_file", match, record, "checkpoint_suffix", risk_flags(match, text, "checkpoint_file")))
    for match in DATA_RE.findall(text):
        resources.append(resource_record("data_artifact", match, record, "data_suffix", risk_flags(match, text, "data_artifact")))
    for call in record.get("api_calls", []):
        if str(call).split(".")[-1] in MODEL_LOAD_CALLS or str(call) in MODEL_LOAD_CALLS:
            resources.append(resource_record("model_load_api", str(call), record, "parsed_api_call", risk_flags(str(call), text, "model_load_api")))
    return resources


def dedupe(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in resources:
        key = (item.get("resource_type"), item.get("identifier"), item.get("source_path"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_resource_inventory(request: dict[str, Any], source_index: dict[str, Any]) -> dict[str, Any]:
    resources = dedupe([item for record in source_index.get("files", []) for item in scan_record(record)])
    resource_types = sorted({str(item.get("resource_type")) for item in resources})
    risk_counts: dict[str, int] = {}
    for item in resources:
        for flag in item.get("risk_flags", []):
            risk_counts[flag] = risk_counts.get(flag, 0) + 1
    findings: list[dict[str, Any]] = []
    if risk_counts.get("permission_or_license_required"):
        findings.append(
            {
                "severity": "warning",
                "code": "resource_permission_boundary_detected",
                "message": "Some model or data resources appear to require explicit permission, license review, login, or access tokens.",
            }
        )
    if risk_counts.get("large_or_implicit_download"):
        findings.append(
            {
                "severity": "warning",
                "code": "large_or_implicit_download_detected",
                "message": "Some resources may trigger large or implicit downloads and need explicit user approval before execution.",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "pass",
        "resource_count": len(resources),
        "resource_types": resource_types,
        "risk_counts": dict(sorted(risk_counts.items())),
        "resources": resources[:200],
        "findings": findings,
        "policy": [
            "Resource inventory is static and never downloads models, weights, or data.",
            "Detected resources are environment and refusal boundaries, not evidence of availability.",
            "Gated, licensed, token-protected, or large resources require explicit user confirmation before execution.",
        ],
    }
