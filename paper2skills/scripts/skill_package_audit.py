"""Audit the Papert2Skills builder skill package shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


ALLOWED_TOP_LEVEL_FILES = {"SKILL.md"}
ALLOWED_TOP_LEVEL_DIRS = {"agents", "assets", "references", "scripts", "templates"}
FORBIDDEN_AUX_DOC_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}
REQUIRED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/papert2skills.py",
    "templates/build_request.yaml",
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


def frontmatter_fields(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    try:
        _, rest = text.split("---\n", 1)
        frontmatter, _body = rest.split("---\n", 1)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def audit_skill_package(skill_dir: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if not skill_dir.exists() or not skill_dir.is_dir():
        add_finding(findings, "error", "missing_skill_dir", "Skill package directory does not exist.", str(skill_dir))
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at": now_utc(),
            "status": "fail",
            "skill_dir": str(skill_dir),
            "checked_files": [],
            "findings": findings,
        }

    files = sorted(rel(path, skill_dir) for path in skill_dir.rglob("*") if path.is_file())
    top_level_paths = list(skill_dir.iterdir())
    for path in top_level_paths:
        if path.is_file() and path.name not in ALLOWED_TOP_LEVEL_FILES:
            add_finding(
                findings,
                "error",
                "unsupported_top_level_file",
                "Builder skill packages should keep top-level files limited to SKILL.md.",
                path.name,
            )
        if path.is_dir() and path.name not in ALLOWED_TOP_LEVEL_DIRS:
            add_finding(
                findings,
                "error",
                "unsupported_top_level_dir",
                "Builder skill package contains an unsupported top-level directory.",
                path.name,
            )

    for required in sorted(REQUIRED_FILES):
        path = skill_dir / required
        if not path.exists():
            add_finding(findings, "error", "missing_required_skill_file", "Required builder skill file is missing.", required)
        elif path.is_file() and path.stat().st_size == 0:
            add_finding(findings, "error", "empty_required_skill_file", "Required builder skill file is empty.", required)

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        fields = frontmatter_fields(read_text(skill_md))
        if fields is None:
            add_finding(findings, "error", "invalid_skill_frontmatter", "SKILL.md must use YAML frontmatter.", "SKILL.md")
        else:
            missing = [field for field in ("name", "description") if not fields.get(field)]
            extra = [field for field in fields if field not in {"name", "description"}]
            if missing:
                add_finding(findings, "error", "missing_skill_frontmatter_field", "SKILL.md frontmatter is missing required fields.", "SKILL.md")
            if extra:
                add_finding(findings, "error", "unsupported_skill_frontmatter_field", "SKILL.md frontmatter must only contain name and description.", "SKILL.md")

    for path in files:
        name = Path(path).name
        if name in FORBIDDEN_AUX_DOC_NAMES:
            add_finding(findings, "error", "auxiliary_doc_in_skill_package", "Auxiliary docs should not live inside the builder skill package.", path)
        if "__pycache__" in Path(path).parts:
            add_finding(findings, "error", "cache_file_in_skill_package", "Cache files should not live inside the builder skill package.", path)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "skill_dir": str(skill_dir),
        "allowed_top_level_files": sorted(ALLOWED_TOP_LEVEL_FILES),
        "allowed_top_level_dirs": sorted(ALLOWED_TOP_LEVEL_DIRS),
        "required_files": sorted(REQUIRED_FILES),
        "checked_files": files,
        "findings": findings,
        "policy": [
            "The builder itself is a Codex skill package.",
            "Keep the builder skill top level limited to SKILL.md and standard resource directories.",
            "Do not add auxiliary docs or non-standard manifest files inside the skill package.",
        ],
    }
