"""Fail-closed SkillIR and public child-skill validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import (
    SKILLIR_SCHEMA,
    VALIDATION_SCHEMA,
    as_list,
    dump_yaml,
    load_yaml,
    slugify,
    unique_strings,
)


TASK_REQUIRED_FIELDS = (
    "intent",
    "selection_rules",
    "do_not_select",
    "accepted_inputs",
    "required_metadata",
    "preflight_checks",
    "workflow",
    "api_sequence",
    "parameters",
    "expected_outputs",
    "refusal_rules",
    "technical_validation",
    "biological_boundaries",
    "reuse_contract",
    "troubleshooting",
    "evidence_ids",
)
ALLOWED_VERIFICATION = {
    "source_grounded",
    "execution_verified",
    "execution_failed",
    "unsupported",
}
TASK_FILE_PATTERN = re.compile(r"^task-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
PLACEHOLDER_PATTERN = re.compile(r"(?:<FILL|\bTODO\b|\bTBD\b|example_task)", re.IGNORECASE)
WINDOWS_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\")
POSIX_HOME_PATTERN = re.compile(r"(?:^|[\s`'\"])/(?:home|Users)/[^\s`'\"]+")
FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
def _nonempty_list(value: Any) -> bool:
    return bool([item for item in as_list(value) if str(item).strip()])


def _known_evidence(
    run_dir: Path,
) -> tuple[set[str], set[str], dict[str, dict[str, Any]]]:
    path = run_dir / "evidence.yaml"
    if not path.is_file():
        return set(), set(), {}
    document = load_yaml(path)
    known: set[str] = set()
    uninspected: set[str] = set()
    records: dict[str, dict[str, Any]] = {}
    for item in as_list(document.get("evidence")):
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id") or "")
        if evidence_id:
            known.add(evidence_id)
            records[evidence_id] = item
            if str(item.get("claim_type") or "").endswith("_uninspected"):
                uninspected.add(evidence_id)
    return known, uninspected, records


def validate_spec(run_dir: Path) -> dict[str, Any]:
    """Validate SkillIR behavior, evidence links, and verification claims."""

    blockers: list[str] = []
    warnings: list[str] = []
    path = run_dir / "skill_spec.yaml"
    if not path.is_file():
        return {
            "schema_version": VALIDATION_SCHEMA,
            "status": "blocked",
            "blockers": ["missing_skill_spec"],
            "warnings": [],
        }

    spec = load_yaml(path)
    if spec.get("schema_version") != SKILLIR_SCHEMA:
        blockers.append("invalid_skillir_schema")

    package = spec.get("package")
    if not isinstance(package, dict):
        blockers.append("missing_package_mapping")
        package = {}
    for field in ("name", "display_name", "description", "source_revision"):
        if not str(package.get(field) or "").strip():
            blockers.append(f"missing_package_{field}")
    if str(package.get("source_revision") or "").strip().lower() == "unresolved":
        warnings.append("source_revision_unresolved")
    if package.get("name"):
        try:
            normalized = slugify(str(package["name"]))
            if normalized != package["name"]:
                blockers.append("package_name_not_normalized")
        except Exception:
            blockers.append("invalid_package_name")

    for field in ("shared_environment", "package_boundaries", "shared_troubleshooting"):
        if not _nonempty_list(spec.get(field)):
            blockers.append(f"missing_{field}")

    tasks = spec.get("task_types")
    if not isinstance(tasks, dict) or not tasks:
        blockers.append("no_task_types")
        tasks = {}

    known_evidence, uninspected_evidence, evidence_records = _known_evidence(run_dir)
    output_files: set[str] = set()
    grounded_api_names: set[str] = set()
    report_path = run_dir / "source_report.yaml"
    if report_path.is_file():
        source_report = load_yaml(report_path)
        grounded_api_names = set(unique_strings(source_report.get("grounded_apis", [])))
        for requested_api in unique_strings(source_report.get("requested_key_apis", [])):
            if not any(
                requested_api == candidate
                or requested_api.endswith("." + candidate)
                or candidate.endswith("." + requested_api)
                for candidate in grounded_api_names
            ):
                blockers.append(f"requested_key_api_ungrounded:{requested_api}")

    for task_type, task in tasks.items():
        prefix = f"task:{task_type}:"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(task_type)):
            blockers.append(prefix + "invalid_task_type_name")
        if not isinstance(task, dict):
            blockers.append(prefix + "not_a_mapping")
            continue
        output_file = str(task.get("output_file") or "")
        if not TASK_FILE_PATTERN.fullmatch(output_file):
            blockers.append(prefix + "invalid_output_file")
        elif output_file in output_files:
            blockers.append(prefix + "duplicate_output_file")
        output_files.add(output_file)

        for field in TASK_REQUIRED_FIELDS:
            if not _nonempty_list(task.get(field)):
                blockers.append(prefix + f"missing_{field}")

        verification = str(task.get("verification_status") or "")
        if verification not in ALLOWED_VERIFICATION:
            blockers.append(prefix + "invalid_verification_status")
        execution_ids = set(
            unique_strings(as_list(task.get("execution_evidence")))
        )
        if verification in {"execution_verified", "execution_failed"}:
            if not execution_ids:
                blockers.append(prefix + "execution_status_without_evidence")
            elif execution_ids - known_evidence:
                blockers.append(prefix + "unknown_execution_evidence")
            elif any(
                evidence_records[evidence_id].get("kind") != "execution"
                for evidence_id in execution_ids
            ):
                blockers.append(prefix + "non_execution_evidence_for_execution_status")

        evidence_ids = set(unique_strings(as_list(task.get("evidence_ids"))))
        missing_evidence = sorted(evidence_ids - known_evidence)
        if missing_evidence:
            blockers.append(prefix + "unknown_evidence:" + ",".join(missing_evidence))
        if evidence_ids and evidence_ids <= uninspected_evidence:
            blockers.append(prefix + "only_uninspected_external_evidence")

        for index, api_entry in enumerate(as_list(task.get("api_sequence"))):
            api_prefix = prefix + f"api:{index}:"
            if not isinstance(api_entry, dict):
                blockers.append(api_prefix + "not_structured")
                continue
            api = str(api_entry.get("api") or "").strip()
            action = str(api_entry.get("action") or "").strip()
            api_evidence = set(
                unique_strings(as_list(api_entry.get("evidence_ids")))
            )
            if not api or not action:
                blockers.append(api_prefix + "missing_api_or_action")
            if not api_evidence:
                blockers.append(api_prefix + "missing_evidence_ids")
            elif not api_evidence <= evidence_ids:
                blockers.append(api_prefix + "api_evidence_not_in_task_evidence")
            elif api_evidence - known_evidence:
                blockers.append(api_prefix + "unknown_evidence")
            elif api_evidence <= uninspected_evidence:
                blockers.append(api_prefix + "uninspected_external_evidence")
            elif not any(
                evidence_records[evidence_id].get("kind") in {"source", "tutorial"}
                for evidence_id in api_evidence
                if evidence_id in evidence_records
            ):
                blockers.append(api_prefix + "api_not_grounded_in_source_or_tutorial")
            if api and grounded_api_names and not any(
                api == candidate
                or api.endswith("." + candidate)
                or candidate.endswith("." + api)
                for candidate in grounded_api_names
            ):
                blockers.append(api_prefix + f"ungrounded_api:{api}")

    routing = spec.get("routing")
    if not isinstance(routing, dict):
        blockers.append("missing_routing_mapping")
        routing = {}
    aliases = routing.get("aliases")
    if aliases is not None and not isinstance(aliases, dict):
        blockers.append("routing_aliases_not_mapping")
    elif isinstance(aliases, dict):
        for alias, target in aliases.items():
            if target not in tasks:
                blockers.append(f"routing_alias_unknown_task:{alias}:{target}")
    if not _nonempty_list(routing.get("unsupported_cases")):
        blockers.append("missing_unsupported_cases")
    if len(tasks) > 1 and not _nonempty_list(routing.get("ambiguity_rules")):
        if not str(routing.get("disjoint_task_reason") or "").strip():
            blockers.append("missing_multi_task_ambiguity_rule")

    if PLACEHOLDER_PATTERN.search(str(spec)):
        blockers.append("unresolved_placeholder")

    return {
        "schema_version": VALIDATION_SCHEMA,
        "status": "pass" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "task_count": len(tasks),
        "known_evidence_count": len(known_evidence),
    }


def validate_child(run_dir: Path, spec_report: dict[str, Any]) -> dict[str, Any]:
    """Validate public package shape and direct progressive-disclosure links."""

    blockers = list(spec_report.get("blockers", []))
    warnings = list(spec_report.get("warnings", []))
    spec = load_yaml(run_dir / "skill_spec.yaml")
    package = spec.get("package") if isinstance(spec.get("package"), dict) else {}
    package_name = slugify(str(package.get("name") or "invalid"))
    child = run_dir / "child_skill" / package_name
    required_shared = {
        "task-routing.md",
        "package-boundaries.md",
        "environment.md",
        "evidence.md",
        "troubleshooting.md",
    }
    if not child.is_dir():
        blockers.append("missing_rendered_child_skill")
    else:
        required_files = {child / "SKILL.md", child / "agents" / "openai.yaml"}
        required_files.update(child / "references" / name for name in required_shared)
        task_files = {
            child / "references" / output_file
            for task in (spec.get("task_types") or {}).values()
            if isinstance(task, dict)
            for output_file in [str(task.get("output_file") or "")]
            if TASK_FILE_PATTERN.fullmatch(output_file)
        }
        required_files.update(task_files)
        for path in required_files:
            if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                blockers.append(f"missing_or_empty_public_file:{path.relative_to(child)}")

        skill_path = child / "SKILL.md"
        if skill_path.is_file():
            skill_text = skill_path.read_text(encoding="utf-8")
            match = FRONTMATTER_PATTERN.search(skill_text)
            if not match:
                blockers.append("invalid_skill_frontmatter")
            else:
                frontmatter_lines = [
                    line.split(":", 1)[0].strip()
                    for line in match.group(1).splitlines()
                    if ":" in line
                ]
                if set(frontmatter_lines) != {"name", "description"}:
                    blockers.append("frontmatter_fields_not_standard")
            for task_file in task_files:
                relative = task_file.relative_to(child).as_posix()
                if relative not in skill_text:
                    blockers.append(f"task_file_not_linked_from_skill:{relative}")
            for shared_reference in required_shared:
                relative = f"references/{shared_reference}"
                if relative not in skill_text:
                    blockers.append(f"shared_reference_not_linked_from_skill:{relative}")

        metadata_path = child / "agents" / "openai.yaml"
        if metadata_path.is_file():
            metadata = load_yaml(metadata_path)
            interface = metadata.get("interface")
            if not isinstance(interface, dict):
                blockers.append("missing_openai_interface")
            else:
                for field in ("display_name", "short_description", "default_prompt"):
                    if not str(interface.get(field) or "").strip():
                        blockers.append(f"missing_openai_{field}")
                if f"${package_name}" not in str(interface.get("default_prompt") or ""):
                    blockers.append("openai_default_prompt_missing_skill_name")

        for path in child.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if PLACEHOLDER_PATTERN.search(text):
                blockers.append(f"public_placeholder:{path.relative_to(child)}")
            if WINDOWS_PATH_PATTERN.search(text) or POSIX_HOME_PATTERN.search(text):
                blockers.append(f"machine_specific_path:{path.relative_to(child)}")

        allowed_top = {"SKILL.md", "agents", "references", "scripts", "assets"}
        extras = sorted(item.name for item in child.iterdir() if item.name not in allowed_top)
        if extras:
            blockers.append("unexpected_public_top_level:" + ",".join(extras))

    report = {
        **spec_report,
        "status": "pass" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "child_skill": str(child),
    }
    dump_yaml(run_dir / "validation_report.yaml", report)
    return report


def validate_run(run_dir: Path) -> dict[str, Any]:
    """Validate both SkillIR and its rendered child skill."""

    return validate_child(run_dir, validate_spec(run_dir))
