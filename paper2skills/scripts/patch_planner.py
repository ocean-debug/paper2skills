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


def apply_review_patches(
    task_catalog: dict[str, Any],
    router: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    patched_catalog = deepcopy(task_catalog)
    changed = False
    refusal_codes = finding_codes(findings, {"refusal", "unsupported", "missing_required_input"})
    contract_codes = finding_codes(findings, {"contract", "input", "output", "validation"})
    verification_codes = finding_codes(findings, {"verification", "verified", "trace", "execution"})
    actions: list[dict[str, Any]] = []
    for task in patched_catalog.get("tasks", []):
        task_type = task.get("task_type")
        if ensure_task_refusals(task):
            actions.append(
                {
                    "artifact": "task_catalog",
                    "task_type": task_type,
                    "operation": "ensure_refusal_boundaries",
                    "action": "add required refusal boundaries",
                    "finding_codes": refusal_codes,
                }
            )
            changed = True
        if ensure_contract_grounding_notes(task):
            actions.append(
                {
                    "artifact": "task_catalog",
                    "task_type": task_type,
                    "operation": "ensure_contract_grounding_notes",
                    "action": "add contract grounding notes and minimum validation fallback",
                    "finding_codes": contract_codes,
                }
            )
            changed = True
        if enforce_verification_boundaries(task):
            actions.append(
                {
                    "artifact": "task_catalog",
                    "task_type": task_type,
                    "operation": "downgrade_execution_verification_without_trace",
                    "action": "downgrade execution verification without execution evidence",
                    "finding_codes": verification_codes,
                }
            )
            changed = True
    patched_router = build_router(patched_catalog) if changed else router
    if changed:
        router_codes = sorted(
            {
                code
                for action in actions
                for code in action.get("finding_codes", [])
            }
        )
        actions.append(
            {
                "artifact": "task_type_router",
                "operation": "rebuild_task_type_router",
                "action": "rebuild routes from reviewed task catalog",
                "finding_codes": router_codes,
                "source_artifacts": ["task_catalog"],
            }
        )
    return {
        "changed": changed,
        "task_catalog": patched_catalog,
        "router": patched_router,
        "actions": actions,
        "patch_summary": "Applied deterministic review patches." if changed else "No deterministic patch available.",
        "finding_count": len(findings),
    }
