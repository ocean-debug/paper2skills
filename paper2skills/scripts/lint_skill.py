"""Child-skill linting and publish metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from action_policy import normalize_action
from common import now_utc, read_text
from constants import BUILDER_VERSION, REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


FORBIDDEN_AUX_DOC_NAMES = {
    "README.MD",
    "INSTALLATION_GUIDE.MD",
    "QUICK_REFERENCE.MD",
    "CHANGELOG.MD",
}


def frontmatter_fields(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    try:
        _, body = text.split("---\n", 1)
        frontmatter, _ = body.split("---\n", 1)
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


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, path: str, message: str | None = None) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "path": path}
    if message:
        finding["message"] = message
    findings.append(finding)


def build_skill_spec(
    request: dict[str, Any],
    child_skill_dir: Path,
    task_catalog: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "product_name": "Papert2Skills",
        "target_agent": "codex",
        "child_skill": {
            "path": str(child_skill_dir),
            "layout": "scientific-agent-skills-lightweight",
            "one_package_one_skill": True,
            "task_type_count": len(task_catalog["tasks"]),
            "required_files": ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES],
        },
        "backend": {
            "language_backend": request.get("language_backend"),
            "python_first": True,
            "r_backend": "extension_reserved",
        },
    }


def lint_child_skill(skill_dir: Path) -> dict[str, Any]:
    findings = []
    required = [skill_dir / "SKILL.md"] + [skill_dir / "references" / name for name in REQUIRED_CHILD_REFERENCES]
    for path in required:
        if not path.exists():
            add_finding(findings, "error", "missing_required_file", str(path.relative_to(skill_dir)))
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        text = read_text(skill_md)
        fields = frontmatter_fields(text)
        if fields is None:
            add_finding(findings, "error", "invalid_frontmatter", "SKILL.md", "SKILL.md must start with YAML frontmatter.")
        else:
            missing = [field for field in ("name", "description") if not fields.get(field)]
            extra = [field for field in fields if field not in {"name", "description"}]
            if missing:
                add_finding(findings, "error", "missing_frontmatter_field", "SKILL.md", ", ".join(missing))
            if extra:
                add_finding(findings, "error", "unsupported_frontmatter_field", "SKILL.md", ", ".join(extra))
        if "task_type" not in text:
            add_finding(findings, "error", "missing_task_type_guidance", "SKILL.md")
        if len(text.splitlines()) > 500:
            add_finding(findings, "error", "skill_md_too_long", "SKILL.md")
        for reference in REQUIRED_CHILD_REFERENCES:
            rel = f"references/{reference}"
            if rel not in text:
                add_finding(findings, "warning", "reference_not_linked_from_skill", "SKILL.md", rel)
    for reference in REQUIRED_CHILD_REFERENCES:
        path = skill_dir / "references" / reference
        if path.exists():
            text = read_text(path)
            rel = str(path.relative_to(skill_dir))
            if not text.strip():
                add_finding(findings, "error", "empty_reference", rel)
            if not text.lstrip().startswith("#"):
                add_finding(findings, "warning", "reference_missing_heading", rel)
    for path in skill_dir.rglob("*"):
        if path.is_file() and "__pycache__" in path.parts:
            add_finding(findings, "error", "cache_file", str(path.relative_to(skill_dir)))
        if path.is_file() and path.name.upper() in FORBIDDEN_AUX_DOC_NAMES:
            add_finding(findings, "error", "auxiliary_doc_in_child_skill", str(path.relative_to(skill_dir)))
    status = "pass" if not any(item["severity"] == "error" for item in findings) else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "status": status,
        "findings": findings,
    }


def publish_manifest(
    request: dict[str, Any],
    child_skill_dir: Path,
    lint_report: dict[str, Any],
    publish_gate: dict[str, Any] | None = None,
    release_package: dict[str, Any] | None = None,
    skill_update_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate_status = publish_gate.get("status") if publish_gate else None
    status = gate_status or ("publishable" if lint_report["status"] == "pass" else "blocked")
    release_package = release_package or {}
    skill_update_plan = skill_update_plan or {}
    action = normalize_action(
        publish_gate.get("discovery_decision") if publish_gate else None,
        skill_update_plan.get("recommended_action") or (publish_gate.get("recommended_action") if publish_gate else None),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "product_name": "Papert2Skills",
        "child_skill_path": str(child_skill_dir),
        "status": status,
        "lint_status": lint_report["status"],
        "publish_gate_status": gate_status,
        "recommended_action": action,
        "discovery_decision": publish_gate.get("discovery_decision") if publish_gate else None,
        "release_recommended_action": release_package.get("recommended_action"),
        "skill_update_recommended_action": skill_update_plan.get("recommended_action"),
        "target_existing_skill_path": release_package.get("target_existing_skill_path"),
        "blocking_findings": [
            finding for finding in (publish_gate.get("findings", []) if publish_gate else []) if finding.get("severity") == "error"
        ],
        "execution_grounded_requested": bool(request.get("execution_grounded")),
        "verification_policy": "Only supplied successful execution traces can mark task_type entries as execution_verified.",
    }
