"""Task-type conflict and ambiguity matrix."""

from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def words(values: list[Any]) -> set[str]:
    text = " ".join(str(value).lower() for value in values if value)
    return {word for word in re.findall(r"[a-z][a-z0-9_]{2,}", text) if word not in {"the", "and", "for", "with"}}


def task_words(task: dict[str, Any]) -> set[str]:
    input_contract = task.get("input_contract", {})
    output_contract = task.get("output_contract", {})
    return words(
        [task.get("task_type"), task.get("capability_name")]
        + task.get("routing_cues", [])
        + input_contract.get("required_from_user", [])
        + input_contract.get("must_confirm", [])
        + output_contract.get("expected_outputs", [])
    )


def conflict_level(overlap_count: int, task_a: dict[str, Any], task_b: dict[str, Any]) -> str:
    if task_a.get("verification_status") != task_b.get("verification_status") and overlap_count > 0:
        return "prefer_verified_if_applicable"
    if overlap_count >= 6:
        return "high_ambiguity"
    if overlap_count >= 3:
        return "medium_ambiguity"
    if overlap_count > 0:
        return "low_overlap"
    return "distinct"


def build_task_conflict_matrix(task_catalog: dict[str, Any], router: dict[str, Any]) -> dict[str, Any]:
    tasks = task_catalog.get("tasks", [])
    route_priority = {route.get("task_type"): route.get("priority") for route in router.get("routes", [])}
    pairs = []
    for task_a, task_b in combinations(tasks, 2):
        words_a = task_words(task_a)
        words_b = task_words(task_b)
        overlap = sorted(words_a.intersection(words_b))
        level = conflict_level(len(overlap), task_a, task_b)
        pairs.append(
            {
                "task_type_a": task_a.get("task_type"),
                "task_type_b": task_b.get("task_type"),
                "conflict_level": level,
                "overlap_terms": overlap[:20],
                "selection_rule": selection_rule(task_a, task_b, level, route_priority),
                "ask_when": [
                    "User goal can be interpreted as either task_type.",
                    "Required modality, metadata role, contrast, or output target is missing.",
                ],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": task_catalog.get("package_name"),
        "method_name": task_catalog.get("method_name"),
        "pair_count": len(pairs),
        "pairs": pairs,
        "global_rules": [
            "Select exactly one task_type before planning execution.",
            "Prefer execution_verified over source_grounded only when the user goal and input contract still match.",
            "Ask for the missing modality, metadata role, contrast, or output target when ambiguity remains.",
            "Refuse when no task_type is evidence-backed for the request.",
        ],
    }


def selection_rule(
    task_a: dict[str, Any],
    task_b: dict[str, Any],
    level: str,
    route_priority: dict[str, Any],
) -> str:
    if level == "prefer_verified_if_applicable":
        return "Prefer the execution_verified task only if both input contracts match; otherwise ask."
    if level in {"high_ambiguity", "medium_ambiguity"}:
        return "Ask a clarifying question before choosing."
    priority_a = route_priority.get(task_a.get("task_type"), 9999)
    priority_b = route_priority.get(task_b.get("task_type"), 9999)
    preferred = task_a.get("task_type") if priority_a <= priority_b else task_b.get("task_type")
    return f"Use router priority when both contracts clearly match; default priority favors `{preferred}`."
