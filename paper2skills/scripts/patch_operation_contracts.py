"""Contract audit for bounded agent-driven review patch operations."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


OPERATION_CONTRACTS: dict[str, dict[str, Any]] = {
    "ensure_refusal_boundaries": {
        "artifact": "task_catalog",
        "required_fields": ["artifact", "task_type", "operation_id", "operation", "action", "finding_codes"],
        "optional_fields": ["proposal_id"],
        "purpose": "Add required refusal boundaries to a task_type record.",
    },
    "ensure_contract_grounding_notes": {
        "artifact": "task_catalog",
        "required_fields": ["artifact", "task_type", "operation_id", "operation", "action", "finding_codes"],
        "optional_fields": ["proposal_id"],
        "purpose": "Add grounding notes and minimum validation fallbacks to task contracts.",
    },
    "ensure_operational_recipe": {
        "artifact": "task_catalog",
        "required_fields": ["artifact", "task_type", "operation_id", "operation", "action", "finding_codes"],
        "optional_fields": ["proposal_id"],
        "purpose": "Create or repair agent-usable workflow steps, API sequence, outputs, and validation from existing task evidence.",
    },
    "downgrade_execution_verification_without_trace": {
        "artifact": "task_catalog",
        "required_fields": ["artifact", "task_type", "operation_id", "operation", "action", "finding_codes"],
        "optional_fields": ["proposal_id"],
        "purpose": "Remove execution_verified status when no successful trace is present.",
    },
    "rebuild_task_type_router": {
        "artifact": "task_type_router",
        "required_fields": ["artifact", "operation_id", "operation", "action", "finding_codes", "source_artifacts"],
        "optional_fields": ["proposal_id"],
        "purpose": "Rebuild task_type routes after task_catalog review patches.",
    },
}

OPERATION_FINDING_TERMS = {
    "ensure_refusal_boundaries": {"refusal", "refusal_boundaries"},
    "ensure_contract_grounding_notes": {"input_contract", "output_contract", "contracts", "validation_rules"},
    "ensure_operational_recipe": {"operational_recipe", "operational_recipes"},
    "downgrade_execution_verification_without_trace": {"verification", "verification_labels"},
    "rebuild_task_type_router": {"routing", "task_routing", "task_split", "task_partition"},
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
    operation: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        finding["iteration"] = iteration
    if operation:
        finding["operation"] = operation
    findings.append(finding)


def finding_code_set(iteration: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for finding in iteration.get("findings", []):
        code = finding.get("code") or finding.get("check")
        if code:
            codes.add(str(code))
    return codes


def finding_matches_task(finding: dict[str, Any], task_type: str | None) -> bool:
    if not task_type:
        return True
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


def compatible_codes(iteration: dict[str, Any], operation: str, task_type: str | None = None) -> set[str]:
    terms = OPERATION_FINDING_TERMS.get(operation, set())
    codes: set[str] = set()
    for finding in iteration.get("findings", []):
        code = str(finding.get("code") or finding.get("check") or "")
        text = " ".join(str(finding.get(key) or "") for key in ("code", "check", "message")).lower()
        if code and finding_matches_task(finding, task_type) and any(term in text for term in terms):
            codes.add(code)
    return codes


def action_identity(action: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(action.get("artifact") or ""),
        str(action.get("task_type") or ""),
        str(action.get("operation_id") or ""),
        str(action.get("operation") or ""),
        str(action.get("action") or ""),
    )


def audit_action(
    findings: list[dict[str, Any]],
    action: dict[str, Any],
    iteration: int,
    source: str,
    iteration_finding_codes: set[str],
    iteration_compatible_codes: set[str],
) -> dict[str, Any]:
    operation = str(action.get("operation") or "")
    contract = OPERATION_CONTRACTS.get(operation)
    record = {
        "iteration": iteration,
        "source": source,
        "artifact": action.get("artifact"),
        "task_type": action.get("task_type"),
        "operation_id": action.get("operation_id"),
        "operation": operation,
        "action": action.get("action"),
        "finding_codes": action.get("finding_codes", []),
    }

    if not operation:
        add_finding(findings, "error", "patch_operation_missing", "Patch action is missing a stable operation name.", iteration)
        return record
    if contract is None:
        add_finding(findings, "error", "patch_operation_unknown", "Patch action uses an undeclared operation.", iteration, operation)
        return record

    required_fields = set(contract["required_fields"])
    allowed_fields = required_fields.union(contract.get("optional_fields", []))
    missing_fields = sorted(field for field in required_fields if field not in action)
    extra_fields = sorted(field for field in action if field not in allowed_fields)
    if missing_fields:
        record["missing_fields"] = missing_fields
        add_finding(findings, "error", "patch_operation_missing_fields", "Patch operation is missing contract-required fields.", iteration, operation)
    if extra_fields:
        record["extra_fields"] = extra_fields
        add_finding(findings, "error", "patch_operation_extra_fields", "Patch operation includes fields outside its contract.", iteration, operation)
    if action.get("artifact") != contract["artifact"]:
        add_finding(findings, "error", "patch_operation_wrong_artifact", "Patch operation targets an artifact outside its contract.", iteration, operation)
    operation_id = action.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id.strip() or operation_id != operation_id.strip():
        add_finding(findings, "error", "patch_operation_invalid_operation_id", "Patch operation must preserve a stable non-empty operation_id.", iteration, operation)

    action_finding_codes = action.get("finding_codes")
    if not isinstance(action_finding_codes, list) or not action_finding_codes:
        add_finding(findings, "error", "patch_operation_missing_finding_codes", "Patch operation must cite review finding codes.", iteration, operation)
    else:
        unknown_codes = sorted(str(code) for code in action_finding_codes if str(code) not in iteration_finding_codes)
        if unknown_codes:
            record["unknown_finding_codes"] = unknown_codes
            add_finding(findings, "error", "patch_operation_unlinked_finding", "Patch operation cites finding codes absent from the same review iteration.", iteration, operation)
        if not iteration_compatible_codes:
            record["compatible_finding_codes"] = []
            add_finding(findings, "error", "patch_operation_missing_compatible_finding", "Patch operation has no compatible review finding in the same iteration.", iteration, operation)
        elif not {str(code) for code in action_finding_codes}.issubset(iteration_compatible_codes):
            record["compatible_finding_codes"] = sorted(iteration_compatible_codes)
            add_finding(findings, "error", "patch_operation_incompatible_finding", "Patch operation cites finding codes that do not match the operation family.", iteration, operation)

    if operation == "rebuild_task_type_router":
        source_artifacts = action.get("source_artifacts")
        if source_artifacts != ["task_catalog"]:
            add_finding(findings, "error", "router_rebuild_missing_source_artifact", "Router rebuild must declare task_catalog as its only source artifact.", iteration, operation)
    elif not action.get("task_type"):
        add_finding(findings, "error", "task_catalog_patch_missing_task_type", "Task catalog patch operation must name the target task_type.", iteration, operation)

    return record


def build_patch_operation_contracts(
    request: dict[str, Any],
    review_result: dict[str, Any],
    patch_application: dict[str, Any],
    patch_safety_audit: dict[str, Any],
) -> dict[str, Any]:
    """Audit patch action operation names, fields, and finding traceability."""
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    if patch_application.get("status") == "fail":
        add_finding(findings, "error", "patch_application_failed", "Patch operation contracts require a passing patch application audit.")
    if patch_safety_audit.get("status") == "fail":
        add_finding(findings, "error", "patch_safety_audit_failed", "Patch operation contracts require a passing patch safety audit.")

    for iteration in review_result.get("iterations", []):
        iteration_index = int(iteration.get("iteration") or 0)
        codes = finding_code_set(iteration)
        patch_plan = iteration.get("patch_plan") or {}
        patch = iteration.get("patch") or {}
        plan_actions = patch_plan.get("actions", [])
        applied_actions = patch.get("actions", [])
        plan_changed = bool(patch_plan.get("changed"))
        applied_changed = bool(patch.get("changed"))

        if plan_changed != applied_changed:
            add_finding(findings, "error", "patch_operation_changed_mismatch", "Patch plan and applied patch disagree on changed status.", iteration_index)
        if plan_changed and not plan_actions:
            add_finding(findings, "error", "changed_patch_plan_without_actions", "Changed patch plan must include at least one operation.", iteration_index)
        if applied_changed and not applied_actions:
            add_finding(findings, "error", "changed_patch_without_operations", "Changed applied patch must include at least one operation.", iteration_index)
        if not plan_changed and plan_actions:
            add_finding(findings, "error", "unchanged_patch_plan_has_actions", "Unchanged patch plan must not include operations.", iteration_index)
        if not applied_changed and applied_actions:
            add_finding(findings, "error", "unchanged_patch_has_operations", "Unchanged applied patch must not include operations.", iteration_index)

        planned = {action_identity(action) for action in plan_actions}
        applied = {action_identity(action) for action in applied_actions}
        if planned != applied:
            add_finding(findings, "error", "patch_operation_plan_apply_mismatch", "Patch plan and applied patch operation identities differ.", iteration_index)

        for action in plan_actions:
            operation = str(action.get("operation") or "")
            task_type = str(action.get("task_type") or "") if operation != "rebuild_task_type_router" else None
            records.append(audit_action(findings, action, iteration_index, "plan", codes, compatible_codes(iteration, operation, task_type)))
        for action in applied_actions:
            operation = str(action.get("operation") or "")
            task_type = str(action.get("task_type") or "") if operation != "rebuild_task_type_router" else None
            records.append(audit_action(findings, action, iteration_index, "applied", codes, compatible_codes(iteration, operation, task_type)))

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "patch_application_status": patch_application.get("status"),
        "patch_safety_status": patch_safety_audit.get("status"),
        "contract_count": len(OPERATION_CONTRACTS),
        "operation_contracts": OPERATION_CONTRACTS,
        "allowed_artifacts": sorted({contract["artifact"] for contract in OPERATION_CONTRACTS.values()}),
        "iteration_count": len(review_result.get("iterations", [])),
        "action_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Review patch operations must use declared operation names with stable required fields.",
            "Every operation must cite review finding codes from the same iteration.",
            "Patch planning and applied patch records must use identical operation identities.",
        ],
    }
