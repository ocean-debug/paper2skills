"""Render one public Codex child skill from a Paper2Skills SkillIR."""

from __future__ import annotations

import shutil
import re
from pathlib import Path
from typing import Any

from common import (
    Paper2SkillsError,
    as_list,
    ensure_within,
    load_yaml,
    slugify,
    unique_strings,
    write_text,
)


TASK_FILE_PATTERN = re.compile(r"^task-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value)
    return str(value).strip()


def _bullets(values: Any, empty: str = "Not confirmed in official evidence.") -> str:
    items = [_text(item) for item in as_list(values) if _text(item)]
    if not items:
        items = [empty]
    return "\n".join(f"- {item}" for item in items)


def _numbered(values: Any, empty: str = "Not confirmed in official evidence.") -> str:
    items = [_text(item) for item in as_list(values) if _text(item)]
    if not items:
        items = [empty]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


def _api_sequence(values: Any) -> str:
    rendered: list[str] = []
    for index, item in enumerate(as_list(values), 1):
        if not isinstance(item, dict):
            rendered.append(f"{index}. {_text(item)}")
            continue
        api = str(item.get("api") or "API not confirmed")
        action = str(item.get("action") or "Action not confirmed")
        evidence_ids = ", ".join(unique_strings(as_list(item.get("evidence_ids"))))
        rendered.append(
            f"{index}. `{api}` - {action}"
            + (f" Evidence: {evidence_ids}." if evidence_ids else "")
        )
    return "\n".join(rendered) or "1. Not confirmed in official evidence."


def _frontmatter(name: str, description: str) -> str:
    clean_description = " ".join(description.split()).replace('"', "'")
    return f'---\nname: {name}\ndescription: "{clean_description}"\n---'


def render_child(run_dir: Path) -> Path:
    """Render the run SkillIR to one clean run-local child skill directory."""

    spec = load_yaml(run_dir / "skill_spec.yaml")
    evidence_doc = load_yaml(run_dir / "evidence.yaml")
    package = spec.get("package")
    tasks = spec.get("task_types")
    if not isinstance(package, dict) or not isinstance(tasks, dict):
        raise Paper2SkillsError("skill_spec.yaml requires package and task_types mappings")

    package_name = slugify(str(package.get("name") or ""))
    child_root = ensure_within(run_dir, run_dir / "child_skill", "child skill root")
    child_dir = ensure_within(child_root, child_root / package_name, "child skill")
    if child_dir.exists():
        shutil.rmtree(child_dir)
    references = child_dir / "references"
    agents = child_dir / "agents"
    references.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)

    task_files: list[tuple[str, str, dict[str, Any]]] = []
    for task_type, task in tasks.items():
        if not isinstance(task, dict):
            continue
        output_file = str(task.get("output_file") or f"task-{slugify(task_type)}.md")
        if not TASK_FILE_PATTERN.fullmatch(output_file):
            raise Paper2SkillsError(
                f"Task {task_type!r} has an unsafe output_file: {output_file!r}"
            )
        task_files.append((str(task_type), output_file, task))

    write_text(child_dir / "SKILL.md", _render_skill(spec, task_files))
    write_text(references / "task-routing.md", _render_routing(spec, task_files))
    for task_type, output_file, task in task_files:
        task_path = ensure_within(
            references, references / output_file, f"task file for {task_type}"
        )
        write_text(task_path, _render_task(task_type, task))
    write_text(
        references / "package-boundaries.md",
        _render_boundaries(spec),
    )
    write_text(references / "environment.md", _render_environment(spec))
    write_text(
        references / "evidence.md",
        _render_evidence(spec, evidence_doc.get("evidence", [])),
    )
    write_text(
        references / "troubleshooting.md",
        _render_troubleshooting(spec),
    )
    write_text(agents / "openai.yaml", _render_openai(spec))
    return child_dir


def _render_skill(
    spec: dict[str, Any], task_files: list[tuple[str, str, dict[str, Any]]]
) -> str:
    package = spec["package"]
    name = slugify(str(package.get("name") or ""))
    display_name = str(package.get("display_name") or name)
    description = str(
        package.get("description")
        or f"Use {display_name} for its evidence-grounded analysis tasks."
    )
    lines = [
        _frontmatter(name, description),
        "",
        f"# {display_name}",
        "",
        "Select one evidence-grounded `task_type`, check its prerequisites, execute",
        "only grounded APIs, validate outputs, and remain inside the stated biological",
        "interpretation boundary.",
        "",
        "## Select a Task",
        "",
    ]
    for task_type, output_file, task in task_files:
        intent = _text(as_list(task.get("intent"))[:1]) or task_type
        lines.append(
            f"- `{task_type}` - {intent} Read [its task contract](references/{output_file})."
        )
    lines.extend(
        [
            "",
            "If the request matches more than one task or lacks task-defining metadata,",
            "read [task routing](references/task-routing.md) and ask for the missing",
            "distinction. If no task matches, refuse using",
            "[package boundaries](references/package-boundaries.md).",
            "",
            "## Execution Discipline",
            "",
            "1. Select one task before proposing commands or code.",
            "2. Read only that task file plus shared references needed for the request.",
            "3. Run its input and metadata preflight before using the package.",
            "4. Follow the grounded API sequence; do not substitute another method.",
            "5. Perform technical validation before biological interpretation.",
            "6. Refuse unsupported input or claims with the task's evidence-backed reason.",
            "",
            "Read [environment guidance](references/environment.md) before installation",
            "or execution. Read [evidence](references/evidence.md) when checking a claim",
            "or resolving version conflicts. Read",
            "[troubleshooting](references/troubleshooting.md) only for relevant failures.",
        ]
    )
    return "\n".join(lines)


def _render_routing(
    spec: dict[str, Any], task_files: list[tuple[str, str, dict[str, Any]]]
) -> str:
    routing = spec.get("routing") if isinstance(spec.get("routing"), dict) else {}
    lines = ["# Task Routing", "", "## Task Map", ""]
    for task_type, output_file, task in task_files:
        lines.extend(
            [
                f"### `{task_type}`",
                "",
                f"Task file: [{output_file}]({output_file})",
                "",
                "Select when:",
                _bullets(task.get("selection_rules")),
                "",
                "Do not select when:",
                _bullets(task.get("do_not_select")),
                "",
            ]
        )
    lines.extend(
        [
            "## Aliases",
            "",
            _bullets(
                [
                    f"{alias} -> `{task}`"
                    for alias, task in (routing.get("aliases") or {}).items()
                ]
            ),
            "",
            "## Ambiguity Rules",
            "",
            _bullets(routing.get("ambiguity_rules"), str(routing.get("disjoint_task_reason") or "No ambiguity rule was confirmed.")),
            "",
            "## Unsupported Requests",
            "",
            _bullets(routing.get("unsupported_cases")),
        ]
    )
    return "\n".join(lines)


def _render_task(task_type: str, task: dict[str, Any]) -> str:
    status = str(task.get("verification_status") or "source_grounded")
    evidence = ", ".join(unique_strings(as_list(task.get("evidence_ids"))))
    sections = [
        ("Select This Task", _bullets(task.get("selection_rules"))),
        ("Do Not Select This Task", _bullets(task.get("do_not_select"))),
        ("Accepted Inputs", _bullets(task.get("accepted_inputs"))),
        ("Required Metadata", _bullets(task.get("required_metadata"))),
        ("Preflight Checks", _bullets(task.get("preflight_checks"))),
        ("Recommended Workflow", _numbered(task.get("workflow"))),
        ("Grounded API Sequence", _api_sequence(task.get("api_sequence"))),
        ("Parameters and Defaults", _bullets(task.get("parameters"))),
        ("Expected Outputs", _bullets(task.get("expected_outputs"))),
        ("Refusal Rules", _bullets(task.get("refusal_rules"))),
        ("Technical Validation", _bullets(task.get("technical_validation"))),
        ("Biological Interpretation Boundary", _bullets(task.get("biological_boundaries"))),
        ("Reuse Contract", _bullets(task.get("reuse_contract"))),
        ("Task-Specific Troubleshooting", _bullets(task.get("troubleshooting"))),
    ]
    lines = [
        f"# {task_type.replace('_', ' ').title()}",
        "",
        f"Verification status: `{status}`",
        "",
        "## Intent",
        "",
        _bullets(task.get("intent")),
        "",
    ]
    for heading, content in sections:
        lines.extend([f"## {heading}", "", content, ""])
    lines.extend(
        [
            "## Evidence",
            "",
            evidence or "No evidence ID was supplied.",
        ]
    )
    if as_list(task.get("execution_evidence")):
        lines.extend(
            [
                "",
                "## Execution Evidence",
                "",
                _bullets(task.get("execution_evidence")),
            ]
        )
    return "\n".join(lines)


def _render_boundaries(spec: dict[str, Any]) -> str:
    package = spec["package"]
    return "\n".join(
        [
            "# Package Boundaries",
            "",
            f"These boundaries apply to every `{package.get('name')}` task.",
            "",
            _bullets(spec.get("package_boundaries")),
            "",
            "Refuse unsupported requests without silently switching methods, modalities,",
            "species, metadata semantics, or language backends.",
        ]
    )


def _render_environment(spec: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Environment",
            "",
            _bullets(spec.get("shared_environment")),
            "",
            "Do not infer a host, environment, execution node, core count, package",
            "version, GPU, model weight, or external resource permission. Require the",
            "user to provide unresolved execution constraints.",
        ]
    )


def _render_evidence(spec: dict[str, Any], evidence: Any) -> str:
    used = {
        item
        for task in (spec.get("task_types") or {}).values()
        if isinstance(task, dict)
        for item in unique_strings(as_list(task.get("evidence_ids")))
    }
    lines = [
        "# Evidence",
        "",
        "Priority: official tutorial/example > current source/API/test > official",
        "documentation/repository guidance > paper Methods/supplement > abstract.",
        "",
    ]
    records = [item for item in as_list(evidence) if isinstance(item, dict)]
    for item in records:
        evidence_id = str(item.get("id") or "")
        marker = "used" if evidence_id in used else "available"
        summary = str(item.get("summary") or item.get("claim_type") or "Evidence record")
        location = str(item.get("public_location") or item.get("location") or "unresolved")
        if re.search(r"\b[A-Za-z]:\\", location) or location.startswith(("/home/", "/Users/")):
            location = "local source retained in the private build evidence"
        lines.append(f"- `{evidence_id}` ({marker}, {item.get('kind')}): {summary} - {location}")
    if not records:
        lines.append("- No evidence record was supplied.")
    lines.extend(
        [
            "",
            "Static evidence supports `source_grounded` claims only. External URLs",
            "registered but not inspected cannot support a task claim.",
        ]
    )
    return "\n".join(lines)


def _render_troubleshooting(spec: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Troubleshooting",
            "",
            _bullets(spec.get("shared_troubleshooting")),
            "",
            "Record version conflicts and failed execution evidence. Do not convert a",
            "failed run into a verified claim or silently replace the package API.",
        ]
    )


def _render_openai(spec: dict[str, Any]) -> str:
    package = spec["package"]
    name = slugify(str(package.get("name") or ""))
    display_name = " ".join(str(package.get("display_name") or name).split()).replace('"', "'")
    short_description = f"Use {display_name} with grounded task contracts"[:64].rstrip()
    return "\n".join(
        [
            "interface:",
            f'  display_name: "{display_name}"',
            f'  short_description: "{short_description}"',
            f'  default_prompt: "Use ${name} to select and execute the appropriate evidence-grounded task for my data."',
        ]
    )
