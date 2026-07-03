"""Check generated child skill drafts for unresolved placeholders."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


ERROR_PATTERNS = {
    "fill_marker": re.compile(r"<FILL[:>]", re.I),
    "template_braces": re.compile(r"{{|}}"),
    "todo_marker": re.compile(r"\bTODO\b|\bTBD\b", re.I),
    "lorem_ipsum": re.compile(r"lorem ipsum", re.I),
}

DEFAULT_REQUEST_STRINGS = {
    "https://github.com/owner/example-package",
    "example.org/tutorial",
    "example.org/docs",
}


def markdown_files(skill_dir: Path) -> list[Path]:
    return sorted(path for path in skill_dir.rglob("*.md") if path.is_file())


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    path: str,
    message: str,
    value: str | None = None,
) -> None:
    finding: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }
    if value is not None:
        finding["value"] = value
    findings.append(finding)


def check_text(path: Path, root: Path, text: str, findings: list[dict[str, Any]]) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    for code, pattern in ERROR_PATTERNS.items():
        if pattern.search(text):
            add_finding(
                findings,
                "error",
                code,
                rel,
                "Generated child skill contains an unresolved draft marker.",
            )
    for value in DEFAULT_REQUEST_STRINGS:
        if value in text:
            add_finding(
                findings,
                "error",
                "default_request_value",
                rel,
                "Generated child skill contains a build-request template value.",
                value,
            )


def check_request_defaults(request: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    repo_url = str(request.get("repo_url") or "")
    if repo_url == "https://github.com/owner/example-package":
        add_finding(
            findings,
            "error",
            "default_repo_url",
            "build_request",
            "Build request still uses the template repository URL.",
            repo_url,
        )
    if request.get("package_name") == "example-package":
        add_finding(
            findings,
            "warning",
            "default_package_name",
            "build_request",
            "Build request package_name matches the template value.",
            "example-package",
        )


def build_draft_readiness(request: dict[str, Any], child_skill_dir: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files = markdown_files(child_skill_dir)
    if not files:
        add_finding(
            findings,
            "error",
            "no_markdown_files",
            str(child_skill_dir),
            "Generated child skill has no Markdown files to review.",
        )
    for path in files:
        check_text(path, child_skill_dir, read_text(path), findings)
    check_request_defaults(request, findings)
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "checked_file_count": len(files),
        "findings": findings,
        "policy": [
            "Draft readiness checks the generated public child skill, not downloaded sources.",
            "Unresolved fill markers, template braces, TODO/TBD markers, lorem text, and default build-request URLs block publish.",
        ],
    }
