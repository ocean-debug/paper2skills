"""Build a non-executing acceptance handoff package."""

from __future__ import annotations

from typing import Any

from common import md_table, now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def rollout_template(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "rollout_id": case.get("rollout_id"),
        "scenario_id": case.get("scenario_id"),
        "source_case_id": case.get("source_case_id"),
        "kind": case.get("kind"),
        "task_type": case.get("task_type"),
        "status": None,
        "observed_decision": None,
        "observed_task_type": None,
        "observed_reason_key": None,
        "satisfied_judge_checks": [],
        "failed_judge_checks": [],
        "notes": [],
        "source_run_id": None,
    }


def replay_template(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "replay_id": job.get("replay_id"),
        "job_id": job.get("job_id"),
        "task_type": job.get("task_type"),
        "status": None,
        "trace_ref": None,
        "environment": job.get("environment", {}),
        "inputs": [],
        "outputs": [],
        "validation_checks": [],
        "package_versions": {},
        "command": None,
        "notebook": None,
        "script": None,
        "failure_reason": None,
        "notes": [],
        "source_run_id": None,
    }


def handoff_items(
    e2e_acceptance: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for template in e2e_acceptance.get("result_templates", []):
        items.append(
            {
                "handoff_id": f"handoff:e2e:{template.get('scenario_id')}",
                "kind": "e2e_acceptance_result",
                "target_request_field": "e2e_acceptance_results",
                "template": template,
            }
        )
    for case in agent_rollout_harness.get("cases", []):
        items.append(
            {
                "handoff_id": f"handoff:rollout:{case.get('rollout_id') or case.get('scenario_id')}",
                "kind": "agent_rollout_result",
                "target_request_field": "agent_rollout_results",
                "template": rollout_template(case),
            }
        )
    for job in execution_replay_orchestrator.get("jobs", []):
        items.append(
            {
                "handoff_id": f"handoff:replay:{job.get('job_id') or job.get('replay_id')}",
                "kind": "execution_replay_result",
                "target_request_field": "execution_replay_results",
                "template": replay_template(job),
                "blocked_reasons": job.get("blocked_reasons", []),
            }
        )
    return items


def build_acceptance_handoff(
    request: dict[str, Any],
    e2e_acceptance: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
    completion_evidence_audit: dict[str, Any],
    publish_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return result templates and instructions for external acceptance work."""
    findings: list[dict[str, Any]] = []
    publish_manifest = publish_manifest or {}
    items = handoff_items(e2e_acceptance, agent_rollout_harness, execution_replay_orchestrator)
    if e2e_acceptance.get("status") == "fail":
        add_finding(findings, "error", "e2e_acceptance_failed", "Acceptance handoff requires a passing E2E acceptance plan.")
    if agent_rollout_harness.get("status") == "fail":
        add_finding(findings, "error", "agent_rollout_harness_failed", "Acceptance handoff requires a passing rollout harness.")
    if execution_replay_orchestrator.get("status") == "fail":
        add_finding(findings, "error", "execution_replay_orchestrator_failed", "Acceptance handoff requires a passing replay orchestrator.")
    if not items:
        add_finding(findings, "error", "empty_acceptance_handoff", "Acceptance handoff has no result templates.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "publish_manifest_status": publish_manifest.get("status"),
        "publish_manifest_supplied": bool(publish_manifest),
        "completion_claim_verdict": completion_evidence_audit.get("claim_verdict"),
        "can_claim_full_goal_complete": completion_evidence_audit.get("can_claim_full_goal_complete"),
        "handoff_item_count": len(items),
        "e2e_template_count": len(e2e_acceptance.get("result_templates", [])),
        "rollout_template_count": len(agent_rollout_harness.get("cases", [])),
        "replay_template_count": len(execution_replay_orchestrator.get("jobs", [])),
        "target_request_fields": ["agent_rollout_results", "execution_replay_results", "e2e_acceptance_results"],
        "handoff_items": items,
        "findings": findings,
        "policy": [
            "Acceptance handoff is plan-only and never runs package code, launches agents, installs environments, or mutates build outputs.",
            "Filled templates should be copied back into the build request external result fields and audited by the existing result judges.",
            "A handoff package is not validation evidence until the filled results are supplied and pass their corresponding audits.",
        ],
    }


def render_acceptance_handoff_markdown(handoff: dict[str, Any]) -> str:
    """Render a compact handoff checklist for human operators."""
    rows = [
        ["Claim verdict", str(handoff.get("completion_claim_verdict") or "unknown")],
        ["Full goal complete", str(handoff.get("can_claim_full_goal_complete"))],
        ["Handoff items", str(handoff.get("handoff_item_count", 0))],
        ["E2E templates", str(handoff.get("e2e_template_count", 0))],
        ["Rollout templates", str(handoff.get("rollout_template_count", 0))],
        ["Replay templates", str(handoff.get("replay_template_count", 0))],
    ]
    item_rows = []
    for item in handoff.get("handoff_items", [])[:25]:
        item_rows.append(
            [
                str(item.get("kind") or "unknown"),
                str(item.get("target_request_field") or "unknown"),
                str(item.get("handoff_id") or "unknown"),
            ]
        )
    if not item_rows:
        item_rows = [["none", "none", "No handoff items were generated."]]
    return "\n\n".join(
        [
            f"# {handoff.get('method_name') or handoff.get('package_name') or 'Papert2Skills'} Acceptance Handoff",
            "This run artifact lists external validation results that must be filled before full completion can be claimed.",
            "## Summary",
            md_table(["Field", "Value"], rows),
            "## Result Templates",
            md_table(["Kind", "Request Field", "Handoff ID"], item_rows),
            "## How To Use",
            "Fill the templates in `acceptance_handoff.yaml`, copy the observed results into the matching build request fields, then rerun the relevant static result audits.",
            "",
        ]
    )
