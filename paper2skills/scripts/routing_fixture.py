"""Build static task_type routing fixtures for generated child skills."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def route_select_case(route: dict[str, Any]) -> dict[str, Any]:
    task_type = str(route.get("task_type"))
    return {
        "case_id": f"route-fixture:{slugify(task_type)}:select",
        "kind": "select_task_type",
        "prompt_shape": "User asks for a documented package workflow that matches the route cues.",
        "expected_decision": "select",
        "expected_task_type": task_type,
        "required_checks": [
            "match user intent to choose_when cues",
            "confirm required modality or data format",
            "confirm required metadata before execution planning",
        ],
        "route_priority": route.get("priority"),
        "evidence_refs": route.get("evidence_refs", []),
    }


def route_refusal_case(task: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    boundaries = task.get("refusal_boundaries", [])
    reason = boundaries[0] if boundaries else {}
    return {
        "case_id": f"route-fixture:{slugify(task_type)}:refuse",
        "kind": "structured_refusal",
        "prompt_shape": "User asks for this task_type but omits required data, metadata, or backend support.",
        "expected_decision": "refuse",
        "expected_task_type": task_type,
        "expected_reason_key": reason.get("reason_key", "missing_required_input"),
        "required_checks": [
            "do not choose a task_type when required inputs are missing",
            "return a structured refusal with reason_key and fix",
        ],
        "evidence_refs": task.get("evidence_refs", []),
    }


def ambiguity_case(pair: dict[str, Any]) -> dict[str, Any]:
    task_type_a = str(pair.get("task_type_a"))
    task_type_b = str(pair.get("task_type_b"))
    return {
        "case_id": f"route-fixture:ambiguity:{slugify(task_type_a)}:{slugify(task_type_b)}",
        "kind": "ask_on_ambiguity",
        "prompt_shape": "User goal can plausibly match both task_type entries.",
        "expected_decision": "ask",
        "candidate_task_types": [task_type_a, task_type_b],
        "selection_rule": pair.get("selection_rule"),
        "required_checks": pair.get("ask_when", []),
        "conflict_level": pair.get("conflict_level"),
    }


def unsupported_case(task_catalog: dict[str, Any]) -> dict[str, Any]:
    task_types = [task.get("task_type") for task in task_catalog.get("tasks", [])]
    return {
        "case_id": "route-fixture:unsupported-task",
        "kind": "unsupported_task",
        "prompt_shape": "User asks for a workflow outside all evidence-backed task_type entries.",
        "expected_decision": "refuse",
        "expected_reason_key": "unsupported_task_type",
        "known_task_types": task_types,
        "required_checks": [
            "do not invent a new task_type",
            "offer the closest supported task_type only if the input contract can be met",
        ],
    }


def build_routing_fixture(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    task_conflict_matrix: dict[str, Any],
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    route_by_task = {route.get("task_type"): route for route in router.get("routes", [])}
    for task in task_catalog.get("tasks", []):
        route = route_by_task.get(task.get("task_type"))
        if route:
            cases.append(route_select_case(route))
        cases.append(route_refusal_case(task))
    cases.extend(ambiguity_case(pair) for pair in task_conflict_matrix.get("pairs", []))
    cases.append(unsupported_case(task_catalog))
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "case_count": len(cases),
        "case_kinds": sorted({str(case.get("kind")) for case in cases}),
        "cases": cases,
        "policy": [
            "Routing fixtures test task_type selection inside one child skill.",
            "Fixtures are static and do not execute package code.",
            "Ambiguous or unsupported requests must ask or refuse instead of selecting by guess.",
        ],
    }
