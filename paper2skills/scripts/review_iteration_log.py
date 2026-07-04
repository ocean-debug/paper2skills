"""Human-readable review iteration log renderer."""

from __future__ import annotations

from typing import Any

from common import md_table, now_utc
from constants import SCHEMA_VERSION


def _text(value: Any) -> str:
    return str(value if value is not None else "unknown")


def _top_findings(findings: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(
        findings,
        key=lambda item: 0 if item.get("severity") == "error" else 1 if item.get("severity") == "warning" else 2,
    )
    return [
        {
            "severity": item.get("severity"),
            "code": item.get("code") or item.get("check"),
            "task_type": item.get("task_type"),
            "message": item.get("message"),
        }
        for item in ranked[:limit]
    ]


def _patch_artifacts(actions: list[dict[str, Any]]) -> list[str]:
    return sorted({str(action.get("artifact")) for action in actions if action.get("artifact")})


def _gate_reason(iteration: dict[str, Any]) -> str | None:
    gate = next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})
    return gate.get("reason")


def iteration_summary(iteration: dict[str, Any]) -> dict[str, Any]:
    patch = iteration.get("patch") or {}
    actions = patch.get("actions") or []
    findings = iteration.get("findings") or []
    return {
        "iteration": iteration.get("iteration"),
        "created_at": iteration.get("created_at"),
        "score": iteration.get("score"),
        "total": iteration.get("total"),
        "score_ratio": iteration.get("score_ratio"),
        "blocking": bool(iteration.get("blocking")),
        "passed": bool(iteration.get("passed")),
        "finding_count": len(findings),
        "top_findings": _top_findings(findings),
        "patch_changed": bool(patch.get("changed")),
        "patch_summary": patch.get("patch_summary"),
        "patch_action_count": len(actions),
        "patch_artifacts": _patch_artifacts(actions),
        "gate_reason": _gate_reason(iteration),
    }


def build_review_iteration_log(
    request: dict[str, Any],
    review_result: dict[str, Any],
    review_evolution: dict[str, Any],
    patch_application: dict[str, Any],
) -> dict[str, Any]:
    """Build metadata for the Markdown review iteration log."""
    iterations = [iteration_summary(item) for item in review_result.get("iterations", [])]
    findings: list[dict[str, Any]] = []
    if review_evolution.get("iteration_count") != len(iterations):
        findings.append(
            {
                "severity": "error",
                "code": "review_iteration_count_mismatch",
                "message": "review_evolution iteration_count does not match review_result iterations.",
            }
        )
    if patch_application.get("iteration_count") != len(iterations):
        findings.append(
            {
                "severity": "error",
                "code": "patch_iteration_count_mismatch",
                "message": "patch_application iteration_count does not match review_result iterations.",
            }
        )

    has_errors = any(finding.get("severity") == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "markdown_path": "review_iteration_log.md",
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "iteration_count": len(iterations),
        "changed_iteration_count": sum(1 for item in iterations if item.get("patch_changed")),
        "passed_iteration_count": sum(1 for item in iterations if item.get("passed")),
        "final_score": review_result.get("final_score", {}),
        "iterations": iterations,
        "findings": findings,
        "policy": [
            "Review iteration log is a run artifact only; it is not copied into the public child skill.",
            "The Markdown log summarizes review_iterations.jsonl without replacing the machine-readable review artifacts.",
            "The log must not introduce new claims, patch actions, or publish decisions.",
        ],
    }


def render_review_iteration_log_markdown(log: dict[str, Any]) -> str:
    """Render a compact Markdown review iteration log."""
    title = log.get("method_name") or log.get("package_name") or "Papert2Skills"
    summary_rows = [
        ["Review status", _text(log.get("review_status"))],
        ["Stop reason", _text(log.get("stop_reason"))],
        ["Iterations", _text(log.get("iteration_count"))],
        ["Changed iterations", _text(log.get("changed_iteration_count"))],
        ["Passed iterations", _text(log.get("passed_iteration_count"))],
    ]
    lines = [
        f"# {title} Review Iteration Log",
        "This run artifact summarizes the agent-driven self-review loop for human audit.",
        "## Summary",
        md_table(["Field", "Value"], summary_rows),
    ]

    for item in log.get("iterations", []):
        score = f"{_text(item.get('score'))}/{_text(item.get('total'))} ({_text(item.get('score_ratio'))})"
        patch_artifacts = ", ".join(item.get("patch_artifacts") or []) or "none"
        iteration_rows = [
            ["Created at", _text(item.get("created_at"))],
            ["Score", score],
            ["Blocking", _text(item.get("blocking"))],
            ["Passed", _text(item.get("passed"))],
            ["Finding count", _text(item.get("finding_count"))],
            ["Patch changed", _text(item.get("patch_changed"))],
            ["Patch action count", _text(item.get("patch_action_count"))],
            ["Patch artifacts", patch_artifacts],
            ["Gate reason", _text(item.get("gate_reason"))],
            ["Patch summary", _text(item.get("patch_summary"))],
        ]
        finding_rows = [
            [
                _text(finding.get("severity")),
                _text(finding.get("code")),
                _text(finding.get("task_type")),
                _text(finding.get("message")),
            ]
            for finding in item.get("top_findings", [])
        ]
        if not finding_rows:
            finding_rows = [["info", "none", "none", "No findings were recorded for this iteration."]]
        lines.extend(
            [
                f"## Iteration {item.get('iteration')}",
                md_table(["Field", "Value"], iteration_rows),
                "### Top Findings",
                md_table(["Severity", "Code", "Task Type", "Message"], finding_rows),
            ]
        )

    return "\n\n".join(lines) + "\n"
