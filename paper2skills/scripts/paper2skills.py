#!/usr/bin/env python3
"""Paper2Skills MVP command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from common import (
    REQUEST_SCHEMA,
    SKILLIR_SCHEMA,
    STATE_SCHEMA,
    Paper2SkillsError,
    append_event,
    as_list,
    dump_yaml,
    ensure_within,
    load_yaml,
    require_schema,
    resolve_run_dir,
    slugify,
    timestamp,
)
from patching import apply_proposal
from rendering import render_child
from source_grounding import collect_grounding
from validation import validate_run


VERSION = "1.0.0"
SKILL_ROOT = Path(__file__).resolve().parents[1]


def _request_errors(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if request.get("schema_version") != REQUEST_SCHEMA:
        errors.append(f"schema_version must be {REQUEST_SCHEMA}")
    for field in ("package_name", "display_name", "output_dir"):
        if not str(request.get(field) or "").strip():
            errors.append(f"missing {field}")
    if not str(request.get("repo_url") or "").strip() and not as_list(
        request.get("source_paths")
    ):
        errors.append("provide repo_url or source_paths")
    if str(request.get("language_backend") or "python") != "python":
        errors.append("MVP supports language_backend: python only")
    if str(request.get("target_agent") or "codex") != "codex":
        errors.append("MVP supports target_agent: codex only")
    return errors


def _initial_spec(request: dict[str, Any]) -> dict[str, Any]:
    package_name = slugify(str(request["package_name"]))
    display_name = str(request.get("display_name") or package_name)
    return {
        "schema_version": SKILLIR_SCHEMA,
        "package": {
            "name": package_name,
            "display_name": display_name,
            "description": (
                f"Use {display_name} for its evidence-grounded bioinformatics "
                "analysis tasks, including task selection, input refusal, "
                "execution guidance, output validation, and reuse."
            ),
            "source_revision": str(
                request.get("source_revision") or "unresolved"
            ),
        },
        "shared_environment": [
            "Python environment requirements are not yet confirmed in official evidence."
        ],
        "package_boundaries": [
            "Refuse tasks outside capabilities confirmed by official package evidence."
        ],
        "shared_troubleshooting": [
            "No shared runtime issue has been confirmed by execution evidence."
        ],
        "task_types": {},
        "routing": {
            "aliases": {},
            "ambiguity_rules": [],
            "disjoint_task_reason": None,
            "unsupported_cases": [
                "Refuse requests outside grounded package capabilities."
            ],
        },
    }


def cmd_init(args: argparse.Namespace) -> int:
    request_path = Path(args.request).expanduser().resolve()
    request = load_yaml(request_path)
    errors = _request_errors(request)
    if errors:
        raise Paper2SkillsError("Invalid build request: " + "; ".join(errors))

    if args.out:
        run_dir = resolve_run_dir(args.out)
    else:
        requested_output = Path(str(request.get("output_dir"))).expanduser()
        run_dir = (
            requested_output.resolve()
            if requested_output.is_absolute()
            else (request_path.parent / requested_output).resolve()
        )
    if run_dir.exists() and any(run_dir.iterdir()):
        raise Paper2SkillsError(
            f"Run directory is not empty: {run_dir}. Choose a new run directory."
        )
    try:
        run_dir.relative_to(SKILL_ROOT)
    except ValueError:
        pass
    else:
        raise Paper2SkillsError(
            f"Run output must stay outside the installed skill directory: {SKILL_ROOT}"
        )
    run_dir.mkdir(parents=True, exist_ok=True)

    normalized = dict(request)
    normalized["package_name"] = slugify(str(request["package_name"]))
    normalized["output_dir"] = str(run_dir)
    normalized.setdefault("source_revision", "unresolved")
    normalized.setdefault("source_paths", [])
    normalized.setdefault("tutorial_paths", [])
    normalized.setdefault("tutorial_urls", [])
    normalized.setdefault("documentation_urls", [])
    normalized.setdefault("paper_urls", [])
    normalized.setdefault("key_apis", [])
    normalized.setdefault("target_agent", "codex")
    normalized.setdefault("language_backend", "python")
    normalized.setdefault("max_files", 500)
    normalized.setdefault("max_file_bytes", 250_000)
    for path_field in ("source_paths", "tutorial_paths"):
        normalized[path_field] = [
            str(
                candidate.resolve()
                if candidate.is_absolute()
                else (request_path.parent / candidate).resolve()
            )
            for item in as_list(normalized.get(path_field))
            for candidate in [Path(str(item)).expanduser()]
        ]

    dump_yaml(run_dir / "request.yaml", normalized)
    dump_yaml(run_dir / "skill_spec.yaml", _initial_spec(normalized))
    dump_yaml(
        run_dir / "evidence.yaml",
        {"schema_version": "paper2skills.evidence.v1", "evidence": []},
    )
    dump_yaml(
        run_dir / "state.yaml",
        {
            "schema_version": STATE_SCHEMA,
            "builder_version": VERSION,
            "status": "initialized",
            "next_action": "ground",
            "created_at": timestamp(),
            "package_name": normalized["package_name"],
        },
    )
    append_event(run_dir, "initialized", request=str(request_path))
    print(run_dir)
    return 0


def cmd_ground(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    report = collect_grounding(run_dir)
    state = load_yaml(run_dir / "state.yaml")
    state.update(
        {
            "status": "grounded",
            "next_action": "agent_contract_synthesis",
            "grounded_at": timestamp(),
            "evidence_count": len(report.get("evidence", [])),
        }
    )
    dump_yaml(run_dir / "state.yaml", state)
    append_event(
        run_dir,
        "grounded",
        evidence_count=len(report.get("evidence", [])),
        indexed_file_count=len(report.get("indexed_files", [])),
    )
    print(run_dir / "agent_packet.md")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    child = render_child(run_dir)
    state = load_yaml(run_dir / "state.yaml")
    state.update(
        {
            "status": "rendered",
            "next_action": "validate",
            "rendered_at": timestamp(),
            "child_skill": str(child),
        }
    )
    dump_yaml(run_dir / "state.yaml", state)
    append_event(run_dir, "rendered", child_skill=str(child))
    print(child)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    report = validate_run(run_dir)
    state = load_yaml(run_dir / "state.yaml")
    state.update(
        {
            "status": "validated" if report["status"] == "pass" else "blocked",
            "next_action": "publish" if report["status"] == "pass" else "revise",
            "validated_at": timestamp(),
            "validation_status": report["status"],
        }
    )
    dump_yaml(run_dir / "state.yaml", state)
    append_event(run_dir, "validated", status=report["status"], blockers=report["blockers"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 2


def cmd_apply_patch(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    result = apply_proposal(run_dir, Path(args.proposal).expanduser().resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "applied" else 2


def cmd_publish(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    report = validate_run(run_dir)
    if report["status"] != "pass":
        raise Paper2SkillsError(
            "Publish blocked: " + "; ".join(report.get("blockers", []))
        )
    spec = load_yaml(run_dir / "skill_spec.yaml")
    package_name = slugify(str(spec["package"]["name"]))
    child = ensure_within(
        run_dir, run_dir / "child_skill" / package_name, "child skill"
    )
    published_root = ensure_within(run_dir, run_dir / "published", "published root")
    target = ensure_within(
        published_root, published_root / package_name, "published skill"
    )
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(child, target)
    manifest = {
        "schema_version": "paper2skills.publish.v1",
        "builder_version": VERSION,
        "package_name": package_name,
        "source_revision": spec["package"].get("source_revision"),
        "task_types": sorted((spec.get("task_types") or {}).keys()),
        "published_skill": str(target),
        "published_at": timestamp(),
        "validation_status": report["status"],
        "installation_performed": False,
    }
    dump_yaml(run_dir / "publish_manifest.yaml", manifest)
    state = load_yaml(run_dir / "state.yaml")
    state.update(
        {
            "status": "published",
            "next_action": "optional_execution_or_user_install",
            "published_at": manifest["published_at"],
            "published_skill": str(target),
        }
    )
    dump_yaml(run_dir / "state.yaml", state)
    append_event(run_dir, "published", published_skill=str(target))
    print(target)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    run_dir = _existing_run(args.run)
    state = load_yaml(run_dir / "state.yaml")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


def _existing_run(path: str) -> Path:
    run_dir = resolve_run_dir(path)
    if not run_dir.is_dir():
        raise Paper2SkillsError(f"Run directory does not exist: {run_dir}")
    for required in ("request.yaml", "skill_spec.yaml", "state.yaml"):
        if not (run_dir / required).is_file():
            raise Paper2SkillsError(f"Run is missing {required}: {run_dir}")
    state = load_yaml(run_dir / "state.yaml")
    require_schema(state, STATE_SCHEMA, "run state")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper2skills",
        description="Build one evidence-grounded Codex skill per bioinformatics package.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Initialize a run from a build request")
    init.add_argument("--request", required=True)
    init.add_argument("--out")
    init.set_defaults(handler=cmd_init)

    for name, help_text, handler in (
        ("ground", "Statically ground local sources and register official URLs", cmd_ground),
        ("render", "Render one child skill from skill_spec.yaml", cmd_render),
        ("validate", "Validate SkillIR and rendered child behavior", cmd_validate),
        ("publish", "Publish a passing child skill inside the run directory", cmd_publish),
        ("status", "Show compact run state", cmd_status),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--run", required=True)
        command.set_defaults(handler=handler)

    patch = commands.add_parser(
        "apply-patch", help="Apply a bounded evidence-backed SkillIR patch"
    )
    patch.add_argument("--run", required=True)
    patch.add_argument("--proposal", required=True)
    patch.set_defaults(handler=cmd_apply_patch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except Paper2SkillsError as exc:
        print(f"paper2skills: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
