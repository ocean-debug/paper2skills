"""Audit that rendered public child skills contain only the lightweight files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, public_child_skill_path
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


ALLOWED_PUBLIC_DIRS = {"references"}
FORBIDDEN_TRACE_NAMES = {
    "DRAFT_INSTRUCTIONS.md",
    "EVOLUTION_PLOT.svg",
    "HOW_TO_INSTALL.md",
    "ITERATION_LOG.md",
    "SOURCE_GROUNDING.md",
}
FORBIDDEN_TRACE_PREFIXES = {
    "SCORE_REPORT",
    "_state_",
}
FORBIDDEN_TRACE_PARTS = {
    "_trajectory",
    "best",
    "candidates",
    "published",
    "assets",
    "scripts",
    "agents",
    "templates",
}


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def build_child_package_purity_audit(
    request: dict[str, Any],
    child_skill_dir: Path,
    skill_spec: dict[str, Any],
) -> dict[str, Any]:
    """Return a strict static audit for the rendered child-skill file set."""
    findings: list[dict[str, Any]] = []
    required_files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    required_set = set(required_files)

    actual_files: list[str] = []
    actual_dirs: list[str] = []
    public_path = public_child_skill_path(child_skill_dir)
    if not child_skill_dir.exists() or not child_skill_dir.is_dir():
        add_finding(findings, "error", "missing_child_skill_dir", "Rendered child skill directory is missing.", public_path)
    else:
        actual_files = sorted(rel(path, child_skill_dir) for path in child_skill_dir.rglob("*") if path.is_file())
        actual_dirs = sorted(rel(path, child_skill_dir) for path in child_skill_dir.rglob("*") if path.is_dir())

    missing_files = sorted(required_set - set(actual_files))
    unexpected_files = sorted(set(actual_files) - required_set)
    unexpected_dirs = sorted(path for path in actual_dirs if path not in ALLOWED_PUBLIC_DIRS)

    for path in missing_files:
        add_finding(findings, "error", "missing_required_public_file", "Required lightweight child-skill file is missing.", path)
    for path in unexpected_files:
        add_finding(findings, "error", "unexpected_public_child_file", "Public child skill contains a file outside the lightweight contract.", path)
    for path in unexpected_dirs:
        add_finding(findings, "error", "unexpected_public_child_directory", "Public child skill contains a directory outside the lightweight contract.", path)

    forbidden_trace_paths: list[str] = []
    for path in actual_files + actual_dirs:
        parts = set(Path(path).parts)
        name = Path(path).name
        if parts & FORBIDDEN_TRACE_PARTS or name in FORBIDDEN_TRACE_NAMES or any(name.startswith(prefix) for prefix in FORBIDDEN_TRACE_PREFIXES):
            forbidden_trace_paths.append(path)
            add_finding(findings, "error", "builder_trace_inside_public_child", "Builder traces or release staging files must not live in the public child skill.", path)

    spec_required = set((skill_spec.get("child_skill") or {}).get("required_files", []))
    if spec_required != required_set:
        add_finding(
            findings,
            "error",
            "skill_spec_required_files_mismatch",
            "skill_spec required child files must exactly match the lightweight child-skill contract.",
            "skill_spec.yaml",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "child_skill_path": public_path,
        "required_public_files": required_files,
        "actual_public_files": actual_files,
        "actual_public_directories": actual_dirs,
        "missing_public_files": missing_files,
        "unexpected_public_files": unexpected_files,
        "unexpected_public_directories": unexpected_dirs,
        "forbidden_trace_paths": sorted(set(forbidden_trace_paths)),
        "findings": findings,
        "policy": [
            "A generated child skill is intentionally lightweight: SKILL.md plus standard references only.",
            "Build traces, candidates, assets, scripts, staging outputs, and auxiliary documents must stay out of the public child skill.",
            "This audit is static and does not copy, publish, install, or execute files.",
        ],
    }
