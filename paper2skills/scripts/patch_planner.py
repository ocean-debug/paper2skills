"""Deterministic artifact patching for the review loop."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from task_router import build_router


OPERATION_FINDING_TERMS = {
    "ensure_refusal_boundaries": {"refusal", "refusal_boundaries"},
    "ensure_contract_grounding_notes": {"input_contract", "output_contract", "contracts", "validation_rules"},
    "ensure_operational_recipe": {"operational_recipe", "operational_recipes"},
    "downgrade_execution_verification_without_trace": {"verification", "verification_labels"},
    "rebuild_task_type_router": {"routing", "task_routing", "task_split", "task_partition"},
}
ALLOWED_AGENT_REVIEW_OPERATIONS = set(OPERATION_FINDING_TERMS)


def finding_code_set(findings: list[dict[str, Any]]) -> set[str]:
    return {str(finding.get("code") or finding.get("check")) for finding in findings if finding.get("code") or finding.get("check")}


def compatible_finding_codes(findings: list[dict[str, Any]], operation: str) -> set[str]:
    terms = OPERATION_FINDING_TERMS.get(operation, set())
    codes: set[str] = set()
    for finding in findings:
        code = str(finding.get("code") or finding.get("check") or "")
        text = " ".join(str(finding.get(key) or "") for key in ("code", "check", "message")).lower()
        if code and any(term in text for term in terms):
            codes.add(code)
    return codes


def finding_matches_task(finding: dict[str, Any], task_type: str) -> bool:
    task_scopes: list[str] = []
    raw_task_type = finding.get("task_type")
    if raw_task_type:
        task_scopes.append(str(raw_task_type))
    raw_task_types = finding.get("task_types")
    if isinstance(raw_task_types, list):
        task_scopes.extend(str(item) for item in raw_task_types if str(item))
    elif raw_task_types:
        task_scopes.append(str(raw_task_types))
    if not task_scopes:
        return True
    return "*" in task_scopes or task_type in task_scopes


def compatible_task_finding_codes(findings: list[dict[str, Any]], operation: str, task_type: str) -> set[str]:
    terms = OPERATION_FINDING_TERMS.get(operation, set())
    codes: set[str] = set()
    for finding in findings:
        code = str(finding.get("code") or finding.get("check") or "")
        text = " ".join(str(finding.get(key) or "") for key in ("code", "check", "message")).lower()
        if code and finding_matches_task(finding, task_type) and any(term in text for term in terms):
            codes.add(code)
    return codes


def operation_finding_codes(
    operation: dict[str, Any],
    op_name: str,
    findings: list[dict[str, Any]],
) -> tuple[list[str], str | None]:
    requested = operation.get("finding_codes")
    if not isinstance(requested, list) or not requested:
        return [], "operation_missing_finding_codes"
    requested_codes = [str(code) for code in requested if str(code)]
    known_codes = finding_code_set(findings)
    unknown = sorted(code for code in requested_codes if code not in known_codes)
    if unknown:
        return requested_codes, "operation_finding_code_not_in_iteration"
    compatible = compatible_finding_codes(findings, op_name)
    if not compatible:
        return requested_codes, "operation_missing_compatible_finding"
    if not set(requested_codes).issubset(compatible):
        return requested_codes, "operation_finding_code_incompatible"
    return requested_codes, None


def operation_task_grounding_error(
    codes: list[str],
    operation: str,
    findings: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> str | None:
    requested = set(codes)
    for task in tasks:
        task_type = str(task.get("task_type") or "")
        compatible = compatible_task_finding_codes(findings, operation, task_type)
        if not requested.issubset(compatible):
            return "operation_finding_code_task_mismatch"
    return None


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


def ensure_operational_recipe(task: dict[str, Any]) -> bool:
    recipe = task.setdefault("operational_recipe", {})
    changed = False
    input_contract = task.get("input_contract") or {}
    output_contract = task.get("output_contract") or {}
    if not recipe.get("required_inputs"):
        recipe["required_inputs"] = list(input_contract.get("required_from_user", []))
        changed = True
    if not recipe.get("expected_outputs"):
        recipe["expected_outputs"] = list(output_contract.get("expected_outputs", []))
        changed = True
    if not recipe.get("validation_checks"):
        recipe["validation_checks"] = list(output_contract.get("minimum_validation", []))
        changed = True
    if not recipe.get("api_sequence"):
        api_sequence = []
        for item in output_contract.get("interface_observed", [])[:8]:
            signature = item.get("signature")
            if signature:
                api_sequence.append(f"source-observed interface: `{signature}`")
        recipe["api_sequence"] = api_sequence
        changed = changed or bool(api_sequence)
    if not recipe.get("workflow_steps"):
        steps = [
            "Confirm task_type, input path/object, metadata roles, and environment approval before execution.",
            "Use the source-grounded API sequence; stop if no primary API is present.",
            "Write or return expected outputs and a machine-readable run summary.",
            "Run minimum validation checks before reporting success.",
        ]
        recipe["workflow_steps"] = steps
        changed = True
    if not recipe.get("status"):
        recipe["status"] = "ready" if recipe.get("api_sequence") else "needs_agent_review"
        changed = True
    if not recipe.get("confidence"):
        recipe["confidence"] = "agent_review_patch_from_existing_contracts"
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


def router_semantics(router: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in router.items() if key != "created_at"}


def apply_agent_review_proposal(
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    proposal: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a bounded agent-authored review-loop edit proposal."""
    patched_catalog = deepcopy(task_catalog)
    changed = False
    actions: list[dict[str, Any]] = []
    rejected_operations: list[dict[str, Any]] = []
    allowed_operations = ALLOWED_AGENT_REVIEW_OPERATIONS
    operations = proposal.get("operations", [])
    requested_router_rebuild = False
    router_operation_id = ""
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
        operation_id = str(operation.get("operation_id") or "").strip()
        task_type = operation.get("task_type")
        if op_name not in allowed_operations:
            rejected_operations.append(
                {
                    "operation_id": operation_id,
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": "unsupported_agent_review_operation",
                }
            )
            continue
        codes, code_error = operation_finding_codes(operation, op_name, findings)
        if code_error:
            rejected_operations.append(
                {
                    "operation_id": operation_id,
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": code_error,
                    "finding_codes": codes,
                }
            )
            continue
        if op_name == "rebuild_task_type_router":
            if requested_router_rebuild:
                rejected_operations.append(
                    {
                        "operation_id": operation_id,
                        "operation": op_name,
                        "task_type": task_type,
                        "reason": "duplicate_router_rebuild_operation",
                        "finding_codes": codes,
                    }
                )
                continue
            requested_router_rebuild = True
            router_operation_id = router_operation_id or operation_id
            continue
        matched_tasks = [task for task in patched_catalog.get("tasks", []) if task_matches(task, task_type)]
        if not matched_tasks:
            rejected_operations.append(
                {
                    "operation_id": operation_id,
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": "task_type_not_found",
                }
            )
            continue
        task_grounding_error = operation_task_grounding_error(codes, op_name, findings, matched_tasks)
        if task_grounding_error:
            rejected_operations.append(
                {
                    "operation_id": operation_id,
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": task_grounding_error,
                    "finding_codes": codes,
                }
            )
            continue
        operation_changed = False
        for task in matched_tasks:
            task_changed = False
            if op_name == "ensure_refusal_boundaries":
                task_changed = ensure_task_refusals(task)
            elif op_name == "ensure_contract_grounding_notes":
                task_changed = ensure_contract_grounding_notes(task)
            elif op_name == "ensure_operational_recipe":
                task_changed = ensure_operational_recipe(task)
            elif op_name == "downgrade_execution_verification_without_trace":
                task_changed = enforce_verification_boundaries(task)
            if task_changed:
                actions.append(
                    {
                        "artifact": "task_catalog",
                        "task_type": task.get("task_type"),
                        "operation_id": operation_id,
                        "operation": op_name,
                        "action": operation.get("rationale") or f"apply agent proposal operation {op_name}",
                        "proposal_id": proposal.get("proposal_id"),
                        "finding_codes": codes,
                    }
                )
                changed = True
                operation_changed = True
        if not operation_changed:
            rejected_operations.append(
                {
                    "operation_id": operation_id,
                    "operation": op_name,
                    "task_type": task_type,
                    "reason": "selected_operation_no_effect",
                    "finding_codes": codes,
                }
            )

    patched_router = build_router(patched_catalog) if changed or requested_router_rebuild else router
    router_changed = router_semantics(patched_router) != router_semantics(router)
    if requested_router_rebuild and router_changed:
        changed = True
    if requested_router_rebuild and not router_changed:
        rejected_operations.append(
            {
                "operation_id": router_operation_id,
                "operation": "rebuild_task_type_router",
                "task_type": "*",
                "reason": "router_already_matches_task_catalog",
            }
        )
    if router_changed:
        router_codes = []
        for operation in operations:
            if isinstance(operation, dict) and operation.get("operation") == "rebuild_task_type_router":
                router_codes = [str(code) for code in operation.get("finding_codes", []) if str(code)]
                break
        derived_from_task_patch = False
        if not router_codes:
            router_codes = sorted({code for action in actions for code in action.get("finding_codes", [])})
            derived_from_task_patch = True
        changed = True
        if not derived_from_task_patch:
            actions.append(
                {
                    "artifact": "task_type_router",
                    "operation_id": router_operation_id,
                    "operation": "rebuild_task_type_router",
                    "action": "rebuild routes from agent-reviewed task catalog",
                    "proposal_id": proposal.get("proposal_id"),
                    "source_artifacts": ["task_catalog"],
                    "finding_codes": router_codes,
                }
            )
    return {
        "changed": changed,
        "task_catalog": patched_catalog,
        "router": patched_router,
        "actions": actions,
        "rejected_operations": rejected_operations,
        "patch_summary": "Applied agent review-loop proposal." if changed else "Agent review-loop proposal made no allowed changes.",
        "finding_count": len(findings),
        "proposal_id": proposal.get("proposal_id"),
    }
