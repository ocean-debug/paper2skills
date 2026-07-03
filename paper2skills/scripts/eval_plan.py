"""Build static evaluation-plan artifacts for generated child skills."""

from __future__ import annotations

from typing import Any

from common import now_utc, slugify
from constants import SCHEMA_VERSION


def scenario(
    task_type: str,
    kind: str,
    purpose: str,
    evidence_refs: list[str],
    required_inputs: list[str] | None = None,
    validation_checks: list[str] | None = None,
    refusal_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": f"eval:{slugify(task_type)}:{slugify(kind)}",
        "task_type": task_type,
        "kind": kind,
        "purpose": purpose,
        "required_inputs": required_inputs or [],
        "validation_checks": validation_checks or [],
        "expected_refusal_reason": refusal_reason,
        "evidence_refs": evidence_refs,
        "execution_required": False,
    }


def build_eval_plan(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    interface_grounding: dict[str, Any],
) -> dict[str, Any]:
    scenarios = []
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        evidence_refs = list(task.get("evidence_refs", []))
        interface_refs = interface_grounding.get("by_task_type", {}).get(task_type, {}).get("interfaces", [])
        required_inputs = list(task.get("input_contract", {}).get("required_from_user", []))
        validation_checks = list(task.get("output_contract", {}).get("minimum_validation", []))
        scenarios.append(
            scenario(
                task_type,
                "contract_acceptance",
                "Check that a valid request can be mapped to the task_type and its input-output contract.",
                evidence_refs,
                required_inputs=required_inputs,
                validation_checks=validation_checks,
            )
        )
        scenarios.append(
            scenario(
                task_type,
                "structured_refusal",
                "Check that missing or unsupported inputs trigger a structured refusal instead of guessed execution.",
                evidence_refs,
                refusal_reason="missing_required_input or unsupported_task_type",
            )
        )
        if interface_refs:
            scenarios.append(
                scenario(
                    task_type,
                    "api_grounding_review",
                    "Check that selected API/interface hints are consistent with the task contract before use.",
                    evidence_refs,
                    validation_checks=["referenced interfaces exist in interface_grounding.yaml"],
                )
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "notes": [
            "The eval plan is static by default and does not execute package code.",
            "Execution-grounded scenarios require explicit user environment approval and trace capture.",
        ],
    }
