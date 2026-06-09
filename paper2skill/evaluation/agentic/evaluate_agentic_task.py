from __future__ import annotations

from typing import Any

from paper2skill.evaluation.agentic.mock_agent import decide_action
from paper2skill.evaluation.agentic.trace_evaluator import evaluate_trace
from paper2skill.evaluation.load_gold import evaluation_result, finish_result


def evaluate_agentic_tasks(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("agentic_usage")
    tasks = gold.get("tasks") or []
    if not tasks:
        return finish_result(result, {"agentic_tasks_defined": 1.0})
    reports = []
    scores = []
    for task in tasks:
        trace = task.get("saved_trace") or decide_action(task, generated)
        report = evaluate_trace(task, trace)
        report["task_id"] = task.get("task_id")
        report["action"] = trace.get("action")
        reports.append(report)
        scores.append(1.0 if report["passed"] else 0.0)
        result["mismatched_items"].extend(report["mismatched_items"])
    result["tasks"] = reports
    return finish_result(
        result,
        {
            "task_intent_classification_accuracy": sum(scores) / len(scores),
            "safe_refusal_or_execution_accuracy": sum(scores) / len(scores),
            "contract_reference_rate": contract_reference_rate(reports),
        },
    )


def contract_reference_rate(reports: list[dict[str, Any]]) -> float:
    if not reports:
        return 1.0
    matched = 0
    for report in reports:
        if not any(item.get("field") == "must_reference" for item in report.get("mismatched_items", [])):
            matched += 1
    return matched / len(reports)
