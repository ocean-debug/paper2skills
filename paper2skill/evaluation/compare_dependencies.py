from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import (
    as_list,
    evaluation_result,
    field_value,
    finish_result,
    list_diff,
    normalize_package_name,
    recall,
    precision,
    text_blob,
)

R_BASE_PACKAGES = {"base", "compiler", "datasets", "graphics", "grdevices", "grid", "methods", "parallel", "splines", "stats", "tools", "utils"}


def compare_dependencies(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("dependencies")
    env = generated.get("environment_spec") or {}
    gold_required = dependency_set(gold, required=True)
    gold_optional = dependency_set(gold, required=False)
    observed_required = observed_required_dependencies(env)
    observed_optional = observed_optional_dependencies(env)
    observed_all = observed_required | observed_optional | R_BASE_PACKAGES
    gold_all = gold_required | gold_optional

    missing_required, extra_required = list_diff(gold_required, observed_required | observed_optional)
    missing_optional, _extra_optional = list_diff(gold_optional, observed_all)
    result["missing_items"].extend(f"required:{item}" for item in missing_required)
    result["missing_items"].extend(f"optional:{item}" for item in missing_optional)
    result["extra_items"].extend(f"required:{item}" for item in extra_required if item not in gold_all)

    metrics = {
        "dependency_precision": precision(gold_all, observed_all),
        "dependency_recall": recall(gold_all, observed_all),
        "required_dependency_recall": recall(gold_required, observed_all),
        "optional_dependency_recall": recall(gold_optional, observed_all),
        "language_detection_accuracy": language_detection_accuracy(gold, env),
    }
    return finish_result(result, metrics)


def dependency_set(gold: dict[str, Any], *, required: bool) -> set[str]:
    keys = ["python_required", "r_required", "system_or_cli"] if required else ["python_optional", "r_optional_or_object_support", "r_possible_required_or_inferred"]
    result: set[str] = set()
    for key in keys:
        for item in as_list(gold.get(key)):
            if isinstance(item, dict):
                item = item.get("name") or item.get("value") or item
            name = normalize_package_name(item)
            if name:
                result.add(name)
    return result


def observed_required_dependencies(env: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in ((env.get("python") or {}).get("packages") or []):
        if item.get("required", True):
            add_dependency_item(result, item)
    for item in ((env.get("r") or {}).get("packages") or []):
        if item.get("required", True):
            add_dependency_item(result, item)
    for item in env.get("executables") or []:
        add_dependency_item(result, item)
    for item in env.get("system_requirements") or []:
        add_dependency_item(result, item)
    for item in ((env.get("conda") or {}).get("packages") or []):
        add_dependency_item(result, item)
    return result


def observed_optional_dependencies(env: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in ((env.get("python") or {}).get("packages") or []):
        if not item.get("required", True):
            add_dependency_item(result, item)
    for item in ((env.get("r") or {}).get("packages") or []):
        if not item.get("required", True):
            add_dependency_item(result, item)
    for section in [env.get("optional_dependencies"), env.get("optional")]:
        collect_nested_dependencies(result, section)
    return result


def collect_nested_dependencies(result: set[str], value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            collect_nested_dependencies(result, item)
        return
    if isinstance(value, list):
        for item in value:
            collect_nested_dependencies(result, item)
        return
    add_dependency_item(result, value)


def add_dependency_item(result: set[str], item: Any) -> None:
    if isinstance(item, dict):
        item = item.get("name") or item.get("spec") or item.get("value") or item.get("package")
    value = field_value(item)
    if value in {None, "", "record_only"}:
        return
    name = normalize_package_name(value)
    if name:
        result.add(name)


def language_detection_accuracy(gold: dict[str, Any], env: dict[str, Any]) -> float:
    language = gold.get("language") or {}
    expected_python = bool(language.get("python"))
    expected_r = bool(language.get("r"))
    observed_python = bool(((env.get("python") or {}).get("packages") or []))
    observed_r = bool((env.get("r") or {}).get("required") or ((env.get("r") or {}).get("packages") or []))
    checks = []
    if expected_python or expected_r:
        checks.append(expected_python == observed_python or (not expected_python and not observed_python))
        checks.append(expected_r == observed_r)
    text = text_blob(env)
    if "rscript" in text and any("rscript" in str(item).lower() for item in as_list(gold.get("system_or_cli"))):
        checks.append(True)
    return sum(1 for item in checks if item) / len(checks) if checks else 1.0
