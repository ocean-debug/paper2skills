"""Audit build output and public child-skill boundary constraints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, public_child_skill_path
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


FORBIDDEN_PUBLIC_SUFFIXES = {".yaml", ".yml", ".json", ".jsonl", ".zip"}
FORBIDDEN_PUBLIC_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}
INSTALL_ROOT_MARKERS = (
    (".codex", "skills"),
    (".agents", "skills"),
)


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


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def public_files(child_skill_dir: Path) -> list[str]:
    if not child_skill_dir.exists():
        return []
    return sorted(str(path.relative_to(child_skill_dir)).replace("\\", "/") for path in child_skill_dir.rglob("*") if path.is_file())


def is_under_likely_install_root(path: Path) -> bool:
    parts = tuple(part.lower() for part in path.resolve().parts)
    for marker in INSTALL_ROOT_MARKERS:
        width = len(marker)
        for index in range(0, len(parts) - width + 1):
            if parts[index : index + width] == marker:
                return True
    return False


def build_output_boundary_audit(
    request: dict[str, Any],
    out: Path,
    child_skill_dir: Path,
    skill_spec: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    expected_files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    actual_files = public_files(child_skill_dir)
    expected_child_root = out / "child_skill"
    output_dir_inside_install_root = is_under_likely_install_root(out)

    if not is_relative_to(child_skill_dir, out):
        add_finding(
            findings,
            "error",
            "child_skill_outside_output_dir",
            "Generated child skill directory must stay inside the build output directory.",
            public_child_skill_path(child_skill_dir),
        )
    if not is_relative_to(child_skill_dir, expected_child_root):
        add_finding(
            findings,
            "error",
            "child_skill_outside_child_skill_root",
            "Generated child skill must be under the output child_skill directory.",
            public_child_skill_path(child_skill_dir),
        )
    if Path(str(request.get("output_dir") or "")).resolve() != out.resolve():
        add_finding(
            findings,
            "error",
            "request_output_dir_mismatch",
            "Normalized request output_dir must match the active build output directory.",
            "request.output_dir",
        )
    if output_dir_inside_install_root:
        add_finding(
            findings,
            "error",
            "output_dir_inside_skill_install_root",
            "Build output_dir must be a run workspace, not a Codex skill install directory.",
            ".",
        )

    spec_path = str((skill_spec.get("child_skill") or {}).get("path") or "")
    if spec_path and spec_path != public_child_skill_path(child_skill_dir):
        add_finding(
            findings,
            "error",
            "skill_spec_path_mismatch",
            "skill_spec child path must match the public run-relative child skill directory.",
            spec_path,
        )

    for path in expected_files:
        if path not in actual_files:
            add_finding(findings, "error", "public_required_file_missing", "Required public child-skill file is missing.", path)

    for path in actual_files:
        suffix = Path(path).suffix.lower()
        name = Path(path).name
        if suffix in FORBIDDEN_PUBLIC_SUFFIXES:
            add_finding(
                findings,
                "error",
                "build_artifact_inside_public_child_skill",
                "Build-run artifact must not be placed inside the public child skill.",
                path,
            )
        if name in FORBIDDEN_PUBLIC_NAMES:
            add_finding(
                findings,
                "error",
                "auxiliary_doc_inside_public_child_skill",
                "Auxiliary docs must not be placed inside the public child skill.",
                path,
            )
        if "__pycache__" in Path(path).parts:
            add_finding(
                findings,
                "error",
                "cache_inside_public_child_skill",
                "Cache files must not be placed inside the public child skill.",
                path,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "output_dir": ".",
        "child_skill_path": public_child_skill_path(child_skill_dir),
        "expected_child_root": "child_skill",
        "output_dir_inside_install_root": output_dir_inside_install_root,
        "install_root_markers": ["/".join(marker) for marker in INSTALL_ROOT_MARKERS],
        "expected_public_files": expected_files,
        "actual_public_files": actual_files,
        "findings": findings,
        "policy": [
            "Build output must stay inside the requested output directory.",
            "Build output must not be placed inside a likely Codex skill install root.",
            "The public child skill must stay under child_skill/ and contain only installable skill files.",
            "This audit is static and does not copy, install, or execute generated files.",
        ],
    }
