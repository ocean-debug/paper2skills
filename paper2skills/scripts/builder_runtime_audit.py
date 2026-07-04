"""Static audit for the Papert2Skills builder runtime surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import load_data, now_utc, read_text
from constants import BUILDER_VERSION, SCHEMA_VERSION


REQUIRED_SKILL_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "templates/build_request.yaml",
    "scripts/papert2skills.py",
]

REQUIRED_TEMPLATE_FIELDS = [
    "schema_version",
    "package_name",
    "method_name",
    "repo_url",
    "tutorial_links",
    "doc_links",
    "paper_links",
    "paper_dois",
    "api_names",
    "source_material_paths",
    "target_agent",
    "language_backend",
    "execution_grounded",
    "execution_traces",
    "execution_replay_results",
    "eval_results",
    "agent_rollout_results",
    "agent_skillopt_proposals",
    "smoke_test_results",
    "require_smoke_test",
    "e2e_acceptance_results",
    "require_e2e_acceptance",
    "execution_environment",
    "existing_skills_dirs",
    "output_dir",
    "requested_task_types",
    "fetch_sources",
    "max_fetch_bytes",
    "max_index_files",
    "max_index_bytes",
    "review_iterations",
    "review_min_score_ratio",
]

REQUIRED_EXECUTION_ENV_FIELDS = [
    "mode",
    "host",
    "working_directory",
    "environment_name",
    "node",
    "cores",
    "remote_only",
    "notes",
]

REQUIRED_CLI_COMMANDS = [
    "build",
    "lint-child",
    "validate-run",
    "audit-child",
    "audit-public-child",
    "audit-child-package-purity",
    "audit-biological-claims",
    "verify-run-manifest",
    "audit-build-timeline",
    "audit-completion",
    "audit-protocol-compliance",
    "audit-agent-metadata",
    "audit-public-origin",
    "audit-source-fetch-boundaries",
    "audit-key-api-coverage",
    "audit-discovery-resolution",
    "audit-eval-leakage",
    "audit-external-results",
    "audit-evidence-claim-taxonomy",
    "audit-execution-replay",
    "audit-e2e-acceptance",
    "audit-smoke-test-plan",
    "audit-completion-evidence",
    "build-acceptance-handoff",
    "judge-agent-rollout-results",
    "validate-forward-test-plan",
    "audit-skill-package",
    "audit-module-inventory",
    "audit-builder-baseline",
    "skillopt-next-step",
]

REQUIRED_OPENAI_INTERFACE_FIELDS = [
    "display_name",
    "short_description",
    "default_prompt",
]


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
        _prefix, rest = text.split("---\n", 1)
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


def build_builder_runtime_audit(request: dict[str, Any], skill_dir: Path) -> dict[str, Any]:
    """Return a non-executing audit of the builder skill's callable surface."""
    findings: list[dict[str, Any]] = []

    if not skill_dir.exists():
        add_finding(findings, "error", "missing_skill_dir", "Builder skill directory does not exist.", str(skill_dir))

    file_records: list[dict[str, Any]] = []
    for relative in REQUIRED_SKILL_FILES:
        path = skill_dir / relative
        exists = path.exists()
        size = path.stat().st_size if exists and path.is_file() else 0
        file_records.append({"path": relative, "exists": exists, "bytes": size})
        if not exists:
            add_finding(findings, "error", "missing_required_builder_file", "Required builder runtime file is missing.", relative)
        elif size == 0:
            add_finding(findings, "error", "empty_required_builder_file", "Required builder runtime file is empty.", relative)

    skill_path = skill_dir / "SKILL.md"
    if skill_path.exists():
        fields = frontmatter_fields(read_text(skill_path))
        if fields is None:
            add_finding(findings, "error", "invalid_skill_frontmatter", "Builder SKILL.md must have YAML frontmatter.", "SKILL.md")
        else:
            for field in ("name", "description"):
                if not fields.get(field):
                    add_finding(findings, "error", "missing_skill_frontmatter_field", "Builder SKILL.md frontmatter field is missing.", "SKILL.md")
            if fields.get("name") != "paper2skills":
                add_finding(findings, "error", "unexpected_skill_name", "Builder skill name must be paper2skills.", "SKILL.md")

    openai_path = skill_dir / "agents" / "openai.yaml"
    openai_interface: dict[str, Any] = {}
    if openai_path.exists():
        openai_data = load_data(openai_path)
        openai_interface = openai_data.get("interface") if isinstance(openai_data, dict) else {}
        for field in REQUIRED_OPENAI_INTERFACE_FIELDS:
            if not openai_interface.get(field):
                add_finding(findings, "error", "missing_openai_interface_field", "Builder agents/openai.yaml interface field is missing.", "agents/openai.yaml")

    template_path = skill_dir / "templates" / "build_request.yaml"
    template_data: dict[str, Any] = {}
    if template_path.exists():
        loaded = load_data(template_path)
        template_data = loaded if isinstance(loaded, dict) else {}
        for field in REQUIRED_TEMPLATE_FIELDS:
            if field not in template_data:
                add_finding(findings, "error", "missing_build_request_template_field", "Build request template is missing a required field.", "templates/build_request.yaml")
        execution_environment = template_data.get("execution_environment") or {}
        for field in REQUIRED_EXECUTION_ENV_FIELDS:
            if field not in execution_environment:
                add_finding(findings, "error", "missing_execution_environment_template_field", "Execution environment template is missing a required field.", "templates/build_request.yaml")
        if template_data.get("target_agent") != "codex":
            add_finding(findings, "error", "template_target_agent_not_codex", "Build request template must target Codex.", "templates/build_request.yaml")
        if template_data.get("language_backend") != "python":
            add_finding(findings, "error", "template_backend_not_python", "Build request template must default to the Python backend.", "templates/build_request.yaml")

    cli_path = skill_dir / "scripts" / "papert2skills.py"
    cli_commands: list[str] = []
    if cli_path.exists():
        cli_text = read_text(cli_path)
        for command in REQUIRED_CLI_COMMANDS:
            if f'"{command}"' in cli_text or f"'{command}'" in cli_text:
                cli_commands.append(command)
            else:
                add_finding(findings, "error", "missing_cli_command", "Builder CLI is missing a required command.", "scripts/papert2skills.py")
        if "from build_pipeline import build" not in cli_text:
            add_finding(findings, "error", "cli_not_wired_to_pipeline", "Builder CLI must delegate build to build_pipeline.", "scripts/papert2skills.py")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "skill_dir": str(skill_dir),
        "required_files": REQUIRED_SKILL_FILES,
        "file_records": file_records,
        "required_template_fields": REQUIRED_TEMPLATE_FIELDS,
        "required_execution_environment_fields": REQUIRED_EXECUTION_ENV_FIELDS,
        "template_field_count": len(template_data),
        "required_cli_commands": REQUIRED_CLI_COMMANDS,
        "observed_cli_commands": cli_commands,
        "required_openai_interface_fields": REQUIRED_OPENAI_INTERFACE_FIELDS,
        "openai_interface_fields": sorted(openai_interface.keys()),
        "findings": findings,
        "policy": [
            "Builder runtime audit is static and never imports builder modules or runs CLI commands.",
            "The builder must remain a callable Codex skill with a thin CLI, build request template, and UI metadata.",
            "Runtime execution, tests, builds, lint, and tutorial reproduction remain governed by the user's explicit execution environment constraints.",
        ],
    }
