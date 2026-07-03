"""Discovery for existing Codex child skills."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import as_list, now_utc, read_text
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


STANDARD_DISCOVERY_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    *[f"references/{name}" for name in REQUIRED_CHILD_REFERENCES],
]

IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_url(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"\.git$", "", text.rstrip("/"))
    return text


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9_.]+", "", normalize_text(value))


def extract_task_types(text: str) -> list[str]:
    values = set(re.findall(r"`([a-z][a-z0-9_]+)`", text))
    values.update(re.findall(r"\btask_type\s*[:=]\s*`?([a-z][a-z0-9_]+)`?", text, flags=re.IGNORECASE))
    values.update(re.findall(r"^\s*\|\s*`?([a-z][a-z0-9_]+)`?\s*\|", text, flags=re.MULTILINE))
    return sorted(values)


def extract_api_symbols(text: str) -> list[str]:
    values = set()
    for token in re.findall(r"`([a-zA-Z_][a-zA-Z0-9_.]+)`", text):
        if "." in token or token.endswith(("fit", "train", "predict", "transform", "run")):
            values.add(normalize_identifier(token))
    for token in IDENTIFIER_RE.findall(text):
        if "." in token:
            values.add(normalize_identifier(token))
    return sorted(value for value in values if value)


def extract_backends(text: str) -> list[str]:
    backends = []
    if re.search(r"\bpython\b|pip install|pyproject\.toml|requirements\.txt", text, flags=re.IGNORECASE):
        backends.append("python")
    if re.search(r"\br\b|rscript|renv|description", text, flags=re.IGNORECASE):
        backends.append("r")
    return sorted(set(backends))


def extract_verification_labels(text: str) -> list[str]:
    labels = re.findall(r"\b(source_grounded|execution_verified|execution_failed|unverified)\b", text)
    return sorted(set(labels))


def shape_findings(skill_dir: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not (skill_dir / "SKILL.md").exists():
        findings.append({"severity": "error", "code": "missing_skill_md", "message": "Existing skill is missing SKILL.md."})
    for name in REQUIRED_CHILD_REFERENCES:
        if not (skill_dir / "references" / name).exists():
            findings.append(
                {
                    "severity": "warning",
                    "code": "missing_child_reference",
                    "reference": name,
                    "message": "Existing skill is missing a standard child-skill reference.",
                }
            )
    return findings


def match_level(field_matches: dict[str, Any], task_coverage_ratio: float, confidence: float) -> str:
    if field_matches.get("repo_url"):
        return "exact_repo"
    if field_matches.get("paper_refs"):
        return "paper_reference"
    if field_matches.get("package_name") and task_coverage_ratio > 0:
        return "package_task_overlap"
    if field_matches.get("api_names") and confidence >= 0.35:
        return "api_overlap"
    if field_matches.get("package_name") or field_matches.get("method_name"):
        return "name_overlap"
    return "weak_overlap"


def scan_existing_skill(skill_dir: Path) -> dict[str, Any] | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    chunks = []
    file_records = []
    for rel in STANDARD_DISCOVERY_FILES:
        path = skill_dir / rel
        if path.exists():
            text = read_text(path)
            chunks.append(text)
            file_records.append({"path": rel, "bytes": len(text.encode("utf-8"))})
    text = "\n".join(chunks)
    lower_text = text.lower()
    urls = sorted({normalize_url(match) for match in URL_RE.findall(text)})
    dois = sorted({normalize_text(match) for match in DOI_RE.findall(text)})
    return {
        "path": str(skill_dir),
        "text": lower_text,
        "files_scanned": file_records,
        "repo_urls": urls,
        "paper_refs": dois,
        "task_types": extract_task_types(text),
        "api_symbols": extract_api_symbols(text),
        "backends": extract_backends(text),
        "verification_labels": extract_verification_labels(text),
        "shape_findings": shape_findings(skill_dir),
    }


def discovery(request: dict[str, Any], task_types: list[str], api_names: list[str] | None = None) -> dict[str, Any]:
    package = normalize_text(request.get("package_name"))
    method = normalize_text(request.get("method_name"))
    repo_url = normalize_url(request.get("repo_url"))
    paper_refs = [
        normalize_text(item)
        for item in as_list(request.get("paper_dois")) + as_list(request.get("paper_links"))
        if item
    ]
    requested_api_names = [
        normalize_identifier(item)
        for item in as_list(request.get("api_names")) + as_list(api_names)
        if item
    ]
    requested_tasks = sorted(set(task_types))
    matches = []
    for root_value in as_list(request.get("existing_skills_dirs")):
        root = Path(str(root_value)).expanduser()
        if not root.exists():
            continue
        candidates = [root] if (root / "SKILL.md").exists() else list(root.glob("*/SKILL.md"))
        for candidate in candidates:
            skill_dir = candidate.parent if candidate.name == "SKILL.md" else candidate
            scanned = scan_existing_skill(skill_dir)
            if not scanned:
                continue
            text = scanned["text"]
            score = 0
            score_components = []
            field_matches: dict[str, Any] = {
                "repo_url": False,
                "package_name": False,
                "method_name": False,
                "paper_refs": [],
                "api_names": [],
                "task_types": [],
            }
            normalized_skill_urls = set(scanned.get("repo_urls", []))
            if repo_url and (repo_url in normalized_skill_urls or repo_url in text):
                score += 3
                score_components.append({"field": "repo_url", "weight": 3})
                field_matches["repo_url"] = True
            if package and package in text:
                score += 2
                score_components.append({"field": "package_name", "weight": 2})
                field_matches["package_name"] = True
            if method and method in text:
                score += 1
                score_components.append({"field": "method_name", "weight": 1})
                field_matches["method_name"] = True
            matched_paper_refs = [ref for ref in paper_refs if ref and ref in text]
            if matched_paper_refs:
                weight = min(len(matched_paper_refs), 3)
                score += weight
                score_components.append({"field": "paper_refs", "weight": weight, "matched_count": len(matched_paper_refs)})
                field_matches["paper_refs"] = matched_paper_refs[:10]
            skill_api_symbols = set(scanned.get("api_symbols", []))
            matched_api_names = [
                name for name in requested_api_names
                if name and (name in skill_api_symbols or name in text)
            ]
            if matched_api_names:
                weight = min(len(matched_api_names), 5)
                score += weight
                score_components.append({"field": "api_names", "weight": weight, "matched_count": len(matched_api_names)})
                field_matches["api_names"] = matched_api_names[:20]
            covered = sorted(set(task_types).intersection(scanned["task_types"]))
            if covered:
                score += len(covered)
                score_components.append({"field": "task_types", "weight": len(covered), "matched_count": len(covered)})
                field_matches["task_types"] = covered
            if score:
                task_coverage_ratio = len(set(covered)) / len(requested_tasks) if requested_tasks else 0.0
                confidence = min(
                    1.0,
                    (0.35 if field_matches["repo_url"] else 0.0)
                    + (0.20 if field_matches["package_name"] else 0.0)
                    + (0.10 if field_matches["method_name"] else 0.0)
                    + min(len(matched_paper_refs), 2) * 0.10
                    + min(len(matched_api_names), 5) * 0.04
                    + task_coverage_ratio * 0.20,
                )
                shape_status = "needs_update" if scanned.get("shape_findings") else "pass"
                matches.append(
                    {
                        "path": scanned["path"],
                        "score": score,
                        "match_level": match_level(field_matches, task_coverage_ratio, confidence),
                        "confidence": round(confidence, 3),
                        "field_matches": field_matches,
                        "score_components": score_components,
                        "covered_task_types": covered,
                        "missing_task_types": sorted(set(task_types).difference(covered)),
                        "task_coverage_ratio": round(task_coverage_ratio, 3),
                        "matched_paper_refs": matched_paper_refs[:10],
                        "matched_api_names": matched_api_names[:20],
                        "known_task_types": scanned["task_types"],
                        "known_api_symbols": scanned.get("api_symbols", [])[:50],
                        "known_backends": scanned.get("backends", []),
                        "verification_labels": scanned.get("verification_labels", []),
                        "files_scanned": scanned.get("files_scanned", []),
                        "shape_status": shape_status,
                        "shape_findings": scanned.get("shape_findings", []),
                    }
                )
    matches.sort(key=lambda item: (item["confidence"], item["score"]), reverse=True)
    if not matches:
        decision = "create"
        reason = "No matching Codex child skill was found."
    else:
        best = matches[0]
        missing = sorted(set(task_types).difference(best["covered_task_types"]))
        if missing:
            decision = "update"
            reason = "A related skill exists but does not cover all requested or inferred task_type entries."
        elif best.get("shape_status") != "pass":
            decision = "update"
            reason = "A related skill exists but needs structural updates before reuse."
        else:
            decision = "reuse"
            reason = "An existing skill appears to cover the package and task_type entries."
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "target_agent": "codex",
        "decision": decision,
        "reason": reason,
        "matches": matches,
        "checked_existing_skill_dirs": as_list(request.get("existing_skills_dirs")),
        "requested_or_inferred_task_types": requested_tasks,
        "matching_policy": [
            "Discovery scans the standard lightweight child-skill files when present.",
            "Exact repository matches outrank name, DOI, API, and task_type overlap.",
            "Reuse requires full task_type coverage and a structurally reusable existing skill.",
            "Update is preferred when a related skill exists but task_type coverage or child-skill shape is incomplete.",
        ],
    }
