"""Audit builder module inventory documentation and basic module shape."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


REQUIRED_DOCS = [
    "SKILL.md",
    "README.md",
    "references/builder-architecture.md",
]


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    module: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if module:
        item["module"] = module
    findings.append(item)


def module_docstring(path: Path) -> str | None:
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def load_docs(skill_dir: Path, repo_root: Path) -> dict[str, str]:
    docs: dict[str, str] = {}
    for doc in REQUIRED_DOCS:
        path = skill_dir / doc if doc != "README.md" else repo_root / "README.md"
        docs[doc] = read_text(path) if path.exists() else ""
    return docs


def audit_module_inventory(skill_dir: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or skill_dir.parent
    scripts_dir = skill_dir / "scripts"
    findings: list[dict[str, Any]] = []

    if not scripts_dir.exists():
        add_finding(findings, "error", "missing_scripts_dir", "Builder skill package is missing scripts/.", "scripts")
        modules: list[Path] = []
    else:
        modules = sorted(path for path in scripts_dir.glob("*.py") if path.is_file())

    docs = load_docs(skill_dir, repo_root)
    for doc_name, text in docs.items():
        if not text:
            add_finding(findings, "error", "missing_inventory_doc", "Required module inventory document is missing.", doc_name)

    records = []
    for path in modules:
        name = path.name
        docstring = module_docstring(path)
        mentioned_in = sorted(doc for doc, text in docs.items() if name in text)
        records.append(
            {
                "module": name,
                "path": rel(path, skill_dir),
                "has_module_docstring": bool(docstring),
                "mentioned_in": mentioned_in,
            }
        )
        if not docstring:
            add_finding(findings, "error", "module_missing_docstring", "Script module is missing a module docstring.", name)
        missing_docs = sorted(doc for doc in REQUIRED_DOCS if doc not in mentioned_in)
        if missing_docs:
            add_finding(
                findings,
                "warning",
                "module_not_documented_everywhere",
                "Script module is not mentioned in every expected module inventory document.",
                name,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "skill_dir": str(skill_dir),
        "repo_root": str(repo_root),
        "module_count": len(records),
        "required_docs": REQUIRED_DOCS,
        "modules": records,
        "findings": findings,
        "policy": [
            "Every builder script module should have a module docstring.",
            "Every builder script module should be discoverable from SKILL.md, README.md, and builder-architecture.md.",
        ],
    }
