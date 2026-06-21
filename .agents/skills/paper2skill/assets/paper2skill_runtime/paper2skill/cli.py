from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from paper2skill.build_validation import VALIDATION_DEPTHS, validate_build
from paper2skill.common import slugify
from paper2skill.common import ensure_dir, write_json, write_yaml
from paper2skill.compiler import annotate_run_trace_promotion, ingest_run_directory, promote_from_run_trace, update_algorithm_contract_after_promotion
from paper2skill.evaluation.run_benchmark import run_benchmark
from paper2skill.generators.codex_skill_generator import build_context, example_inputs, generate_skill, plan_outputs
from paper2skill.runtime.env_manager import inspect_environment, load_environment_spec, public_environment_report
from paper2skill.reproduction.agentic import ReproduceConfig, run_agentic_reproduction
from paper2skill.validators.skill_validator import validate_skill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper2skill", description="Generate evidence-first Codex skills from papers, repositories, and tutorials.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Analyze inputs and write a build plan without generating a skill.")
    add_input_args(plan)
    add_generation_metadata_args(plan)
    plan.add_argument("--out", default="paper2skill_plan")

    triage = sub.add_parser("triage-plan", help="Write thin plan-run-plan artifacts without generating a skill.")
    add_input_args(triage)
    add_generation_metadata_args(triage)
    triage.add_argument("--out", default="paper2skill_triage_plan")

    build = sub.add_parser("build", help="Generate a Codex skill.")
    add_input_args(build)
    add_generation_metadata_args(build)
    build.add_argument("--example", choices=["toy_python", "toy_r"], default=None)
    build.add_argument("--out", default=None)
    build.add_argument("--validation-depth", default="dry_run", choices=list(VALIDATION_DEPTHS), help="Build-time self-check depth; not benchmark scoring.")
    build.add_argument("--validation-manifest", default=None, help="Manifest and output contract used only for data_smoke/live_execute build self-checks.")
    build.add_argument("--validation-result-dir", default=None, help="Output directory for build self-check execution.")
    build.add_argument("--validation-timeout", type=int, default=600, help="Timeout in seconds for build self-check commands.")
    build.add_argument("--validation-env-prefix", default=None, help="Existing conda prefix used to run data_smoke/live_execute validation.")
    build.add_argument("--validation-python", default=None, help="Python executable used to run data_smoke/live_execute validation.")
    build.add_argument("--example-data-cache-dir", default=None, help="Directory containing pre-downloaded official example data for data_smoke/live_execute validation.")
    build.add_argument("--repair-attempts", type=int, default=4, help="Regenerate and re-check the skill when build-time self-check fails; capped at 4.")
    build.add_argument("--example-id", default=None, help="Example id from references/tutorial_catalog.yaml to verify for data_smoke/live_execute.")
    build.add_argument("--example-data-url", action="append", default=[], help="Official tutorial data URL to include in the generated examples catalog.")

    reproduce = sub.add_parser("reproduce", help="Build, smoke-run, repair, and promote a generated skill to verified when execution is approved.")
    add_input_args(reproduce)
    add_generation_metadata_args(reproduce)
    reproduce.add_argument("--example", choices=["toy_python", "toy_r"], default=None)
    reproduce.add_argument("--out", default=None)
    reproduce.add_argument("--confirm-run", choices=["yes", "no"], default="no")
    reproduce.add_argument("--install-policy", choices=["never", "plan", "yes"], default="never")
    reproduce.add_argument("--repair-budget", type=int, default=2)
    reproduce.add_argument("--smoke-timeout", type=int, default=600)
    reproduce.add_argument("--data-cache-dir", default=None)
    reproduce.add_argument("--target-maturity", choices=["L2", "L3", "L4"], default="L2")
    reproduce.add_argument("--validation-python", default=None)
    reproduce.add_argument("--validation-env-prefix", default=None)
    reproduce.add_argument("--example-id", default=None)
    reproduce.add_argument("--example-data-url", action="append", default=[], help="Official tutorial data URL to include in the generated examples catalog.")

    validate = sub.add_parser("validate", help="Validate a generated skill.")
    validate.add_argument("--skill", required=True)
    validate.add_argument("--json", action="store_true", dest="as_json")

    run_example = sub.add_parser("run-example", help="Run a selected generated-skill example and write a run trace.")
    run_example.add_argument("--skill", required=True)
    run_example.add_argument("--manifest", required=True)
    run_example.add_argument("--out", required=True)
    run_example.add_argument("--example-id", default=None)
    run_example.add_argument("--python", default=sys.executable)
    run_example.add_argument("--timeout", type=int, default=600)
    run_example.add_argument("--confirm-run", choices=["yes", "no"], default="no")

    ingest = sub.add_parser("ingest-run", help="Ingest an existing result directory into a Paper2Skill run trace.")
    ingest.add_argument("--run-dir", required=True)
    ingest.add_argument("--skill", default=None)
    ingest.add_argument("--example-id", default=None)
    ingest.add_argument("--out", default="paper2skill_run_trace")

    promote = sub.add_parser("promote", help="Promote a generated skill using a promotion-ready run trace.")
    promote.add_argument("--skill", required=True)
    promote.add_argument("--run-trace", required=True)
    promote.add_argument("--example-id", default=None)
    promote.add_argument("--out", default=None, help="Optional output directory for promoted contracts; default updates the skill.")

    inspect = sub.add_parser("inspect-env", help="Inspect a generated skill environment.")
    inspect.add_argument("--skill", required=True)
    inspect.add_argument("--manifest", default=None)
    inspect.add_argument("--json", action="store_true", dest="as_json")

    benchmark = sub.add_parser("benchmark", help="Run independent gold-standard benchmark evaluation.")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_sub.add_parser("run", help="Run a benchmark case against a generated or newly built skill.")
    benchmark_run.add_argument("--case", required=True, help="Benchmark case YAML file.")
    benchmark_run.add_argument("--level", default="L1", choices=["L0", "L1", "L2", "L3", "L4"])
    benchmark_run.add_argument("--skill", default=None, help="Existing generated skill directory. If omitted, the case inputs are built first.")
    benchmark_run.add_argument("--out", default=None, help="Directory for generated benchmark artifacts.")
    benchmark_run.add_argument("--json", action="store_true", dest="as_json")

    return parser


def add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--paper", default=None)
    parser.add_argument("--paper-url", default=None)
    parser.add_argument("--paper-title", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--repo-ref", default="main")
    parser.add_argument("--skip-repo-clone", action="store_true")
    parser.add_argument("--no-execute-tutorials", action="store_true")
    parser.add_argument("--strict-evidence", action="store_true")
    parser.add_argument("--tutorial-filter", default=None)
    parser.add_argument("--catalog-all-tutorials", action="store_true")
    parser.add_argument("--adapter-review", default=None)
    parser.add_argument("--tutorial", action="append", default=[])
    parser.add_argument("--maturity-target", default=None)


def add_generation_metadata_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--skill-name", default=None)
    parser.add_argument("--algorithm-name", default=None)
    parser.add_argument("--task", default=None)


def command_plan(args: argparse.Namespace) -> int:
    context = build_context(
        skill_name=args.skill_name or args.paper_title,
        algorithm_name=args.algorithm_name or args.paper_title,
        task=args.task or "algorithm_execution",
        paper=args.paper,
        repo=args.repo,
        tutorials=args.tutorial,
        paper_url=args.paper_url,
        paper_title=args.paper_title,
        repo_ref=args.repo_ref,
        skip_repo_clone=args.skip_repo_clone,
        no_execute_tutorials=args.no_execute_tutorials,
        strict_evidence=args.strict_evidence,
        tutorial_filter=args.tutorial_filter,
        catalog_all_tutorials=args.catalog_all_tutorials,
        adapter_review=args.adapter_review,
        collection_dir=Path(args.out) / ".paper2skill_collection",
        maturity_level=args.maturity_target or "L1",
    )
    out = plan_outputs(context, args.out)
    print(f"Wrote plan outputs to {out}")
    return 0


def command_triage_plan(args: argparse.Namespace) -> int:
    return command_plan(args)


def command_build(args: argparse.Namespace) -> int:
    input_errors = validate_build_inputs(args)
    if input_errors:
        for error in input_errors:
            print(f"ERROR: {error}")
        return 2
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
        "repo_ref": args.repo_ref,
        "skip_repo_clone": args.skip_repo_clone,
        "no_execute_tutorials": args.no_execute_tutorials,
        "strict_evidence": args.strict_evidence,
        "tutorial_filter": args.tutorial_filter,
        "catalog_all_tutorials": args.catalog_all_tutorials,
        "adapter_review": args.adapter_review,
        "example_data_urls": args.example_data_url or None,
    }.items():
        if value is not None and value != "" and value != [] and value is not False:
            values[key] = value
    if args.out:
        out_dir = Path(args.out)
    else:
        inferred_name = values.get("skill_name") or values.get("algorithm_name") or "generated-skill"
        out_dir = Path(".agents") / "skills" / slugify(str(inferred_name))
    values["collection_dir"] = out_dir.parent / ".paper2skill_collection" / out_dir.name
    context = build_context(**values)
    evidence_errors = validate_resolved_evidence(args, context)
    if evidence_errors:
        for error in evidence_errors:
            print(f"ERROR: {error}")
        return 2
    validation = generate_with_build_validation(
        context,
        out_dir,
        validation_depth=args.validation_depth,
        validation_manifest=args.validation_manifest,
        validation_result_dir=args.validation_result_dir,
        validation_timeout=args.validation_timeout,
        validation_env_prefix=args.validation_env_prefix,
        validation_python=args.validation_python,
        example_data_cache_dir=args.example_data_cache_dir,
        repair_attempts=args.repair_attempts,
        example_id=args.example_id,
    )
    write_json(out_dir / "build_validation" / "build_validation.json", validation)
    print(f"Generated skill at {out_dir}")
    return 0 if validation["passed"] else 2


def validate_build_inputs(args: argparse.Namespace) -> list[str]:
    if args.example:
        return []
    errors: list[str] = []
    if not (args.paper or args.paper_url):
        errors.append("build requires paper evidence: provide --paper or --paper-url, or use --example for toy fixtures.")
    elif args.paper:
        errors.extend(validate_existing_file("--paper", args.paper))
    if not args.repo:
        errors.append("build requires an official source repository: provide --repo.")
    elif not is_remote_repo(args.repo):
        errors.extend(validate_existing_dir("--repo", args.repo))
    elif args.repo.startswith("file://"):
        errors.extend(validate_existing_dir("--repo", file_url_path(args.repo)))
    if not (args.tutorial or args.tutorial_filter or args.catalog_all_tutorials):
        errors.append("build requires official tutorial/example evidence: provide --tutorial or --tutorial-filter.")
    for tutorial in args.tutorial or []:
        errors.extend(validate_tutorial_file(tutorial, args.repo))
    return errors


def validate_existing_file(flag: str, value: str | Path) -> list[str]:
    path = Path(value)
    if not path.exists():
        return [f"{flag} path does not exist: {value}"]
    if not path.is_file():
        return [f"{flag} must point to a file: {value}"]
    return []


def validate_existing_dir(flag: str, value: str | Path) -> list[str]:
    path = Path(value)
    if not path.exists():
        return [f"{flag} path does not exist: {value}"]
    if not path.is_dir():
        return [f"{flag} must point to a directory: {value}"]
    return []


def validate_tutorial_file(value: str | Path, repo: str | None) -> list[str]:
    path = Path(value)
    if path.exists():
        return [] if path.is_file() else [f"--tutorial must point to a file: {value}"]
    repo_base = local_repo_base(repo)
    if repo_base and not path.is_absolute():
        candidate = repo_base / path
        if candidate.exists():
            return [] if candidate.is_file() else [f"--tutorial must point to a file: {value}"]
    if repo and is_remote_repo(repo) and not repo.startswith("file://") and not path.is_absolute():
        return []
    return [f"--tutorial path does not exist locally or under --repo: {value}"]


def is_remote_repo(value: str) -> bool:
    return value.startswith(("http://", "https://", "git@")) or value.startswith("file://")


def local_repo_base(value: str | None) -> Path | None:
    if not value:
        return None
    if value.startswith("file://"):
        return file_url_path(value)
    if is_remote_repo(value):
        return None
    return Path(value)


def file_url_path(value: str) -> Path:
    parsed = urlparse(value)
    path = unquote(parsed.path)
    if path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return Path(path)


def validate_resolved_evidence(args: argparse.Namespace, context: dict[str, Any]) -> list[str]:
    if args.example:
        return []
    errors: list[str] = []
    tutorial_trace = context.get("tutorial_trace") if isinstance(context.get("tutorial_trace"), dict) else {}
    tutorials = tutorial_trace.get("tutorials") if isinstance(tutorial_trace.get("tutorials"), list) else []
    if args.tutorial:
        for requested in args.tutorial:
            trace = find_tutorial_trace(tutorials, requested)
            if trace is None or trace.get("error"):
                errors.append(f"build could not resolve --tutorial evidence after repository inspection: {requested}")
    elif args.tutorial_filter:
        resolved = [trace for trace in tutorials if isinstance(trace, dict) and not trace.get("error") and tutorial_trace_matches_filter(trace, args.tutorial_filter)]
        if not resolved:
            errors.append(f"build could not find tutorial/example evidence matching --tutorial-filter: {args.tutorial_filter}")
    scanner_report = tutorial_trace.get("tutorial_scanner_report") if isinstance(tutorial_trace.get("tutorial_scanner_report"), dict) else {}
    missing_indexed = scanner_report.get("missing_indexed_tutorials") if isinstance(scanner_report.get("missing_indexed_tutorials"), list) else []
    if getattr(args, "strict_evidence", False) and missing_indexed:
        missing = ", ".join(str(item.get("target") or item) for item in missing_indexed if isinstance(item, dict))
        errors.append(f"repo tutorial index references missing tutorial files: {missing}")
    return errors


def find_tutorial_trace(tutorials: list[Any], requested: str) -> dict[str, Any] | None:
    requested_path = str(requested).replace("\\", "/").split("#", 1)[0]
    requested_name = Path(requested_path).name
    for trace in tutorials:
        if not isinstance(trace, dict):
            continue
        path = str(trace.get("path") or "").replace("\\", "/").split("#", 1)[0]
        if path == requested_path or path.endswith(f"/{requested_path}") or (requested_name and Path(path).name == requested_name):
            return trace
    return None


def tutorial_trace_matches_filter(trace: dict[str, Any], tutorial_filter: str) -> bool:
    needles = [part.strip().lower() for part in str(tutorial_filter or "").split("|") if part.strip()]
    if not needles:
        return True
    haystack = "\n".join(str(trace.get(key) or "") for key in ["path", "title", "source", "source_path"]).lower()
    return any(needle in haystack for needle in needles)


def command_reproduce(args: argparse.Namespace) -> int:
    args.catalog_all_tutorials = True
    input_errors = validate_build_inputs(args)
    if input_errors:
        for error in input_errors:
            print(f"ERROR: {error}")
        return 2
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
        "repo_ref": args.repo_ref,
        "skip_repo_clone": args.skip_repo_clone,
        "no_execute_tutorials": args.no_execute_tutorials,
        "strict_evidence": args.strict_evidence,
        "tutorial_filter": args.tutorial_filter,
        "catalog_all_tutorials": True,
        "adapter_review": args.adapter_review,
        "example_data_urls": args.example_data_url or None,
    }.items():
        if value is not None and value != "" and value != [] and value is not False:
            values[key] = value
    if args.out:
        out_dir = Path(args.out)
    else:
        inferred_name = values.get("skill_name") or values.get("algorithm_name") or "generated-skill"
        out_dir = Path(".agents") / "skills" / slugify(str(inferred_name))
    values["collection_dir"] = out_dir.parent / ".paper2skill_collection" / out_dir.name
    context = build_context(**values)
    evidence_errors = validate_resolved_evidence(args, context)
    if evidence_errors:
        for error in evidence_errors:
            print(f"ERROR: {error}")
        return 2
    result = run_agentic_reproduction(
        context,
        out_dir,
        ReproduceConfig(
            confirm_run=args.confirm_run == "yes",
            install_policy=args.install_policy,
            repair_budget=max(0, args.repair_budget),
            smoke_timeout=args.smoke_timeout,
            data_cache_dir=args.data_cache_dir,
            target_maturity=args.target_maturity,
            validation_python=args.validation_python,
            validation_env_prefix=args.validation_env_prefix,
            example_id=args.example_id,
        ),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "pass" else 2


def generate_with_build_validation(
    context: dict[str, Any],
    out_dir: Path,
    *,
    validation_depth: str,
    validation_manifest: str | None,
    validation_result_dir: str | None,
    validation_timeout: int,
    validation_env_prefix: str | None,
    validation_python: str | None,
    example_data_cache_dir: str | None,
    repair_attempts: int,
    example_id: str | None,
) -> dict[str, Any]:
    attempts = min(max(0, repair_attempts), 4)
    repair_actions: list[dict[str, Any]] = []
    validation: dict[str, Any] = {}
    for attempt in range(attempts + 1):
        generate_skill(context, out_dir)
        validation = validate_build(
            out_dir,
            validation_depth=validation_depth,
            manifest=validation_manifest,
            result_dir=validation_result_dir,
            timeout_seconds=validation_timeout,
            example_id=example_id,
            env_prefix=validation_env_prefix,
            python_executable=validation_python,
            example_data_cache_dir=example_data_cache_dir,
        )
        if validation.get("passed"):
            break
        if attempt >= attempts:
            break
        repair = plan_repair_action(validation, attempt=attempt + 1)
        repair_actions.append(repair)
        if not repair.get("repairable"):
            break
        context = apply_repair_context(context, repair)
    validation["repair_actions"] = repair_actions
    validation["repair_attempts"] = len(repair_actions)
    return validation


def plan_repair_action(validation: dict[str, Any], *, attempt: int) -> dict[str, Any]:
    errors = list(validation.get("errors") or [])
    package = validation.get("package_structure") or {}
    missing_items = list(package.get("missing_items") or [])
    mismatched_items = list(package.get("mismatched_items") or [])
    status = str(validation.get("status") or "")
    repairable, action, reason = classify_repair(errors, missing_items, mismatched_items, status)
    return {
        "attempt": attempt,
        "action": action,
        "reason": reason,
        "repairable": repairable,
        "errors": errors,
        "missing_items": missing_items,
        "mismatched_items": mismatched_items,
    }


def classify_repair(
    errors: list[str],
    missing_items: list[str],
    mismatched_items: list[dict[str, Any]],
    status: str,
) -> tuple[bool, str, str]:
    if any(is_review_or_manifest_gate_error(error) for error in errors):
        return True, "repair_validation_manifest_or_example_contract", "verification manifest or selected example contract is incomplete"
    if any(error in {"output_contract_mismatch", "expected_outputs_missing", "required_outputs_missing"} for error in errors):
        return True, "repair_output_contract_or_adapter", "output contract mismatch can be repaired from machine validation evidence"
    if any(error in {"adapter_execution_failed", "preflight_failed", "execution_plan_failed"} for error in errors):
        return True, "repair_adapter_or_manifest", "verification execution failed; regenerate with repair context"
    if missing_items or any(error.startswith("missing_required_item:") for error in errors):
        return True, "regenerate_skill_package", "required child skill files are missing"
    if "install_plan_status:missing" in errors:
        return True, "supplement_install_context_and_regenerate", "environment or install artifacts are missing"
    if "preflight_plan_status:missing" in errors or "execution_plan_status:missing" in errors:
        return True, "regenerate_skill_package", "child skill planning scripts are missing"
    if mismatched_items or any(error.startswith("policy_mismatch:") for error in errors):
        return False, "stop_policy_mismatch", "policy mismatch requires template or safety policy review"
    return False, "no_deterministic_repair", "no safe deterministic repair is available for this failure"


def is_review_or_manifest_gate_error(error: str) -> bool:
    prefixes = (
        "validation_manifest.",
        "validation_manifest_",
    )
    exact = {
        "validation_manifest_required",
        "validation_manifest_invalid",
        "verification_manifest_required",
        "example_contract_required",
        "verification_adapter_required",
        "verified_output_validation_required",
    }
    return error in exact or error.startswith(prefixes)


def apply_repair_context(context: dict[str, Any], repair: dict[str, Any]) -> dict[str, Any]:
    next_context = dict(context)
    warnings = list(next_context.get("warnings", []) or [])
    if repair.get("action") == "supplement_install_context_and_regenerate":
        warnings.append(f"repair_attempt_{repair['attempt']}: regenerated with required environment and install artifacts")
    else:
        warnings.append(f"repair_attempt_{repair['attempt']}: regenerated skill package after build-time validation failure")
    next_context["warnings"] = warnings
    return next_context


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


def command_ingest_run(args: argparse.Namespace) -> int:
    trace = ingest_run_directory(args.run_dir, skill_dir=args.skill, example_id=args.example_id)
    out = ensure_dir(Path(args.out))
    write_json(out / "run_trace.json", trace)
    print(f"Wrote run trace to {out / 'run_trace.json'}")
    return 0 if trace.get("status") == "pass" else 2


def command_run_example(args: argparse.Namespace) -> int:
    paths = resolve_run_example_paths(args.skill, args.out, args.manifest)
    skill = paths["skill"]
    out = ensure_dir(paths["out"])
    manifest = paths["manifest"]
    result_dir = paths["result_dir"]
    trace_path = out / "run_trace.json"
    if args.confirm_run != "yes":
        trace = {
            "schema_version": 1,
            "trace_type": "paper2skill_run_trace",
            "status": "blocked_confirmation_required",
            "skill_dir": str(skill),
            "example_id": args.example_id,
            "commands": [],
            "output_validation": {"status": "not_run"},
            "message": "run-example requires --confirm-run yes before executing generated skill code.",
        }
        write_json(trace_path, trace)
        print(f"Blocked execution; wrote run trace to {trace_path}")
        return 2
    commands = [
        ("preflight", [args.python, str(skill / "scripts" / "preflight.py"), "--manifest", str(manifest), "--out", str(result_dir)]),
        ("plan", [args.python, str(skill / "scripts" / "plan.py"), "--manifest", str(manifest), "--out", str(result_dir)]),
        ("run", [args.python, str(skill / "scripts" / "run.py"), "--manifest", str(manifest), "--out", str(result_dir), "--verification-run"]),
        ("validate_outputs", [args.python, str(skill / "scripts" / "validate_outputs.py"), "--result", str(result_dir)]),
    ]
    command_records = []
    status = "pass"
    for stage, command in commands:
        if args.example_id and stage in {"plan", "run", "validate_outputs"}:
            command = [*command, "--example-id", args.example_id]
        try:
            completed = subprocess.run(command, cwd=skill, text=True, capture_output=True, check=False, timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            command_records.append(
                {
                    "stage": stage,
                    "command": command,
                    "returncode": None,
                    "stdout_tail": tail_text(exc.stdout or ""),
                    "stderr_tail": tail_text(exc.stderr or ""),
                    "status": "timeout",
                }
            )
            status = "fail"
            break
        record = {
            "stage": stage,
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": tail_text(completed.stdout),
            "stderr_tail": tail_text(completed.stderr),
        }
        command_records.append(record)
        if completed.returncode != 0:
            status = "fail"
            break
    trace = ingest_run_directory(result_dir, skill_dir=skill, example_id=args.example_id)
    trace["status"] = "pass" if status == "pass" and trace.get("output_validation", {}).get("status") == "pass" else status
    trace["commands"] = command_records
    annotate_run_trace_promotion(trace)
    write_json(trace_path, trace)
    print(f"Wrote run trace to {trace_path}")
    return 0 if trace.get("status") == "pass" else 2


def resolve_run_example_paths(skill: str | Path, out: str | Path, manifest: str | Path) -> dict[str, Path]:
    out_path = resolve_cli_path(out)
    return {
        "skill": resolve_cli_path(skill),
        "out": out_path,
        "manifest": resolve_cli_path(manifest),
        "result_dir": (out_path / "result").resolve(),
    }


def command_promote(args: argparse.Namespace) -> int:
    skill = Path(args.skill)
    target = ensure_dir(Path(args.out)) if args.out else skill
    trace = load_mapping(Path(args.run_trace))
    adapter_spec = load_mapping(skill / "references" / "adapter_spec.yaml")
    adapter_review = load_mapping(skill / "references" / "adapter_review.yaml")
    algorithm_contract = load_mapping(skill / "references" / "algorithm_contract.yaml")
    tutorial_catalog_path = skill / "references" / "tutorial_catalog.yaml"
    if not tutorial_catalog_path.exists():
        tutorial_catalog_path = skill / "references" / "examples_catalog.yaml"
    tutorial_catalog = load_mapping(tutorial_catalog_path)
    result = promote_from_run_trace(
        adapter_spec=adapter_spec,
        adapter_review=adapter_review,
        tutorial_catalog=tutorial_catalog,
        run_trace=trace,
        example_id=args.example_id,
    )
    write_json(target / "promotion_report.json", result)
    write_json(target / "debug" / "run_trace.promoted.json", trace)
    if result["promoted"]:
        updated_algorithm_contract = update_algorithm_contract_after_promotion(algorithm_contract, result["adapter_spec"], result["maturity"])
        write_yaml(target / "references" / "algorithm_contract.yaml", updated_algorithm_contract)
        write_yaml(target / "references" / "adapter_spec.yaml", result["adapter_spec"])
        write_yaml(target / "references" / "adapter_review.yaml", result["adapter_review"])
        write_yaml(target / "references" / "tutorial_catalog.yaml", result["tutorial_catalog"])
        write_yaml(target / "references" / "maturity.yaml", result["maturity"])
        write_yaml(target / "references" / "contracts" / "algorithm_contract.yaml", updated_algorithm_contract)
        write_yaml(target / "references" / "contracts" / "adapter_contract.yaml", result["adapter_spec"])
    print(f"promotion: {'promoted' if result['promoted'] else 'not_promoted'}")
    return 0 if result["promoted"] else 2


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


def command_benchmark(args: argparse.Namespace) -> int:
    if args.benchmark_command != "run":
        raise ValueError(f"unknown benchmark command: {args.benchmark_command}")
    result = run_benchmark(args.case, level=args.level, skill_dir=args.skill, out_dir=args.out)
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"status: {result['status']}")
        print(f"level: {result['level']}")
        print(f"case: {result['case_id']}")
        if result.get("score") is not None:
            print(f"score: {result['score']}")
        for error in result.get("errors", []):
            print(f"ERROR: {error}")
        for warning in result.get("warnings", []):
            print(f"WARN: {warning}")
    return 0 if result["status"] == "pass" else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        return command_plan(args)
    if args.command == "triage-plan":
        return command_triage_plan(args)
    if args.command == "build":
        return command_build(args)
    if args.command == "reproduce":
        return command_reproduce(args)
    if args.command == "validate":
        return command_validate(args)
    if args.command == "run-example":
        return command_run_example(args)
    if args.command == "ingest-run":
        return command_ingest_run(args)
    if args.command == "promote":
        return command_promote(args)
    if args.command == "inspect-env":
        return command_inspect_env(args)
    if args.command == "benchmark":
        return command_benchmark(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_cli_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def tail_text(value: object, *, max_chars: int = 4000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = str(value or "")
    return value[-max_chars:] if len(value) > max_chars else value


if __name__ == "__main__":
    raise SystemExit(main())
