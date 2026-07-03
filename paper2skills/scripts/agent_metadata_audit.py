"""Audit builder skill metadata alignment across SKILL.md and agents/openai.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import load_data, now_utc, read_text
from constants import SCHEMA_VERSION


EXPECTED_SKILL_NAME = "paper2skills"
EXPECTED_DISPLAY_NAME = "Papert2Skills"
ALLOWED_FRONTMATTER_FIELDS = {"name", "description"}
REQUIRED_INTERFACE_FIELDS = ["display_name", "short_description", "default_prompt"]
REQUIRED_METADATA_CONCEPTS = {
    "codex": [["codex"]],
    "source_grounded": [["source-grounded"], ["source grounded"]],
    "scientific_package": [["scientific", "package"]],
    "task_type": [["task_type"]],
    "contracts": [["contract"]],
    "refusal": [["refusal"], ["refuse"]],
    "evidence": [["evidence"]],
}


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


def frontmatter_and_body(text: str) -> tuple[dict[str, str] | None, str]:
    if not text.startswith("---\n"):
        return None, text
    try:
        _, rest = text.split("---\n", 1)
        frontmatter, body = rest.split("---\n", 1)
    except ValueError:
        return None, text
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            return None, body
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields, body


def missing_concepts(text: str) -> list[str]:
    lowered = text.lower()
    missing: list[str] = []
    for concept, alternatives in REQUIRED_METADATA_CONCEPTS.items():
        if not any(all(token in lowered for token in alternative) for alternative in alternatives):
            missing.append(concept)
    return missing


def build_agent_metadata_audit(skill_dir: Path) -> dict[str, Any]:
    """Return a static audit of skill trigger metadata and UI metadata alignment."""
    findings: list[dict[str, Any]] = []
    skill_path = skill_dir / "SKILL.md"
    openai_path = skill_dir / "agents" / "openai.yaml"

    skill_text = read_text(skill_path) if skill_path.exists() else ""
    frontmatter, body = frontmatter_and_body(skill_text)
    if frontmatter is None:
        frontmatter = {}
        add_finding(findings, "error", "invalid_skill_frontmatter", "SKILL.md must have YAML frontmatter.", "SKILL.md")

    missing_frontmatter = sorted(ALLOWED_FRONTMATTER_FIELDS - set(frontmatter))
    extra_frontmatter = sorted(set(frontmatter) - ALLOWED_FRONTMATTER_FIELDS)
    for field in missing_frontmatter:
        add_finding(findings, "error", "missing_skill_frontmatter_field", "SKILL.md frontmatter is missing a required field.", f"SKILL.md:{field}")
    for field in extra_frontmatter:
        add_finding(findings, "error", "unsupported_skill_frontmatter_field", "SKILL.md frontmatter must only contain name and description.", f"SKILL.md:{field}")
    if frontmatter.get("name") != EXPECTED_SKILL_NAME:
        add_finding(findings, "error", "skill_name_mismatch", "SKILL.md name must match the installable skill name.", "SKILL.md:name")

    skill_metadata_text = " ".join([frontmatter.get("name", ""), frontmatter.get("description", ""), body])
    missing_skill_concepts = missing_concepts(skill_metadata_text)
    for concept in missing_skill_concepts:
        add_finding(findings, "error", "skill_metadata_missing_concept", "SKILL.md metadata/body does not describe a required builder concept.", concept)

    openai_data = load_data(openai_path) if openai_path.exists() else {}
    interface = openai_data.get("interface") if isinstance(openai_data, dict) else None
    if not isinstance(interface, dict):
        interface = {}
        add_finding(findings, "error", "missing_openai_interface", "agents/openai.yaml must contain an interface mapping.", "agents/openai.yaml")

    for field in REQUIRED_INTERFACE_FIELDS:
        if not interface.get(field):
            add_finding(findings, "error", "missing_openai_interface_field", "agents/openai.yaml interface field is missing.", f"agents/openai.yaml:{field}")

    display_name = str(interface.get("display_name") or "")
    short_description = str(interface.get("short_description") or "")
    default_prompt = str(interface.get("default_prompt") or "")

    if display_name != EXPECTED_DISPLAY_NAME:
        add_finding(findings, "error", "display_name_mismatch", "OpenAI display_name must match the builder product name.", "agents/openai.yaml:display_name")
    if EXPECTED_DISPLAY_NAME not in skill_text:
        add_finding(findings, "error", "display_name_not_rendered", "SKILL.md must render the product display name used by agents/openai.yaml.", "SKILL.md")
    if f"${EXPECTED_SKILL_NAME}" not in default_prompt:
        add_finding(findings, "error", "default_prompt_missing_skill_token", "OpenAI default_prompt must explicitly mention the skill token.", "agents/openai.yaml:default_prompt")
    if len(short_description) > 140:
        add_finding(findings, "error", "short_description_too_long", "OpenAI short_description should remain short enough for UI display.", "agents/openai.yaml:short_description")
    if len(default_prompt) > 240:
        add_finding(findings, "error", "default_prompt_too_long", "OpenAI default_prompt should remain a short starter prompt.", "agents/openai.yaml:default_prompt")

    interface_text = " ".join([display_name, short_description, default_prompt])
    missing_openai_concepts = missing_concepts(interface_text)
    for concept in missing_openai_concepts:
        add_finding(findings, "error", "openai_metadata_missing_concept", "agents/openai.yaml does not describe a required builder concept.", concept)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "skill_dir": str(skill_dir),
        "skill_path": str(skill_path),
        "openai_path": str(openai_path),
        "allowed_frontmatter_fields": sorted(ALLOWED_FRONTMATTER_FIELDS),
        "frontmatter_fields": sorted(frontmatter),
        "required_interface_fields": REQUIRED_INTERFACE_FIELDS,
        "interface_fields": sorted(interface),
        "display_name": display_name,
        "short_description_length": len(short_description),
        "default_prompt_has_skill_token": f"${EXPECTED_SKILL_NAME}" in default_prompt,
        "required_concepts": sorted(REQUIRED_METADATA_CONCEPTS),
        "missing_skill_concepts": missing_skill_concepts,
        "missing_openai_concepts": missing_openai_concepts,
        "findings": findings,
        "policy": [
            "SKILL.md frontmatter must remain limited to name and description.",
            "agents/openai.yaml must stay aligned with the installable skill name and product display name.",
            "UI metadata must describe the builder as a Codex-focused source-grounded scientific package skill builder with task_type routing, contracts, refusal boundaries, and evidence.",
        ],
    }
