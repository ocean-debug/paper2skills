from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paper2skill.common import read_json, write_json
from paper2skill.env_rebuilder.env_paths import resolve_env_path
from paper2skill.env_rebuilder.executor import apply_install_plan
from paper2skill.env_rebuilder.lockfile import export_lock_artifacts
from paper2skill.env_rebuilder.planner import plan_environment
from paper2skill.env_rebuilder.repair import diagnose_failure
from paper2skill.env_rebuilder.scanner import load_scan, scan_repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild bioinformatics execution environments for Paper2Skill.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan a repository for environment files and install hints")
    scan.add_argument("--repo", required=True)
    scan.add_argument("--out", required=True)

    plan = sub.add_parser("plan", help="Create a layered BioEnvRebuilder install plan")
    plan.add_argument("--scan", required=True)
    plan.add_argument("--target", default="new", choices=["new", "existing"])
    plan.add_argument("--env", required=True)
    plan.add_argument("--out", required=True)
    plan.add_argument("--allow-shared-env", action="store_true")
    plan.add_argument("--allow-github-install", default="ask", choices=["ask", "approved"])
    plan.add_argument("--gpu-policy", default="optional", choices=["required", "optional", "cpu_only"])
    plan.add_argument("--torch-backend", default="auto", choices=["auto", "cpu", "cu118", "cu121", "cu124", "cu126", "cu128"])
    plan.add_argument("--manager-preference", default="auto", choices=["auto", "uv", "conda"])
    plan.add_argument("--env-base-dir", help="Base directory for resolving bare uv environment names")
    plan.add_argument("--r-mode", default="conda", choices=["conda", "renv"], help="R resolver mode; renv restore requires --allow-renv-lock")
    plan.add_argument("--allow-renv-lock", action="store_true", help="Allow renv.lock restore in r-mode=renv")

    apply = sub.add_parser("apply", help="Execute an approved BioEnvRebuilder install plan")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--out", required=True)
    apply.add_argument("--yes", action="store_true")

    repair = sub.add_parser("repair", help="Diagnose install failure output and produce a repair plan")
    repair.add_argument("--failure-report", required=True)
    repair.add_argument("--out", required=True)

    lock = sub.add_parser("export-lock", help="Create lockfile export command plan")
    lock.add_argument("--env", required=True)
    lock.add_argument("--out", required=True)
    lock.add_argument("--manager", default="conda", choices=["conda", "uv", "conda+uv"])
    lock.add_argument("--resolved-env-path")
    lock.add_argument("--python-executable")
    lock.add_argument("--plan-out", help="Compatibility alias for output report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
    except Exception as exc:  # noqa: BLE001 - CLI should report structured failures.
        out = output_path(args)
        result = {"status": "invalid", "errors": [str(exc)]}
        write_json(out, result)
        print(json.dumps({"status": "invalid", "out": str(out), "errors": result["errors"]}, ensure_ascii=False))
        return 2
    out = output_path(args)
    write_json(out, result)
    print(json.dumps({"status": result.get("status"), "out": str(out)}, ensure_ascii=False))
    return 0 if result.get("status") in {"scanned", "ready", "blocked_manual", "executed", "exported", "partial", "repair_plan_available", "no_known_repair"} else 1


def output_path(args: argparse.Namespace) -> Path:
    if getattr(args, "command", None) == "export-lock":
        return Path(args.plan_out or Path(args.out) / "lock_export_plan.json")
    return Path(getattr(args, "out", None) or "bio_env_rebuilder_error.json")


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "scan":
        return scan_repo(args.repo)
    if args.command == "plan":
        return plan_environment(
            load_scan(args.scan),
            target=args.target,
            env=args.env,
            allow_shared_env=args.allow_shared_env,
            allow_github_install=args.allow_github_install,
            gpu_policy=args.gpu_policy,
            torch_backend=args.torch_backend,
            manager_preference=args.manager_preference,
            env_path=resolve_env_path(args.env, args.env_base_dir) if args.env_base_dir else None,
            r_mode=args.r_mode,
            allow_renv=args.allow_renv_lock,
        )
    if args.command == "apply":
        return apply_install_plan(read_json(Path(args.plan)), yes=args.yes)
    if args.command == "repair":
        return diagnose_failure(read_json(Path(args.failure_report)))
    if args.command == "export-lock":
        return export_lock_artifacts(args.env, args.out, manager=args.manager, resolved_env_path=args.resolved_env_path, python_executable=args.python_executable)
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
