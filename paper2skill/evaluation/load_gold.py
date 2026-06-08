from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


GOLD_FILES = {
    "case_metadata": "case_metadata.yaml",
    "source_collection": "source_collection.yaml",
    "dependency_contract": "dependency_contract.yaml",
    "tutorial_selection": "tutorial_selection.yaml",
    "workflow_dag": "workflow_dag.yaml",
    "io_contract": "io_contract.yaml",
    "bio_contract": "bio_contract.yaml",
    "adapter_behavior": "adapter_behavior.yaml",
    "evidence_expectations": "evidence_expectations.yaml",
    "metrics": "metrics.yaml",
    "level0_skill_package": "level0_skill_package.yaml",
    "level2_official_examples": "level2_official_examples.yaml",
    "level3_new_data": "level3_new_data.yaml",
    "level4_agentic_tasks": "level4_agentic_tasks.yaml",
}

REFERENCE_FILES = {
    "source_manifest": "source_manifest.json",
    "repo_index": "repo_index.json",
    "repo_evidence": "repo_evidence.json",
    "paper_evidence": "paper_evidence.json",
    "tutorial_candidates": "tutorial_candidates.json",
    "tutorial_trace": "tutorial_trace.json",
    "workflow_dag": "workflow_dag.json",
    "io_contract": "io_contract.yaml",
    "bio_contract": "bio_contract.yaml",
    "adapter_spec": "adapter_spec.yaml",
    "adapter_review": "adapter_review.yaml",
    "evidence_graph": "evidence_graph.json",
    "algorithm_contract": "algorithm_contract.yaml",
    "environment_spec": "environment_spec.yaml",
    "notebook_execution_policy": "notebook_execution_policy.json",
}


def load_gold(case_dir: str | Path) -> dict[str, Any]:
    root = Path(case_dir)
    gold_dir = root / "gold"
    data: dict[str, Any] = {"case_dir": str(root), "case_id": root.name, "case_md_present": (root / "case.md").exists(), "gold": {}, "missing_files": []}
    for key, filename in GOLD_FILES.items():
        path = gold_dir / filename
        if not path.exists():
            data["missing_files"].append(str(path))
            data["gold"][key] = {}
            continue
        data["gold"][key] = read_yaml(path)
    return data


def load_generated_bundle(generated: str | Path) -> dict[str, Any]:
    root = Path(generated)
    skill_root = root.parent if root.name == "references" else root
    references_root = root if root.name == "references" else root / "references"
    bundle: dict[str, Any] = {
        "generated_dir": str(references_root),
        "skill_dir": str(skill_root),
        "files": {},
        "missing_files": [],
        "warnings": [],
    }
    if not references_root.exists():
        bundle["warnings"].append(f"generated references path does not exist: {references_root}")
    for key, filename in REFERENCE_FILES.items():
        path = references_root / filename
        if key == "environment_spec" and not path.exists():
            sibling_assets = references_root.parent / "assets" / filename
            if sibling_assets.exists():
                path = sibling_assets
        if not path.exists():
            bundle["missing_files"].append(str(path))
            bundle["files"][key] = {}
            continue
        try:
            bundle["files"][key] = read_data(path)
        except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
            bundle["files"][key] = {}
            bundle["warnings"].append(f"could not load {path}: {exc}")
    return bundle


def read_data(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return read_yaml(path)


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def evaluation_result(name: str) -> dict[str, Any]:
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


def recall(expected: set[str], observed: set[str]) -> float:
    if not expected:
        return 1.0
    return len(expected & observed) / len(expected)


def precision(expected: set[str], observed: set[str]) -> float:
    if not observed:
        return 1.0 if not expected else 0.0
    return len(expected & observed) / len(observed)


def normalize_token(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"['\"`]", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalize_package_name(value: Any) -> str:
    text = str(value).strip()
    if "@" in text and "://" in text:
        text = text.split("@", 1)[0].strip()
    text = re.split(r"[<>=!~;,\[\]\s(]", text, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", text).strip().lower()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def field_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


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


def text_blob(value: Any) -> str:
    return "\n".join(flatten_strings(value)).lower()


def contains_text(value: Any, needle: Any) -> bool:
    return str(needle).lower() in text_blob(value)


def ratio_for_needles(needles: list[Any], haystack: Any) -> tuple[float, list[str]]:
    expected = [str(item) for item in needles if str(item).strip()]
    if not expected:
        return 1.0, []
    missing = [item for item in expected if item.lower() not in text_blob(haystack)]
    return (len(expected) - len(missing)) / len(expected), missing


def list_diff(expected: set[str], observed: set[str]) -> tuple[list[str], list[str]]:
    return sorted(expected - observed), sorted(observed - expected)
