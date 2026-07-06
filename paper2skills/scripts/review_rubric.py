"""Rubric scoring for source-grounded child skill drafts."""

from __future__ import annotations

from typing import Any


RUBRIC_ITEMS = [
    "source_grounding",
    "api_grounding",
    "interface_grounding",
    "environment_contract",
    "tutorial_catalog",
    "parameter_constraints",
    "operational_recipes",
    "task_partition",
    "task_routing",
    "input_contracts",
    "output_contracts",
    "refusal_boundaries",
    "validation_rules",
    "verification_labels",
]


def item_result(
    item: str,
    status: str,
    points: int,
    evidence: list[str] | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "item": item,
        "status": status,
        "points": points,
        "evidence": evidence or [],
        "message": message,
    }


def score_artifacts(
    source_grounding: dict[str, Any],
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    evidence_cards: dict[str, Any],
    api_grounding: dict[str, Any] | None = None,
    interface_grounding: dict[str, Any] | None = None,
    environment_spec: dict[str, Any] | None = None,
    tutorial_catalog: dict[str, Any] | None = None,
    parameter_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings = []
    item_results: list[dict[str, Any]] = []
    score = 0
    total = len(RUBRIC_ITEMS)

    if source_grounding.get("sources"):
        score += 1
        item_results.append(item_result("source_grounding", "pass", 1, ["source_grounding.sources"]))
    else:
        findings.append({"severity": "error", "check": "source_grounding", "message": "No official sources recorded."})
        item_results.append(item_result("source_grounding", "fail", 0, [], "No official sources recorded."))

    if api_grounding is None or api_grounding.get("api_candidate_count", 0) > 0 or not evidence_cards.get("cards"):
        score += 1
        evidence = ["api_grounding.api_candidates"] if api_grounding and api_grounding.get("api_candidate_count", 0) > 0 else ["not_applicable:no_evidence_cards"]
        item_results.append(item_result("api_grounding", "pass", 1, evidence))
    else:
        findings.append({"severity": "warning", "check": "api_grounding", "message": "Parsed evidence exists, but no API candidates were derived."})
        item_results.append(item_result("api_grounding", "warn", 0, ["evidence_cards.cards"], "Parsed evidence exists, but no API candidates were derived."))

    if (
        interface_grounding is None
        or interface_grounding.get("interface_count", 0) > 0
        or not api_grounding
        or api_grounding.get("api_candidate_count", 0) == 0
    ):
        score += 1
        evidence = (
            ["interface_grounding.interfaces"]
            if interface_grounding and interface_grounding.get("interface_count", 0) > 0
            else ["not_applicable:no_api_candidates"]
        )
        item_results.append(item_result("interface_grounding", "pass", 1, evidence))
    else:
        findings.append(
            {
                "severity": "warning",
                "check": "interface_grounding",
                "message": "API candidates exist, but no Python interfaces were statically inspected.",
            }
        )
        item_results.append(
            item_result(
                "interface_grounding",
                "warn",
                0,
                ["api_grounding.api_candidates"],
                "API candidates exist, but no Python interfaces were statically inspected.",
            )
        )

    if environment_spec is None or environment_spec.get("declared_dependencies") or environment_spec.get("imported_modules"):
        score += 1
        evidence = []
        if environment_spec is None:
            evidence = ["not_available:environment_spec_not_supplied"]
        elif environment_spec.get("declared_dependencies"):
            evidence.append("environment_spec.declared_dependencies")
        elif environment_spec.get("imported_modules"):
            evidence.append("environment_spec.imported_modules")
        item_results.append(item_result("environment_contract", "pass", 1, evidence))
    else:
        score += 1
        findings.append({"severity": "warning", "check": "environment_contract", "message": "No dependency or import hints were mined."})
        item_results.append(item_result("environment_contract", "pass_with_warning", 1, ["environment_spec"], "No dependency or import hints were mined."))

    if tutorial_catalog is None or tutorial_catalog.get("tutorial_count", 0) > 0:
        score += 1
        evidence = ["tutorial_catalog.tutorials"] if tutorial_catalog and tutorial_catalog.get("tutorial_count", 0) > 0 else ["not_available:tutorial_catalog_not_supplied"]
        item_results.append(item_result("tutorial_catalog", "pass", 1, evidence))
    else:
        score += 1
        findings.append({"severity": "warning", "check": "tutorial_catalog", "message": "No tutorial or example steps were mined."})
        item_results.append(item_result("tutorial_catalog", "pass_with_warning", 1, ["tutorial_catalog"], "No tutorial or example steps were mined."))

    if parameter_catalog is None or parameter_catalog.get("parameter_count", 0) > 0 or not interface_grounding or interface_grounding.get("interface_count", 0) == 0:
        score += 1
        if parameter_catalog and parameter_catalog.get("parameter_count", 0) > 0:
            evidence = ["parameter_catalog.parameters"]
        elif interface_grounding and interface_grounding.get("interface_count", 0) == 0:
            evidence = ["not_applicable:no_interface_grounding"]
        else:
            evidence = ["not_available:parameter_catalog_not_supplied"]
        item_results.append(item_result("parameter_constraints", "pass", 1, evidence))
    else:
        score += 1
        findings.append({"severity": "warning", "check": "parameter_constraints", "message": "Interfaces were inspected, but no parameters were mined."})
        item_results.append(item_result("parameter_constraints", "pass_with_warning", 1, ["interface_grounding.interfaces"], "Interfaces were inspected, but no parameters were mined."))

    tasks = task_catalog.get("tasks", [])
    missing_recipes = [
        task.get("task_type")
        for task in tasks
        if not task.get("operational_recipe") or not task.get("operational_recipe", {}).get("workflow_steps")
    ]
    abstract_recipes = [
        task.get("task_type")
        for task in tasks
        if task.get("operational_recipe") and not task.get("operational_recipe", {}).get("api_sequence")
    ]
    needs_agent_review_recipes = [
        task.get("task_type")
        for task in tasks
        if task.get("operational_recipe", {}).get("status") == "needs_agent_review"
    ]
    if tasks and not missing_recipes and not abstract_recipes and not needs_agent_review_recipes:
        score += 1
        item_results.append(
            item_result(
                "operational_recipes",
                "pass",
                1,
                ["task_catalog.tasks.operational_recipe.api_sequence"],
                "",
            )
        )
    else:
        failing_tasks = sorted({str(task) for task in missing_recipes + abstract_recipes + needs_agent_review_recipes if task})
        findings.append(
            {
                "severity": "error",
                "check": "operational_recipes",
                "message": "Task entries must include execution-ready operational recipes with source-grounded API sequences before drafting.",
                "task_types": failing_tasks,
            }
        )
        item_results.append(
            item_result(
                "operational_recipes",
                "fail",
                0,
                ["task_catalog.tasks"],
                "Task entries must include execution-ready operational recipes with source-grounded API sequences before drafting.",
            )
        )

    if task_catalog.get("tasks"):
        fallback_tasks = [task.get("task_type") for task in task_catalog.get("tasks", []) if task.get("evidence_support") == "fallback_only"]
        if fallback_tasks:
            findings.append(
                {
                    "severity": "error",
                    "check": "task_partition",
                    "message": "Some task_type entries have only fallback package-level evidence.",
                    "task_types": fallback_tasks,
                }
            )
            item_results.append(item_result("task_partition", "fail", 0, ["task_catalog.tasks"], "Task_type entries require task-specific evidence."))
        else:
            score += 1
            item_results.append(item_result("task_partition", "pass", 1, ["task_catalog.tasks"]))
    else:
        findings.append({"severity": "error", "check": "task_partition", "message": "No task_type entries produced."})
        item_results.append(item_result("task_partition", "fail", 0, [], "No task_type entries produced."))

    if router.get("routes"):
        score += 1
        item_results.append(item_result("task_routing", "pass", 1, ["task_type_router.routes"]))
    else:
        findings.append({"severity": "error", "check": "task_routing", "message": "No task_type routes produced."})
        item_results.append(item_result("task_routing", "fail", 0, [], "No task_type routes produced."))

    if tasks and all(task.get("input_contract", {}).get("evidence_observed") or task.get("evidence_refs") for task in tasks):
        score += 1
        item_results.append(item_result("input_contracts", "pass", 1, ["task_catalog.tasks.input_contract", "task_catalog.tasks.evidence_refs"]))
    else:
        findings.append({"severity": "warning", "check": "input_contracts", "message": "Some input contracts are not grounded in parsed evidence cards."})
        item_results.append(item_result("input_contracts", "warn", 0, ["task_catalog.tasks"], "Some input contracts are not grounded in parsed evidence cards."))

    if tasks and all(task.get("output_contract", {}).get("evidence_observed") or task.get("evidence_refs") for task in tasks):
        score += 1
        item_results.append(item_result("output_contracts", "pass", 1, ["task_catalog.tasks.output_contract", "task_catalog.tasks.evidence_refs"]))
    else:
        findings.append({"severity": "warning", "check": "output_contracts", "message": "Some output contracts are not grounded in parsed evidence cards."})
        item_results.append(item_result("output_contracts", "warn", 0, ["task_catalog.tasks"], "Some output contracts are not grounded in parsed evidence cards."))

    if tasks and all(task.get("refusal_boundaries") for task in tasks):
        score += 1
        item_results.append(item_result("refusal_boundaries", "pass", 1, ["task_catalog.tasks.refusal_boundaries"]))
    else:
        findings.append({"severity": "error", "check": "refusal_boundaries", "message": "Missing refusal boundaries."})
        item_results.append(item_result("refusal_boundaries", "fail", 0, ["task_catalog.tasks"], "Missing refusal boundaries."))

    if tasks and all(task.get("output_contract", {}).get("minimum_validation") for task in tasks):
        score += 1
        item_results.append(item_result("validation_rules", "pass", 1, ["task_catalog.tasks.output_contract.minimum_validation"]))
    else:
        findings.append({"severity": "error", "check": "validation_rules", "message": "Missing validation rules."})
        item_results.append(item_result("validation_rules", "fail", 0, ["task_catalog.tasks"], "Missing validation rules."))

    bad_verified = [
        task.get("task_type")
        for task in tasks
        if task.get("verification_status") == "execution_verified" and not task.get("trace_ref")
    ]
    if not bad_verified:
        score += 1
        item_results.append(item_result("verification_labels", "pass", 1, ["task_catalog.tasks.verification_status"]))
    else:
        findings.append(
            {
                "severity": "error",
                "check": "verification_labels",
                "message": "execution_verified task types require trace_ref.",
                "task_types": bad_verified,
            }
        )
        item_results.append(item_result("verification_labels", "fail", 0, ["task_catalog.tasks.verification_status"], "execution_verified task types require trace_ref."))

    return {
        "score": score,
        "total": total,
        "score_ratio": score / total if total else 0,
        "findings": findings,
        "rubric_items": RUBRIC_ITEMS,
        "item_results": item_results,
    }
