from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from paper2skill.generators.codex_skill_generator import build_context, example_inputs, generate_skill, plan_outputs
from paper2skill.runtime.env_manager import inspect_environment, load_environment_spec, public_environment_report
from paper2skill.validators.skill_validator import validate_skill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper2skill", description="Generate evidence-first Codex skills from papers, repositories, and tutorials.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Analyze inputs and write a build plan without generating a skill.")
    add_input_args(plan)
    plan.add_argument("--out", default="paper2skill_plan")

    build = sub.add_parser("build", help="Generate a Codex skill.")
    add_input_args(build)
    build.add_argument("--example", choices=["toy_python", "toy_r"], default=None)
    build.add_argument("--skill-name", default=None)
    build.add_argument("--algorithm-name", default=None)
    build.add_argument("--task", default=None)
    build.add_argument("--out", default=None)

    validate = sub.add_parser("validate", help="Validate a generated skill.")
    validate.add_argument("--skill", required=True)
    validate.add_argument("--json", action="store_true", dest="as_json")

    test = sub.add_parser("test", help="Run tests for a generated skill.")
    test.add_argument("--skill", required=True)
    test.add_argument("--mode", choices=["preflight", "environment", "plan", "demo", "all"], default="all")

    inspect = sub.add_parser("inspect-env", help="Inspect a generated skill environment.")
    inspect.add_argument("--skill", required=True)
    inspect.add_argument("--manifest", default=None)
    inspect.add_argument("--json", action="store_true", dest="as_json")

    return parser


def add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--paper", default=None)
    parser.add_argument("--paper-url", default=None)
    parser.add_argument("--paper-title", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--tutorial", action="append", default=[])
    parser.add_argument("--maturity-target", default=None)


def command_plan(args: argparse.Namespace) -> int:
    context = build_context(
        skill_name=args.paper_title,
        algorithm_name=args.paper_title,
        paper=args.paper,
        repo=args.repo,
        tutorials=args.tutorial,
        paper_url=args.paper_url,
        paper_title=args.paper_title,
        maturity_level=args.maturity_target or "L1",
    )
    out = plan_outputs(context, args.out)
    print(f"Wrote plan outputs to {out}")
    return 0


def command_build(args: argparse.Namespace) -> int:
    values: dict[str, Any] = {}
    if args.example:
        values.update(example_inputs(args.example))
    for key, value in {
        "skill_name": args.skill_name,
        "algorithm_name": args.algorithm_name,
        "task": args.task,
        "paper": args.paper,
        "repo": args.repo,
        "tutorials": args.tutorial or None,
        "paper_url": args.paper_url,
        "paper_title": args.paper_title,
        "maturity_level": args.maturity_target,
    }.items():
        if value is not None and value != "" and value != []:
            values[key] = value
    context = build_context(**values)
    out_dir = Path(args.out) if args.out else Path(".agents") / "skills" / context["skill_name"]
    generate_skill(context, out_dir)
    print(f"Generated skill at {out_dir}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    result = validate_skill(args.skill)
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"status: {result['status']}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
    return 0 if result["status"] == "pass" else 2


def command_test(args: argparse.Namespace) -> int:
    skill = Path(args.skill)
    test_map = {
        "preflight": ["tests/test_preflight.py"],
        "environment": ["tests/test_environment.py"],
        "plan": ["tests/test_plan.py"],
        "demo": ["tests/test_output_contract.py"],
        "all": ["tests"],
    }
    command = [sys.executable, "-m", "pytest", "-q", *test_map[args.mode]]
    result = subprocess.run(command, cwd=skill, text=True, check=False)
    return result.returncode


def command_inspect_env(args: argparse.Namespace) -> int:
    spec_path = Path(args.skill) / "assets" / "environment_spec.yaml"
    spec = load_environment_spec(spec_path)
    report = inspect_environment(spec)
    public_report = public_environment_report(report, Path(args.skill))
    if args.as_json:
        print(json.dumps(public_report, indent=2, ensure_ascii=False))
    else:
        print(f"status: {report['status']}")
        print(json.dumps(public_report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        return command_plan(args)
    if args.command == "build":
        return command_build(args)
    if args.command == "validate":
        return command_validate(args)
    if args.command == "test":
        return command_test(args)
    if args.command == "inspect-env":
        return command_inspect_env(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
