"""Deterministic artifact patching for the review loop."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from task_router import build_router


def finding_codes(findings: list[dict[str, Any]], terms: set[str]) -> list[str]:
    codes: list[str] = []
    for finding in findings:
        code = str(finding.get("code") or finding.get("check") or "")
        text = " ".join(str(finding.get(key) or "") for key in ("code", "check", "message")).lower()
        if code and any(term in text for term in terms) and code not in codes:
            codes.append(code)
    if codes:
        return codes
    for finding in findings:
        code = str(finding.get("code") or finding.get("check") or "")
        if code and code not in codes:
            codes.append(code)
        if len(codes) >= 3:
            break
    return codes


def ensure_task_refusals(task: dict[str, Any]) -> bool:
    existing = {item.get("reason_key") for item in task.get("refusal_boundaries", [])}
    changed = False
    required = [
        {
            "reason_key": "missing_required_input",
            "refusal_type": "fixable",
            "when": "Required user input, path, metadata, or parameter is missing.",
        },
        {
            "reason_key": "unsupported_task_type",
            "refusal_type": "unsupported",
            "when": "The requested analysis goal is outside this task_type.",
        },
        {
            "reason_key": "unverified_execution_request",
            "refusal_type": "fixable",
            "when": "The user asks for execution verification, but no successful trace is available.",
        },
    ]
    for item in required:
        if item["reason_key"] not in existing:
            task.setdefault("refusal_boundaries", []).append(item)
            changed = True
    return changed


def ensure_contract_grounding_notes(task: dict[str, Any]) -> bool:
    changed = False
    input_contract = task.setdefault("input_contract", {})
    output_contract = task.setdefault("output_contract", {})
    if not input_contract.get("evidence_observed"):
        input_contract["review_note"] = "No parsed input evidence card was found; keep input requirements as ask-before-run guidance."
        changed = True
    if not output_contract.get("evidence_observed"):
        output_contract["review_note"] = "No parsed output evidence card was found; validate only technical outputs explicitly documented later."
        changed = True
    if not output_contract.get("minimum_validation"):
        output_contract["minimum_validation"] = [
            "expected output exists",
            "output format can be opened by the documented reader",
        ]
        changed = True
    return changed


def enforce_verification_boundaries(task: dict[str, Any]) -> bool:
    if task.get("verification_status") == "execution_verified" and not task.get("trace_ref"):
        task["verification_status"] = "source_grounded"
        task["execution_grounded"] = False
        task["review_note"] = "Downgraded from execution_verified because no trace_ref was available."
        return True
    return False


def task_matches(task: dict[str, Any], task_type: str | None) -> bool:
    return task_type in {None, "", "*"} or str(task.get("task_type")) == str(task_type)


def apply_agent_review_proposal(
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    proposal: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a bounded agent-authored SkillOpt edit proposal."""
    patched_catalog = deepcopy(task_catalog)
    changed = False
    actions: list[dict[str, Any]] = []
    rejected_operations: list[dict[str, Any]] = []
    allowed_operations = {
        "ensure_refusal_boundaries",
        "ensure_contract_grounding_notes",
        "downgrade_execution_verification_without_trace",
        "rebuild_task_type_router",
    }
    operations = proposal.get("operations", [])
    requested_router_rebuild = False
    if not isinstance(operations, list):
        operations = []
        rejected_operations.append(
            {
                "operation": None,
                "reason": "proposal_operations_must_be_list",
            }
        )

    for operation in operations:
        if not isinstance(operation, dict):
            rejected_operations.append({"operation": None, "reason": "operation_must_be_mapping"})
            continue
        op_name = str(operation.get("operation") or "")
        task_type = operation.get("task_type")
        if op_name not in allowed_operations:
            rejected_operations.append(
                {
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": "unsupported_agent_skillopt_operation",
                }
            )
            continue
        if op_name == "rebuild_task_type_router":
            requested_router_rebuild = True
            continue
        matched = False
        for task in patched_catalog.get("tasks", []):
            if not task_matches(task, task_type):
                continue
            matched = True
            task_changed = False
            if op_name == "ensure_refusal_boundaries":
                task_changed = ensure_task_refusals(task)
            elif op_name == "ensure_contract_grounding_notes":
                task_changed = ensure_contract_grounding_notes(task)
            elif op_name == "downgrade_execution_verification_without_trace":
                task_changed = enforce_verification_boundaries(task)
            if task_changed:
                actions.append(
                    {
                        "artifact": "task_catalog",
                        "task_type": task.get("task_type"),
                        "operation": op_name,
                        "action": operation.get("rationale") or f"apply agent proposal operation {op_name}",
                        "proposal_id": proposal.get("proposal_id"),
                        "finding_codes": finding_codes(findings, {op_name.replace("_", " ")}),
                    }
                )
                changed = True
        if not matched:
            rejected_operations.append(
                {
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": "task_type_not_found",
                }
            )

    patched_router = build_router(patched_catalog) if changed else router
    if changed and (requested_router_rebuild or not any(action.get("artifact") == "task_type_router" for action in actions)):
        actions.append(
            {
                "artifact": "task_type_router",
                "operation": "rebuild_task_type_router",
                "action": "rebuild routes from agent-reviewed task catalog",
                "proposal_id": proposal.get("proposal_id"),
                "source_artifacts": ["task_catalog"],
                "finding_codes": finding_codes(findings, {"routing", "task"}),
            }
        )
    return {
        "changed": changed,
        "task_catalog": patched_catalog,
        "router": patched_router,
        "actions": actions,
        "rejected_operations": rejected_operations,
        "patch_summary": "Applied agent SkillOpt proposal." if changed else "Agent SkillOpt proposal made no allowed changes.",
        "finding_count": len(findings),
        "proposal_id": proposal.get("proposal_id"),
    }
