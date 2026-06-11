from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.evaluation.validate_skill_package import validate_skill_package


VALIDATION_DEPTHS = ("dry_run", "data_smoke", "live_execute")


def validate_build(skill_dir: str | Path, *, validation_depth: str = "dry_run") -> dict[str, Any]:
    depth = normalize_validation_depth(validation_depth)
    root = Path(skill_dir)
    package = validate_skill_package(root)
    preflight_plan = file_status(root / "scripts" / "preflight.py")
    install_plan = install_plan_status(root)
    execution_plan = file_status(root / "scripts" / "run.py")
    policy = {
        "package_structure": package["passed"],
        "preflight_plan": preflight_plan["present"],
        "install_plan": install_plan["present"],
        "execution_plan": execution_plan["present"],
        "benchmark_scoring": False,
    }
    check_passed = all(value for key, value in policy.items() if key != "benchmark_scoring")
    report = {
        "validation_type": "build_time_self_check",
        "validation_depth": depth,
        "self_check_status": "pass" if check_passed else "fail",
        "passed": check_passed,
        "benchmark_score": None,
        "diagnostic_only": True,
        "package_structure": package,
        "policy_safety": {
            "notebook_policy_safe": metric_passed(package, "notebook_policy_safe"),
            "install_policy_safe": metric_passed(package, "install_policy_safe"),
            "path_leakage_absent": metric_passed(package, "path_leakage_absent"),
        },
        "preflight_plan_status": preflight_plan,
        "install_plan_status": install_plan,
        "execution_plan_status": execution_plan,
        "repair_actions": [],
        "warnings": [],
        "errors": [],
    }
    if depth in {"data_smoke", "live_execute"}:
        report["passed"] = False
        report["self_check_status"] = "unsupported"
        report["status"] = "unsupported"
        report["errors"].append("validation_depth_unsupported")
        report["warnings"].append(f"{depth} build validation requires an explicit reviewed example runner; no benchmark score is produced.")
    return report


def normalize_validation_depth(value: str) -> str:
    depth = str(value or "").strip()
    if depth not in VALIDATION_DEPTHS:
        raise ValueError(f"unknown validation depth: {depth}")
    return depth


def file_status(path: Path) -> dict[str, Any]:
    return {"present": path.is_file(), "path": str(path)}


def install_plan_status(root: Path) -> dict[str, Any]:
    candidates = [
        root / "assets" / "environment_spec.yaml",
        root / "assets" / "env" / "paper2skill.environment.yml",
        root / "assets" / "install_plan.json",
    ]
    present = [path for path in candidates if path.is_file()]
    return {"present": bool(present), "paths": [str(path) for path in present]}


def metric_passed(package_report: dict[str, Any], metric: str) -> bool:
    return float((package_report.get("metrics") or {}).get(metric, 0.0)) >= 1.0
