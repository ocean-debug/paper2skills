"""Install-readiness checks for generated child skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from action_policy import REUSE_EXISTING
from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


FORBIDDEN_PUBLIC_SUFFIXES = {".yaml", ".yml", ".json", ".jsonl", ".zip"}
FORBIDDEN_PUBLIC_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}


def rel_path(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        finding["path"] = path
    findings.append(finding)


def expected_release_files() -> list[str]:
    return ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]


def actual_public_files(child_skill_dir: Path) -> list[str]:
    if not child_skill_dir.exists():
        return []
    return sorted(rel_path(path, child_skill_dir) for path in child_skill_dir.rglob("*") if path.is_file())


def build_install_readiness(
    request: dict[str, Any],
    child_skill_dir: Path,
    release_package: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    expected = expected_release_files()
    actual = actual_public_files(child_skill_dir)
    release_files = sorted(str(item.get("path")) for item in release_package.get("files", []) if item.get("path"))
    action = release_package.get("recommended_action")

    if action == REUSE_EXISTING:
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at": now_utc(),
            "package_name": request.get("package_name"),
            "method_name": request.get("method_name") or request.get("package_name"),
            "status": "not_applicable",
            "child_skill_path": str(child_skill_dir),
            "expected_files": expected,
            "actual_files": actual,
            "release_manifest_files": release_files,
            "findings": findings,
            "policy": [
                "Install readiness is skipped for reuse_existing because no generated duplicate should be copied.",
                "Reuse points to the existing child skill recorded in release_package.yaml.",
            ],
        }

    if not child_skill_dir.exists():
        add_finding(findings, "error", "missing_child_skill_dir", "Child skill directory does not exist.", str(child_skill_dir))

    for path in expected:
        full_path = child_skill_dir / path
        if not full_path.exists():
            add_finding(findings, "error", "missing_install_file", "Required install file is missing.", path)
        elif full_path.stat().st_size == 0:
            add_finding(findings, "error", "empty_install_file", "Required install file is empty.", path)

    for path in actual:
        suffix = Path(path).suffix.lower()
        name = Path(path).name
        if suffix in FORBIDDEN_PUBLIC_SUFFIXES:
            add_finding(findings, "error", "build_artifact_in_child_skill", "Build artifact file must not be inside the public child skill.", path)
        if name in FORBIDDEN_PUBLIC_NAMES:
            add_finding(findings, "error", "auxiliary_doc_in_child_skill", "Auxiliary documentation must not be inside the public child skill.", path)
        if "__pycache__" in Path(path).parts:
            add_finding(findings, "error", "cache_file_in_child_skill", "Cache files must not be inside the public child skill.", path)

    missing_from_manifest = sorted(path for path in expected if path not in release_files)
    for path in missing_from_manifest:
        add_finding(findings, "error", "release_manifest_missing_file", "Release package manifest omits a required file.", path)

    unexpected_public_files = sorted(path for path in actual if path not in expected)
    for path in unexpected_public_files:
        add_finding(findings, "warning", "extra_public_file", "Child skill contains an extra public file not listed as required.", path)

    if release_package.get("status") != "ready":
        add_finding(findings, "error", "release_package_not_ready", "Release package is not ready.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "child_skill_path": str(child_skill_dir),
        "expected_files": expected,
        "actual_files": actual,
        "release_manifest_files": release_files,
        "findings": findings,
        "policy": [
            "Install readiness is a manifest and filesystem check only; it does not copy or install the skill.",
            "The public child skill should contain SKILL.md and required references, not build-run artifacts or auxiliary docs.",
        ],
    }
