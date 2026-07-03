"""Audit public project files for private origin markers and local execution details."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION, TEXT_FILE_SUFFIXES


FORBIDDEN_PATTERNS = [
    ("reference_platform_name", ["Omi", "cOS"]),
    ("reference_org_name", ["omi", "cverse"]),
    ("reference_builder_name", ["omi", "cos"]),
    ("reference_builder_suffix", ["port", "build"]),
    ("legacy_short_label_upper", ["M", "V", "P"]),
    ("legacy_short_label_lower", ["m", "v", "p"]),
    ("private_ipv4_prefix", ["192", ".168", "."]),
    ("private_home_path", ["/ho", "me/"]),
    ("private_gpu_node", ["gpu", "03"]),
    ("private_conda_activation", ["conda", " activate ", "skill"]),
    ("private_remote_phrase", ["private", " remote"]),
    ("example_package_name", ["scvi", "-tools"]),
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    line: int | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    if line is not None:
        item["line"] = line
    findings.append(item)


def public_text_files(repo_root: Path, skill_dir: Path) -> list[Path]:
    paths: list[Path] = []
    readme = repo_root / "README.md"
    if readme.exists():
        paths.append(readme)
    if skill_dir.exists():
        for path in skill_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_FILE_SUFFIXES:
                paths.append(path)
    return sorted(set(paths))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def build_public_origin_audit(repo_root: Path, skill_dir: Path) -> dict[str, Any]:
    """Return a static audit for public-facing project files."""
    findings: list[dict[str, Any]] = []
    files = public_text_files(repo_root, skill_dir)
    pattern_records: list[dict[str, Any]] = []
    for code, parts in FORBIDDEN_PATTERNS:
        pattern = "".join(parts)
        pattern_records.append({"code": code, "pattern_length": len(pattern)})
        lowered_pattern = pattern.lower()
        for path in files:
            try:
                text = read_text(path)
            except UnicodeDecodeError:
                add_finding(findings, "warning", "public_file_not_utf8", "Public text candidate could not be decoded as UTF-8.", rel(path, repo_root))
                continue
            for index, line in enumerate(text.splitlines(), start=1):
                if lowered_pattern in line.lower():
                    add_finding(
                        findings,
                        "error",
                        code,
                        "Public project file contains a private origin marker, reference-source marker, legacy label, or machine-specific execution detail.",
                        rel(path, repo_root),
                        index,
                    )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "repo_root": str(repo_root),
        "skill_dir": str(skill_dir),
        "checked_files": [rel(path, repo_root) for path in files],
        "checked_file_count": len(files),
        "pattern_records": pattern_records,
        "findings": findings,
        "policy": [
            "Public project files must describe Papert2Skills without exposing private origin markers or machine-specific execution details.",
            "README.md and the builder skill package are public surfaces; remote testing examples must remain generic.",
            "This audit is static and does not execute builder code, install dependencies, or contact external services.",
        ],
    }
