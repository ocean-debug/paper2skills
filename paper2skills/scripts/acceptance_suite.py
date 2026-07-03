"""Static acceptance suite for routing, contracts, and refusals."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def route_case(route: dict[str, Any]) -> dict[str, Any]:
    task_type = str(route.get("task_type"))
    return {
        "case_id": f"accept:{slugify(task_type)}:route",
        "kind": "task_type_routing",
        "task_type": task_type,
        "prompt_shape": "User asks for a documented package workflow matching the route cues.",
        "expected_decision": "select_task_type",
        "expected_task_type": task_type,
        "must_check": [
            "user goal matches at least one choose_when cue",
            "input modality and format are known",
            "required metadata roles are present or explicitly requested",
        ],
        "evidence_refs": route.get("evidence_refs", []),
    }


def refusal_case(task: dict[str, Any], boundary: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    reason_key = str(boundary.get("reason_key"))
    return {
        "case_id": f"accept:{slugify(task_type)}:refuse:{slugify(reason_key)}",
        "kind": "structured_refusal",
        "task_type": task_type,
        "prompt_shape": boundary.get("when"),
        "expected_decision": "refuse",
        "expected_reason_key": reason_key,
        "expected_refusal_type": boundary.get("refusal_type"),
        "must_check": [
            "do not invent missing fields",
            "return structured refusal template",
            "include a fix when refusal_type is fixable",
        ],
        "evidence_refs": task.get("evidence_refs", []),
    }


def contract_case(task: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type"))
    input_contract = task.get("input_contract") or {}
    output_contract = task.get("output_contract") or {}
    return {
        "case_id": f"accept:{slugify(task_type)}:contract",
        "kind": "input_output_contract",
        "task_type": task_type,
        "prompt_shape": "User provides a task goal plus all required inputs for this task_type.",
        "expected_decision": "accept_for_planning",
        "required_inputs": input_contract.get("required_from_user", []),
        "must_confirm": input_contract.get("must_confirm", []),
        "expected_outputs": output_contract.get("expected_outputs", []),
        "validation_checks": output_contract.get("minimum_validation", []),
        "evidence_refs": task.get("evidence_refs", []),
    }


def ambiguity_case(pair: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": f"accept:ambiguity:{slugify(str(pair.get('task_type_a')))}:{slugify(str(pair.get('task_type_b')))}",
        "kind": "ambiguity_resolution",
        "task_type_a": pair.get("task_type_a"),
        "task_type_b": pair.get("task_type_b"),
        "prompt_shape": "User goal can plausibly match both task_type entries.",
        "expected_decision": "ask_clarifying_question",
        "selection_rule": pair.get("selection_rule"),
        "ask_when": pair.get("ask_when", []),
        "conflict_level": pair.get("conflict_level"),
    }


def execution_boundary_case(task_plan: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task_plan.get("task_type"))
    return {
        "case_id": f"accept:{slugify(task_type)}:execution-boundary",
        "kind": "execution_boundary",
        "task_type": task_type,
        "prompt_shape": "User asks to run or verify the workflow.",
        "expected_decision": "require_explicit_execution_approval",
        "planned_action": task_plan.get("planned_action"),
        "must_check": task_plan.get("preflight_checks", []),
        "success_criteria": task_plan.get("success_criteria", []),
        "refusal_if_missing": task_plan.get("refusal_if_missing", []),
    }


def tutorial_reproduction_case(replay: dict[str, Any]) -> dict[str, Any]:
    task_type = str(replay.get("task_type"))
    return {
        "case_id": f"accept:{slugify(task_type)}:tutorial-reproduction",
        "kind": "tutorial_reproduction_plan",
        "task_type": task_type,
        "prompt_shape": "User asks to reproduce a tutorial/example path for this task_type.",
        "expected_decision": "require_explicit_execution_approval",
        "replay_id": replay.get("replay_id"),
        "status": replay.get("status"),
        "must_check": [
            "execution approval is explicit",
            "environment fields are complete",
            "trace requirements are recorded before claiming verified status",
        ],
        "tutorial_replay_sources": [
            source.get("tutorial_id")
            for source in replay.get("tutorial_replay_sources", [])
            if source.get("tutorial_id")
        ],
        "trace_requirements": replay.get("trace_requirements", []),
        "success_criteria": replay.get("success_criteria", []),
        "refusal_if_missing": replay.get("refusal_if_missing", []),
    }


def traceability_case(task_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": f"accept:{slugify(task_type)}:contract-traceability",
        "kind": "contract_traceability",
        "task_type": task_type,
        "prompt_shape": "Reviewer checks whether generated task contracts are evidence-linked.",
        "expected_decision": "review_contract_evidence_refs",
        "contract_record_count": len(records),
        "must_check": [
            "each required input contract has evidence_refs",
            "each expected output contract has evidence_refs",
            "each validation check has evidence_refs",
            "each refusal boundary has evidence_refs",
        ],
        "evidence_refs": sorted({ref for record in records for ref in record.get("evidence_refs", [])}),
    }


def eval_case(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": f"accept:{slugify(str(scenario.get('scenario_id')))}",
        "kind": f"eval_{scenario.get('kind')}",
        "task_type": scenario.get("task_type"),
        "prompt_shape": scenario.get("purpose"),
        "expected_decision": "review_contract",
        "required_inputs": scenario.get("required_inputs", []),
        "validation_checks": scenario.get("validation_checks", []),
        "expected_refusal_reason": scenario.get("expected_refusal_reason"),
        "evidence_refs": scenario.get("evidence_refs", []),
    }


def build_acceptance_suite(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    task_conflict_matrix: dict[str, Any],
    eval_plan: dict[str, Any],
    execution_plan: dict[str, Any],
    tutorial_reproduction_plan: dict[str, Any] | None = None,
    contract_traceability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    cases.extend(route_case(route) for route in router.get("routes", []))
    for task in task_catalog.get("tasks", []):
        cases.append(contract_case(task))
        for boundary in task.get("refusal_boundaries", []):
            cases.append(refusal_case(task, boundary))
    cases.extend(ambiguity_case(pair) for pair in task_conflict_matrix.get("pairs", []))
    cases.extend(eval_case(scenario) for scenario in eval_plan.get("scenarios", []))
    cases.extend(execution_boundary_case(task) for task in execution_plan.get("tasks", []))
    if tutorial_reproduction_plan:
        cases.extend(tutorial_reproduction_case(replay) for replay in tutorial_reproduction_plan.get("replays", []))
    if contract_traceability:
        records_by_task: dict[str, list[dict[str, Any]]] = {}
        for record_item in contract_traceability.get("records", []):
            records_by_task.setdefault(str(record_item.get("task_type")), []).append(record_item)
        for task_type, records in sorted(records_by_task.items()):
            cases.append(traceability_case(task_type, records))
    kinds = sorted({str(case.get("kind")) for case in cases})
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "case_count": len(cases),
        "case_kinds": kinds,
        "cases": cases,
        "policy": [
            "Acceptance cases are static and do not execute package code.",
            "Passing the acceptance suite means the generated skill routes, asks, refuses, and validates according to its contracts.",
            "Execution-boundary cases require explicit user approval and trace capture before they can verify runtime behavior.",
        ],
    }
