from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


VALID_ADAPTER_STATUSES = {
    "demo_only",
    "candidate",
    "blocked",
    "ready",
    "reviewed",
    "verified",
}

EXECUTABLE_ADAPTER_STATUSES = {"ready", "reviewed", "verified"}

REQUIRED_SKILL_FILES = [
    "SKILL.md",
    "scripts/preflight.py",
    "scripts/env_manager.py",
    "scripts/run_in_env.sh",
    "scripts/plan.py",
    "scripts/run.py",
    "scripts/validate_outputs.py",
    "references/io_contract.yaml",
    "references/bio_contract.yaml",
    "references/workflow_dag.json",
    "references/adapter_spec.yaml",
    "references/adapter_review.yaml",
    "references/notebook_execution_policy.json",
    "references/evidence_graph.json",
    "assets/environment_spec.yaml",
    "assets/env/paper2skill.environment.yml",
    "assets/env/normalization_report.json",
]

REQUIRED_DIRS = ["scripts/adapters"]

ABSOLUTE_PATH_PATTERNS = [
    re.compile(r"\b[A-Za-z]:\\"),
    re.compile(r"/home/[A-Za-z0-9_.-]+/"),
    re.compile(r"/Users/[A-Za-z0-9_.-]+/"),
]


def validate_skill_package(skill_dir: str | Path, gold: dict[str, Any] | None = None) -> dict[str, Any]:
    root = normalize_skill_root(Path(skill_dir))
    gold = gold or {}
    result = validation_result("skill_package")
    missing_files = [path for path in required_files(gold) if not (root / path).is_file()]
    missing_dirs = [path for path in REQUIRED_DIRS if not (root / path).is_dir()]
    leakage = path_leakage(root)
    adapter_report = adapter_lifecycle_report(root)
    notebook_report = notebook_policy_report(root)
    install_report = install_policy_report(root)

    result["missing_items"].extend(missing_files)
    result["missing_items"].extend(missing_dirs)
    result["mismatched_items"].extend(adapter_report["mismatched_items"])
    result["mismatched_items"].extend(notebook_report["mismatched_items"])
    result["mismatched_items"].extend(install_report["mismatched_items"])
    result["warnings"].extend(adapter_report["warnings"])
    result["warnings"].extend(notebook_report["warnings"])
    result["warnings"].extend(install_report["warnings"])
    result["path_leakage"] = leakage

    metrics = {
        "required_files_present": 1.0 - (len(missing_files) / len(required_files(gold))) if required_files(gold) else 1.0,
        "required_dirs_present": 1.0 - (len(missing_dirs) / len(REQUIRED_DIRS)) if REQUIRED_DIRS else 1.0,
        "path_leakage_absent": 1.0 if not leakage else 0.0,
        "adapter_lifecycle_valid": adapter_report["score"],
        "notebook_policy_safe": notebook_report["score"],
        "install_policy_safe": install_report["score"],
    }
    finished = finish_result(result, metrics)
    finished["level"] = "L0"
    finished["missing_files"] = missing_files
    return finished


def normalize_skill_root(path: Path) -> Path:
    if path.name == "references":
        return path.parent
    return path


def required_files(gold: dict[str, Any]) -> list[str]:
    configured = gold.get("required_files")
    if isinstance(configured, list) and configured:
        return [str(item) for item in configured]
    return REQUIRED_SKILL_FILES


def read_reference(root: Path, relative: str) -> Any:
    path = root / relative
    if not path.exists():
        return {}
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return {}


def adapter_lifecycle_report(root: Path) -> dict[str, Any]:
    spec = read_reference(root, "references/adapter_spec.yaml")
    review = read_reference(root, "references/adapter_review.yaml")
    text = "\n".join(flatten_strings({"adapter_spec": spec, "adapter_review": review})).lower()
    statuses = [
        str(value).lower()
        for value in flatten_strings({"adapter_spec": spec, "adapter_review": review})
        if str(value).lower() in VALID_ADAPTER_STATUSES
    ]
    status = statuses[0] if statuses else "not_confirmed"
    mismatches = []
    warnings = []
    if status not in VALID_ADAPTER_STATUSES:
        mismatches.append({"field": "adapter_status", "expected": sorted(VALID_ADAPTER_STATUSES), "actual": status})
    if status not in EXECUTABLE_ADAPTER_STATUSES and any(token in text for token in ["executable: true", "execution_status: ready", "ready_to_run: true"]):
        mismatches.append({"field": "candidate_executable", "expected": "not executable", "actual": status})
    if not statuses:
        warnings.append("adapter status was not found")
    return {"score": 1.0 if not mismatches else 0.0, "mismatched_items": mismatches, "warnings": warnings}


def notebook_policy_report(root: Path) -> dict[str, Any]:
    policy = read_reference(root, "references/notebook_execution_policy.json")
    text = "\n".join(flatten_strings(policy)).lower()
    mismatches = []
    if "execute_unknown_notebooks" in text and "true" in text:
        mismatches.append({"field": "notebook_execution_policy", "expected": "unknown notebooks disabled", "actual": "enabled"})
    return {"score": 1.0 if not mismatches else 0.0, "mismatched_items": mismatches, "warnings": []}


def install_policy_report(root: Path) -> dict[str, Any]:
    environment = read_reference(root, "assets/environment_spec.yaml")
    adapter = read_reference(root, "references/adapter_spec.yaml")
    text = "\n".join(flatten_strings({"environment": environment, "adapter": adapter})).lower()
    mismatches = []
    if "auto_install" in text and "true" in text and "requires_confirmation" not in text:
        mismatches.append({"field": "install_policy", "expected": "no auto install without confirmation", "actual": "auto install"})
    return {"score": 1.0 if not mismatches else 0.0, "mismatched_items": mismatches, "warnings": []}


def path_leakage(root: Path) -> list[str]:
    if not root.exists():
        return []
    leaked: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in ABSOLUTE_PATH_PATTERNS):
            leaked.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(leaked)


def validation_result(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "component": name,
        "score": 0.0,
        "passed": False,
        "metrics": {},
        "missing_items": [],
        "extra_items": [],
        "mismatched_items": [],
        "warnings": [],
    }


def finish_result(result: dict[str, Any], metrics: dict[str, float], *, pass_threshold: float = 1.0) -> dict[str, Any]:
    clean_metrics = {key: clamp01(value) for key, value in metrics.items()}
    result["metrics"] = clean_metrics
    result["score"] = round(100.0 * mean(clean_metrics.values()), 2) if clean_metrics else 100.0
    result["passed"] = result["score"] >= round(100.0 * pass_threshold, 2) and not result["missing_items"] and not result["mismatched_items"]
    return result


def clamp01(value: float | int | bool) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return max(0.0, min(1.0, float(value)))


def mean(values: Any) -> float:
    items = list(values)
    if not items:
        return 1.0
    return sum(float(value) for value in items) / len(items)


def flatten_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            strings.append(str(key))
            strings.extend(flatten_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(flatten_strings(item))
    elif value is not None:
        strings.append(str(value))
    return strings


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a generated Paper2Skill skill package.")
    parser.add_argument("skill_dir")
    args = parser.parse_args(argv)
    print(json.dumps(validate_skill_package(args.skill_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
