"""Audit generated public child-skill markdown for release safety."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


SECRET_PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("credential_assignment", re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
]
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", flags=re.S)

MAX_MARKDOWN_CHARS = 25000
MAX_CODE_FENCE_LINES = 120
MAX_CODE_FENCE_CHARS = 8000


def markdown_files(skill_dir: Path) -> list[Path]:
    return [path for path in sorted(skill_dir.rglob("*.md")) if path.is_file()]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    path: str,
    message: str,
    **extra: Any,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "path": path, "message": message}
    item.update(extra)
    findings.append(item)


def audit_public_child_skill(skill_dir: Path) -> dict[str, Any]:
    """Return a conservative public-release safety audit for child-skill markdown."""
    findings: list[dict[str, Any]] = []
    files = markdown_files(skill_dir)

    if not files:
        add_finding(
            findings,
            "error",
            "no_markdown_files",
            ".",
            "No public Markdown files were found in the generated child skill.",
        )

    for path in files:
        text = read_text(path)
        rel = str(path.relative_to(skill_dir))
        if len(text) > MAX_MARKDOWN_CHARS:
            add_finding(
                findings,
                "warning",
                "large_markdown_file",
                rel,
                "Markdown file is large enough to risk bundling excessive source excerpts.",
                char_count=len(text),
                max_chars=MAX_MARKDOWN_CHARS,
            )
        for code, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                add_finding(
                    findings,
                    "error",
                    code,
                    rel,
                    "Generated child skill appears to contain a secret, credential, or private key.",
                )
        if EMAIL_RE.search(text):
            add_finding(
                findings,
                "warning",
                "email_address_present",
                rel,
                "Generated child skill contains an email address; confirm it is a public project contact and not personal data.",
            )
        for index, match in enumerate(CODE_FENCE_RE.finditer(text), start=1):
            fence = match.group(2)
            line_count = fence.count("\n") + 1 if fence else 0
            if line_count > MAX_CODE_FENCE_LINES or len(fence) > MAX_CODE_FENCE_CHARS:
                add_finding(
                    findings,
                    "warning",
                    "long_code_fence",
                    rel,
                    "Code fence is long enough to risk copying excessive source or tutorial content into the public skill.",
                    fence_index=index,
                    line_count=line_count,
                    char_count=len(fence),
                    max_lines=MAX_CODE_FENCE_LINES,
                    max_chars=MAX_CODE_FENCE_CHARS,
                )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "checked_file_count": len(files),
        "findings": findings,
        "policy": "Public child skills must not contain credentials, private keys, long copied excerpts, or personal contact data without review.",
    }
