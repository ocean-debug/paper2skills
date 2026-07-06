"""Audit public project files for private origin markers and local execution details."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION, TEXT_FILE_SUFFIXES


PUBLIC_ROOT_FILES = {"README.md", "LICENSE", ".gitignore"}
GENERIC_MARKER_SUFFIXES = {".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".json", ".html", ".htm"}

ALWAYS_FORBIDDEN_PATTERNS = [
    ("legacy_product_name", ["Paper", "t", "2", "Skills"]),
    ("legacy_product_token", ["paper", "t", "2", "skills"]),
    ("legacy_product_prefix", ["paper", "t"]),
    ("reference_platform_name", ["Omi", "cOS"]),
    ("reference_org_name", ["omi", "cverse"]),
    ("reference_builder_name", ["omi", "cos"]),
    ("reference_builder_suffix", ["port", "build"]),
    ("reference_builder_flow_name", ["port", "flow"]),
    ("reference_builder_loop_phrase", ["port", " loop"]),
    ("reference_review_origin_name", ["Skill", "Opt"]),
    ("reference_review_origin_token", ["skill", "opt"]),
]
DOCUMENT_FORBIDDEN_PATTERNS = [
    ("legacy_short_label_upper", ["M", "V", "P"]),
    ("legacy_short_label_lower", ["m", "v", "p"]),
    ("private_ipv4_prefix", ["192", ".168", "."]),
    ("private_home_path", ["/ho", "me/"]),
    ("private_gpu_node", ["gpu", "03"]),
    ("private_conda_activation", ["conda", " activate ", "skill"]),
    ("private_remote_phrase", ["private", " remote"]),
    ("example_package_name", ["scvi", "-tools"]),
]
FORBIDDEN_PATTERNS = ALWAYS_FORBIDDEN_PATTERNS + DOCUMENT_FORBIDDEN_PATTERNS
PRIVATE_IPV4_RE = re.compile(r"\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|" + "192" + r"\." + "168" + r")\.\d{1,3}\.\d{1,3}\b")
PATH_SEPARATOR_RE = r"(?:/|" + re.escape(chr(92)) + ")"
GENERIC_FORBIDDEN_REGEXES = [
    ("windows_absolute_path", re.compile(r"[A-Za-z]:" + PATH_SEPARATOR_RE + r"[^\s)\"']+")),
    ("file_uri_local_path", re.compile("file://" + r"/[^\s)\"']+", re.IGNORECASE)),
    ("posix_user_local_path", re.compile(r"(?<!:)\/(?:home|Users|tmp|var\/folders)\/[^\s)\"']+")),
    ("unc_local_path", re.compile(re.escape(chr(92) * 2) + r"[^\s)\"']+")),
    ("private_ipv4_address", PRIVATE_IPV4_RE),
    ("remote_host_field", re.compile(r"\b(?:host|hostname|remote_host|server)\s*[:=]\s*['\"]?[A-Za-z0-9_.-]+['\"]?", re.IGNORECASE)),
    ("environment_name_field", re.compile(r"\b(?:conda_env|environment_name|env_name|runtime_env)\s*[:=]\s*['\"]?[A-Za-z0-9_.-]+['\"]?", re.IGNORECASE)),
    ("node_label", re.compile(r"\b(?:gpu|node|login)[0-9]{1,3}\b", re.IGNORECASE)),
    ("conda_activation_command", re.compile(r"\bconda\s+activate\s+[A-Za-z0-9_.-]+", re.IGNORECASE)),
]
SAFE_PLACEHOLDER_VALUES = {"", "null", "none", "~", "unspecified", "<redacted>", "<placeholder>", "example"}


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
    for filename in PUBLIC_ROOT_FILES:
        root_file = repo_root / filename
        if root_file.exists():
            paths.append(root_file)
    if skill_dir.exists():
        for path in skill_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_FILE_SUFFIXES:
                continue
            paths.append(path)
    return sorted(set(paths))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return f"<external>/{path.name}"


def field_value(line: str) -> str:
    separator = ":" if ":" in line else "=" if "=" in line else ""
    if not separator:
        return ""
    return line.split(separator, 1)[1].strip().strip("'\"").lower()


def is_safe_placeholder(code: str, line: str) -> bool:
    if code not in {"remote_host_field", "environment_name_field"}:
        return False
    value = field_value(line)
    return value in SAFE_PLACEHOLDER_VALUES or value.startswith("<")


def should_scan_generic_markers(path: Path) -> bool:
    return path.suffix.lower() in GENERIC_MARKER_SUFFIXES or path.name in PUBLIC_ROOT_FILES


def build_public_origin_audit(repo_root: Path, skill_dir: Path) -> dict[str, Any]:
    """Return a static audit for public-facing project files."""
    findings: list[dict[str, Any]] = []
    files = public_text_files(repo_root, skill_dir)
    pattern_records: list[dict[str, Any]] = []
    always_patterns: list[tuple[str, str]] = []
    document_patterns: list[tuple[str, str]] = []
    for code, parts in ALWAYS_FORBIDDEN_PATTERNS:
        pattern = "".join(parts)
        pattern_records.append({"code": code, "pattern_length": len(pattern)})
        always_patterns.append((code, pattern.lower()))
    for code, parts in DOCUMENT_FORBIDDEN_PATTERNS:
        pattern = "".join(parts)
        pattern_records.append({"code": code, "pattern_length": len(pattern)})
        document_patterns.append((code, pattern.lower()))
    for path in files:
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            add_finding(findings, "warning", "public_file_not_utf8", "Public text candidate could not be decoded as UTF-8.", rel(path, repo_root))
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            active_patterns = always_patterns + (document_patterns if should_scan_generic_markers(path) else [])
            for code, lowered_pattern in active_patterns:
                if lowered_pattern in line.lower():
                    add_finding(
                        findings,
                        "error",
                        code,
                        "Public project file contains a private origin marker, reference-source marker, legacy label, or machine-specific execution detail.",
                        rel(path, repo_root),
                        index,
                    )
            if should_scan_generic_markers(path):
                for code, regex in GENERIC_FORBIDDEN_REGEXES:
                    if regex.search(line) and not is_safe_placeholder(code, line):
                        add_finding(
                            findings,
                            "error",
                            code,
                            "Public project file contains a local path, host, runtime environment, node label, or private network detail.",
                            rel(path, repo_root),
                            index,
                        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "repo_root": ".",
        "skill_dir": rel(skill_dir, repo_root),
        "checked_files": [rel(path, repo_root) for path in files],
        "checked_file_count": len(files),
        "ignored_skill_subtrees": [],
        "generic_marker_suffixes": sorted(GENERIC_MARKER_SUFFIXES),
        "pattern_records": pattern_records,
        "findings": findings,
        "policy": [
            "Public project files must describe paper2skills without exposing private origin markers or machine-specific execution details.",
            "README.md, LICENSE, SKILL.md, agents, references, templates, and scripts are public package surfaces.",
            "Source files are checked for legacy product and reference-source markers; machine path and host regexes run on documentation and structured public metadata surfaces.",
            "Remote testing examples must remain generic.",
            "This audit is static and does not execute builder code, install dependencies, or contact external services.",
        ],
    }
