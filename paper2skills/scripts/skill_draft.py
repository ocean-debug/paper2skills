"""Render lightweight scientific-agent-skills style child skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import md_table, slugify, write_text


def render_child_skill(skill_dir: Path, request: dict[str, Any], artifacts: dict[str, Any]) -> None:
    method_name = str(request.get("method_name") or request.get("package_name"))
    slug = slugify(method_name)
    task_catalog = artifacts["task_catalog"]
    source_grounding = artifacts["source_grounding"]
    source_parse_report = artifacts.get("source_parse_report", {})
    source_parsing_coverage = artifacts.get("source_parsing_coverage", {})
    router = artifacts["router"]
    environment_spec = artifacts.get("environment_spec", {})
    environment_install_plan = artifacts.get("environment_install_plan", {})
    resource_inventory = artifacts.get("resource_inventory", {})
    tutorial_catalog = artifacts.get("tutorial_catalog", {})
    tutorial_reproduction_plan = artifacts.get("tutorial_reproduction_plan", {})
    execution_replay_orchestrator = artifacts.get("execution_replay_orchestrator", {})
    evidence_precedence = artifacts.get("evidence_precedence", {})
    task_conflict_matrix = artifacts.get("task_conflict_matrix", {})
    write_text(skill_dir / "SKILL.md", render_skill_md(method_name, slug, task_catalog))
    refs = skill_dir / "references"
    write_text(refs / "task-types.md", render_task_types_md(router, task_conflict_matrix))
    write_text(refs / "input-output-contracts.md", render_io_contracts_md(task_catalog))
    write_text(refs / "limitations-and-refusal.md", render_limitations_md(task_catalog, request, resource_inventory))
    write_text(refs / "validation.md", render_validation_md(task_catalog, environment_install_plan, tutorial_reproduction_plan, execution_replay_orchestrator))
    write_text(refs / "troubleshooting.md", render_troubleshooting_md(request, tutorial_catalog, tutorial_reproduction_plan, resource_inventory, execution_replay_orchestrator))
    write_text(refs / "evidence.md", render_evidence_md(source_grounding, task_catalog, source_parse_report, source_parsing_coverage, evidence_precedence))
    write_text(refs / "environment.md", render_environment_md(request, environment_spec, environment_install_plan, resource_inventory))


def render_skill_md(method_name: str, slug: str, task_catalog: dict[str, Any]) -> str:
    task_rows = []
    for task in task_catalog["tasks"]:
        task_rows.append(
            [
                f"`{task['task_type']}`",
                task["verification_status"],
                "; ".join(task["routing_cues"][:2]),
            ]
        )
    return f"""---
name: {slug}
description: Use {method_name} for evidence-grounded scientific analysis tasks supported by official package sources. Select a task_type first, check input-output contracts, and refuse unsupported inputs.
---

# {method_name}

Use this skill when the user wants to apply `{method_name}` to a task covered by
the official package evidence in `references/evidence.md`.

Do not use this skill for unsupported modalities, missing required metadata,
unconfirmed environment changes, or task types outside `references/task-types.md`.

## Task-Type Routing

Choose a `task_type` before planning execution.

{md_table(["task_type", "status", "routing cues"], task_rows)}

If more than one `task_type` matches, ask for the missing goal, modality, or
metadata distinction. If none match, refuse with the structured template in
`references/limitations-and-refusal.md`.

## Workflow

1. Read `references/task-types.md` to select `task_type`.
2. Read `references/input-output-contracts.md` and confirm required inputs.
3. Read `references/limitations-and-refusal.md` before running or recommending
   the method.
4. Read `references/environment.md` before any installation or execution.
5. Use `references/validation.md` to check expected outputs.
6. Cite `references/evidence.md` when explaining supported boundaries.
7. Read `references/troubleshooting.md` when installation, API drift, data,
   memory, GPU, or tutorial reproduction issues appear.

## Verification Rule

`source_grounded` means the task is supported by official sources but has not
been execution-verified by Papert2Skills. Only `execution_verified` task types
have supplied execution evidence.
"""


def render_task_types_md(router: dict[str, Any], task_conflict_matrix: dict[str, Any] | None = None) -> str:
    rows = []
    for route in router["routes"]:
        rows.append(
            [
                f"`{route['task_type']}`",
                route["verification_status"],
                "; ".join(route["choose_when"]),
                "; ".join(route["ask_when"]),
                ", ".join(route["evidence_refs"]),
            ]
        )
    conflict_rows = []
    if task_conflict_matrix:
        for pair in task_conflict_matrix.get("pairs", [])[:20]:
            conflict_rows.append(
                [
                    f"`{pair['task_type_a']}` vs `{pair['task_type_b']}`",
                    pair["conflict_level"],
                    pair["selection_rule"],
                ]
            )
    conflict_text = ""
    if conflict_rows:
        conflict_text = "\n## Conflict Matrix\n\n" + md_table(["pair", "level", "selection rule"], conflict_rows) + "\n"
    return f"""# Task Types

This package is represented as one child skill. Capabilities are selected by
`task_type`, not by switching to separate capability skills.

{md_table(["task_type", "status", "choose when", "ask when", "evidence"], rows)}
{conflict_text}

## Routing Order

1. Match the user's goal to a candidate `task_type`.
2. Check input modality and file format.
3. Check required metadata roles and parameters.
4. Prefer `execution_verified` over `source_grounded` if both match.
5. Ask when ambiguity remains.
6. Refuse when the request is outside evidence-backed boundaries.
"""


def render_io_contracts_md(task_catalog: dict[str, Any]) -> str:
    parts = ["# Input-Output Contracts\n"]
    parts.append("Contracts are evidence-bounded. Unknown package-specific fields must be confirmed from official tutorials, docs, or source API before execution.\n")
    for task in task_catalog["tasks"]:
        input_contract = task["input_contract"]
        output_contract = task["output_contract"]
        parts.append(f"## `{task['task_type']}`\n")
        parts.append("### Required From User\n")
        for item in input_contract["required_from_user"]:
            parts.append(f"- {item}")
        parts.append("\n### Must Confirm\n")
        for item in input_contract["must_confirm"]:
            parts.append(f"- {item}")
        if input_contract.get("evidence_observed"):
            parts.append("\n### Parsed Input Evidence\n")
            for item in input_contract["evidence_observed"]:
                parts.append(f"- {item['summary']} ({item['evidence_ref']})")
        if input_contract.get("parameter_constraints_observed"):
            parts.append("\n### Parsed Parameter Constraints\n")
            for item in input_contract["parameter_constraints_observed"]:
                roles = ", ".join(item.get("semantic_roles", [])) or "unspecified"
                branch_values = item.get("branch_values") or []
                branch_text = f"; observed branch values: {branch_values}" if branch_values else ""
                default = item.get("default")
                default_text = f"; default: {default}" if default is not None else ""
                required_text = "required" if item.get("required") else "optional"
                parts.append(
                    f"- `{item['name']}` ({required_text}; roles: {roles}{default_text}{branch_text}) from `{item['signature']}`"
                )
        if input_contract.get("review_note"):
            parts.append(f"\nReview note: {input_contract['review_note']}\n")
        parts.append("\n### Expected Outputs\n")
        for item in output_contract["expected_outputs"]:
            parts.append(f"- {item}")
        parts.append("\n### Minimum Validation\n")
        for item in output_contract["minimum_validation"]:
            parts.append(f"- {item}")
        if output_contract.get("evidence_observed"):
            parts.append("\n### Parsed Output Evidence\n")
            for item in output_contract["evidence_observed"]:
                parts.append(f"- {item['summary']} ({item['evidence_ref']})")
        if output_contract.get("api_entrypoints_observed"):
            parts.append("\n### Parsed API Entrypoints\n")
            for item in output_contract["api_entrypoints_observed"]:
                parts.append(f"- {item['summary']} ({item['evidence_ref']})")
        if output_contract.get("interface_observed"):
            parts.append("\n### Parsed Interface Hints\n")
            for item in output_contract["interface_observed"]:
                branch_values = item.get("branch_parameter_values") or {}
                branch_text = f"; branch values: {branch_values}" if branch_values else ""
                doc_text = f"; {item['docstring_summary']}" if item.get("docstring_summary") else ""
                parts.append(f"- `{item['signature']}` from {item['source_path']}{doc_text}{branch_text}")
        if output_contract.get("validation_observed"):
            parts.append("\n### Parsed Validation Hints\n")
            for item in output_contract["validation_observed"]:
                parts.append(f"- {item['summary']} ({item['evidence_ref']})")
        if output_contract.get("review_note"):
            parts.append(f"\nReview note: {output_contract['review_note']}\n")
        parts.append(f"\nEvidence refs: {', '.join(task['evidence_refs'])}\n")
    return "\n".join(parts)


def render_limitations_md(
    task_catalog: dict[str, Any],
    request: dict[str, Any],
    resource_inventory: dict[str, Any] | None = None,
) -> str:
    parts = ["# Limitations And Refusal\n"]
    parts.append("Refusal is a core feature. Do not continue when the request is outside the package evidence or required inputs are missing.\n")
    parts.append("## Common Refusal Cases\n")
    seen = set()
    for task in task_catalog["tasks"]:
        for boundary in task["refusal_boundaries"]:
            key = boundary["reason_key"]
            if key in seen:
                continue
            seen.add(key)
            parts.append(f"- `{key}` ({boundary['refusal_type']}): {boundary['when']}")
    if request.get("language_backend") != "python":
        parts.append("- `backend_not_implemented` (unsupported): Python is supported first; R is an extension point.")
    resource_inventory = resource_inventory or {}
    if resource_inventory.get("resource_count", 0):
        parts.append("- `missing_model_or_data_resource` (fixable): Required model, checkpoint, or data resource is unavailable, unapproved, gated, licensed, token-protected, or would require an implicit download.")
        parts.append("- `resource_access_not_confirmed` (fixable): Resource permission, license, login, token, or large-download approval has not been confirmed.")
    parts.append(
        """
## Structured Refusal Template

```yaml
status: refused
refusal_type: fixable_or_unsupported
reason_key: missing_required_input
human_message: "Explain the problem in one sentence."
missing_field: null
expected: null
observed: null
suggested_fix: "Ask for the exact missing field or suggest rebuilding with official evidence."
evidence_refs: []
```
"""
    )
    return "\n".join(parts)


def render_validation_md(
    task_catalog: dict[str, Any],
    environment_install_plan: dict[str, Any] | None = None,
    tutorial_reproduction_plan: dict[str, Any] | None = None,
    execution_replay_orchestrator: dict[str, Any] | None = None,
) -> str:
    rows = []
    for task in task_catalog["tasks"]:
        rows.append(
            [
                f"`{task['task_type']}`",
                task["verification_status"],
                "; ".join(task["output_contract"]["minimum_validation"]),
                task.get("trace_ref") or "none",
            ]
        )
    environment_install_plan = environment_install_plan or {}
    tutorial_reproduction_plan = tutorial_reproduction_plan or {}
    execution_replay_orchestrator = execution_replay_orchestrator or {}
    install_text = ""
    if environment_install_plan:
        missing = environment_install_plan.get("missing_environment_fields", [])
        missing_text = ", ".join(missing) if missing else "none"
        install_text = f"""
## Environment Install Boundary

- Plan status: {environment_install_plan.get("status")}
- Plan only: {environment_install_plan.get("plan_only")}
- Install strategy: {environment_install_plan.get("install_strategy")}
- Missing environment fields: {missing_text}
- User approval required: {environment_install_plan.get("requires_user_approval")}

Installation success does not verify a task_type. A matching successful
execution trace is still required before changing any task to execution_verified.
"""
    replay_rows = []
    for replay in tutorial_reproduction_plan.get("replays", []):
        replay_rows.append(
            [
                f"`{replay.get('task_type')}`",
                replay.get("status"),
                str(len(replay.get("tutorial_replay_sources", []))),
                "; ".join(replay.get("success_criteria", [])[:2]),
            ]
        )
    replay_text = ""
    if replay_rows:
        replay_text = "\n## Tutorial Replay Plan\n\n" + md_table(
            ["task_type", "plan status", "source count", "success criteria"],
            replay_rows,
        ) + "\n"
    job_rows = []
    for job in execution_replay_orchestrator.get("jobs", []):
        job_rows.append(
            [
                f"`{job.get('task_type')}`",
                job.get("status"),
                ", ".join(job.get("blocked_reasons", [])) or "none",
                "; ".join(job.get("success_criteria", [])[:2]),
            ]
        )
    job_text = ""
    if job_rows:
        job_text = "\n## Replay Job Queue\n\n" + md_table(
            ["task_type", "job status", "blocked reasons", "success criteria"],
            job_rows,
        ) + "\n"
    return f"""# Validation

Technical validation should be strict about file existence and format. Biological
sanity checks should be warnings unless official evidence defines them as hard
requirements.

{md_table(["task_type", "status", "minimum checks", "trace"], rows)}

## Preflight

- Confirm selected `task_type`.
- Confirm input files exist and formats match official evidence.
- Confirm required metadata roles are present and semantically correct.
- Confirm environment changes are approved before installation.

## Output Checks

- Required outputs exist.
- Output formats open with documented readers.
- Required result fields are present when evidence specifies them.
- Warnings are reported for biological surprises that are not hard evidence
  violations.
{install_text}
{replay_text}
{job_text}
"""


def render_troubleshooting_md(
    request: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any] | None = None,
    resource_inventory: dict[str, Any] | None = None,
    execution_replay_orchestrator: dict[str, Any] | None = None,
) -> str:
    backend = request.get("language_backend", "python")
    tutorial_note = "No static tutorial steps were mined."
    if tutorial_catalog.get("tutorial_count"):
        tutorial_note = f"{tutorial_catalog['tutorial_count']} static tutorial/example source(s) were mined; compare failures against their step order."
    tutorial_reproduction_plan = tutorial_reproduction_plan or {}
    replay_rows = []
    for replay in tutorial_reproduction_plan.get("replays", []):
        replay_rows.append(
            [
                f"`{replay.get('task_type')}`",
                replay.get("status"),
                "; ".join(replay.get("refusal_if_missing", [])[:3]),
            ]
        )
    replay_text = ""
    if replay_rows:
        replay_text = "\n### Replay Boundaries\n\n" + md_table(["task_type", "status", "refuse if missing"], replay_rows)
    resource_inventory = resource_inventory or {}
    execution_replay_orchestrator = execution_replay_orchestrator or {}
    replay_result_rows = []
    for record in execution_replay_orchestrator.get("result_records", []):
        replay_result_rows.append(
            [
                f"`{record.get('task_type')}`",
                record.get("status"),
                ", ".join(record.get("missing_fields", [])) or "none",
                "yes" if record.get("has_failure_reason") else "no",
            ]
        )
    replay_result_text = ""
    if replay_result_rows:
        replay_result_text = "\n### Replay Result Notes\n\n" + md_table(
            ["task_type", "status", "missing fields", "failure reason"],
            replay_result_rows,
        )
    resource_text = ""
    if resource_inventory.get("resource_count", 0):
        risk_counts = resource_inventory.get("risk_counts", {})
        resource_text = f"""
## Resource Boundaries

- Resource mentions mined: {resource_inventory.get("resource_count", 0)}
- Resource risks: {risk_counts}
- Do not download model weights, checkpoints, datasets, or registry snapshots
  without explicit user approval.
- Refuse or ask for confirmation when permission, license, login, token, or
  large-download requirements are unresolved.
"""
    return f"""# Troubleshooting

## Environment

- Do not install dependencies silently.
- Prefer the user-selected environment.
- Record any installation or version pin before execution.
- Backend requested during build: `{backend}`.

## Data

- Check that file paths exist.
- Check that the data modality matches the selected `task_type`.
- Check that metadata columns have the intended biological meaning.

## API Drift

- Prefer official documented APIs.
- If source APIs have changed, record the mismatch and use adapter-level
  guidance only after review.
- Do not patch upstream source or site-packages silently.

## Tutorial Reproduction

- {tutorial_note}
- Treat mined tutorial steps as source guidance, not execution verification.
{replay_text}
{replay_result_text}
{resource_text}

## Memory Or GPU

- Treat GPU and memory requirements as environment constraints.
- Ask before moving execution to another host, node, or environment.
"""


def render_evidence_md(
    source_grounding: dict[str, Any],
    task_catalog: dict[str, Any],
    source_parse_report: dict[str, Any] | None = None,
    source_parsing_coverage: dict[str, Any] | None = None,
    evidence_precedence: dict[str, Any] | None = None,
) -> str:
    rows = []
    for source in source_grounding["sources"]:
        rows.append(
            [
                source["evidence_id"],
                source["type"],
                source["priority"],
                source["uri"],
            ]
        )
    task_rows = []
    for task in task_catalog["tasks"]:
        task_rows.append(
            [
                f"`{task['task_type']}`",
                task["verification_status"],
                ", ".join(task["evidence_refs"]),
                task.get("trace_ref") or "none",
            ]
        )
    source_parse_report = source_parse_report or {}
    source_parsing_coverage = source_parsing_coverage or {}
    evidence_precedence = evidence_precedence or {}
    capability_rows = []
    for row in source_parse_report.get("capability_matrix", []):
        capability_rows.append(
            [
                row.get("kind"),
                row.get("parser"),
                row.get("backend_support"),
                "yes" if row.get("can_ground_contract") else "no",
                "yes" if row.get("can_verify_execution") else "no",
            ]
        )
    capability_text = ""
    if capability_rows:
        capability_text = "\n## Parser Capability Matrix\n\n" + md_table(
            ["source kind", "parser", "backend status", "contract hints", "execution verified"],
            capability_rows,
        ) + "\n"
    coverage_text = ""
    if source_parsing_coverage:
        coverage_text = f"""
## Source Parsing Coverage

- Status: {source_parsing_coverage.get("status")}
- Indexed files: {source_parsing_coverage.get("indexed_file_count", 0)}
- Parseable files: {source_parsing_coverage.get("parseable_file_count", 0)}
- API candidates: {source_parsing_coverage.get("api_candidate_count", 0)}
- Interfaces: {source_parsing_coverage.get("interface_count", 0)}
- Tutorial sources: {source_parsing_coverage.get("tutorial_count", 0)}
"""
    precedence_rows = []
    for item in evidence_precedence.get("tasks", []):
        precedence_rows.append(
            [
                f"`{item.get('task_type')}`",
                item.get("verification_status"),
                item.get("best_priority") or "none",
                ", ".join(item.get("accepted_refs", [])) or "none",
            ]
        )
    precedence_text = ""
    if precedence_rows:
        precedence_text = "\n## Evidence Precedence By Task\n\n" + md_table(
            ["task_type", "status", "accepted source", "accepted refs"],
            precedence_rows,
        ) + "\n"
    return f"""# Evidence

Evidence priority:

```text
execution trace > official tutorials/docs > source code/API > paper
```

## Sources

{md_table(["evidence_id", "type", "priority", "uri"], rows)}

## Task Evidence

{md_table(["task_type", "status", "evidence_refs", "trace_ref"], task_rows)}
{capability_text}
{coverage_text}
{precedence_text}

Long source excerpts and full execution logs are intentionally not stored in
this public child skill.
"""


def render_environment_md(
    request: dict[str, Any],
    environment_spec: dict[str, Any],
    environment_install_plan: dict[str, Any] | None = None,
    resource_inventory: dict[str, Any] | None = None,
) -> str:
    backend = request.get("language_backend", "python")
    if backend == "python":
        backend_text = "Python is the currently supported backend."
    else:
        backend_text = "This backend is reserved as an extension point and is not implemented yet."
    dependencies = environment_spec.get("declared_dependencies", [])[:40]
    imports = environment_spec.get("imported_modules", [])[:40]
    gpu_hints = environment_spec.get("gpu_hints", [])
    dependency_text = "\n".join(f"- {item}" for item in dependencies) or "- none mined"
    import_text = "\n".join(f"- {item}" for item in imports) or "- none mined"
    gpu_text = ", ".join(gpu_hints) if gpu_hints else "none mined"
    environment_install_plan = environment_install_plan or {}
    resource_inventory = resource_inventory or {}
    install_section = ""
    if environment_install_plan:
        missing = environment_install_plan.get("missing_environment_fields", [])
        missing_text = ", ".join(missing) if missing else "none"
        steps = "\n".join(f"- {item}" for item in environment_install_plan.get("planned_steps", [])) or "- Ask for authoritative install instructions."
        refusals = "\n".join(f"- {item}" for item in environment_install_plan.get("refusal_if_missing", [])) or "- explicit approval"
        install_section = f"""
## Install Plan Boundary

- Status: {environment_install_plan.get("status")}
- Plan only: {environment_install_plan.get("plan_only")}
- Install strategy: {environment_install_plan.get("install_strategy")}
- Missing environment fields: {missing_text}
- User approval required: {environment_install_plan.get("requires_user_approval")}

### Planned Steps

{steps}

### Refuse Installation Or Execution If Missing

{refusals}
"""
    resource_rows = []
    for item in resource_inventory.get("resources", [])[:40]:
        resource_rows.append(
            [
                item.get("resource_type", "unknown"),
                item.get("identifier", "unknown"),
                ", ".join(item.get("risk_flags", [])) or "none",
                item.get("source_path", "unknown"),
            ]
        )
    resource_section = ""
    if resource_rows:
        resource_section = "\n## Resource Boundaries\n\n" + md_table(
            ["type", "identifier", "risk flags", "source"],
            resource_rows,
        ) + """

Do not download model weights, checkpoints, datasets, registry snapshots, or
other external resources without explicit user approval. Refuse execution when
required permission, license, login, token, or large-download approval is
missing.
"""
    return f"""# Environment

Backend requested at build time: `{backend}`.

{backend_text}

## Static Dependency Hints

Declared dependencies:

{dependency_text}

Imported modules:

{import_text}

GPU-related hints: {gpu_text}
{install_section}
{resource_section}

## Policy

- Do not install dependencies silently.
- Ask before creating or modifying environments.
- Record package versions and install commands when execution is attempted.
- Treat execution verification as absent unless validated execution evidence exists.

## R Backend

R support is reserved for a future backend extension. R-only workflows should
produce a structured `backend_not_implemented` refusal until that backend is implemented.
"""
