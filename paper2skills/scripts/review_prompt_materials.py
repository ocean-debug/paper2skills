"""Static prompt materials for the review-loop roles."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PROMPT_MATERIALS: list[dict[str, Any]] = [
    {
        "prompt_id": "draft_snapshot_prompt",
        "role": "draft_snapshot",
        "purpose": "Summarize current task_type and router shape before critique.",
        "allowed_inputs": ["task_catalog.yaml", "task_type_router.yaml"],
        "required_outputs": ["role", "task_types", "route_count"],
        "forbidden_outputs": ["execution claims", "file edits", "new task_type names without evidence"],
        "template": "Read task_catalog and task_type_router. Return task_types and route_count only.",
    },
    {
        "prompt_id": "critic_prompt",
        "role": "critic",
        "purpose": "Critique grounding, task split, contracts, refusals, validation, and verification labels.",
        "allowed_inputs": [
            "request_audit.yaml",
            "discovery_report.yaml",
            "source_grounding.yaml",
            "evidence_cards.yaml",
            "task_catalog.yaml",
            "task_type_router.yaml",
            "api_grounding.yaml",
            "interface_grounding.yaml",
            "environment_spec.yaml",
            "tutorial_catalog.yaml",
            "parameter_catalog.yaml",
        ],
        "required_outputs": ["role", "score", "total", "score_ratio", "severity_counts", "focus_counts", "item_results", "blocking_findings"],
        "forbidden_outputs": ["patch actions", "execution_verified without trace_ref", "claims without evidence_refs"],
        "template": "Score each rubric item from supplied artifacts. Emit findings with severity, check, task_type, and message.",
    },
    {
        "prompt_id": "patch_plan_prompt",
        "role": "patch_plan",
        "purpose": "Plan deterministic in-memory repairs for fixable review findings.",
        "allowed_inputs": ["review_iteration.findings", "task_catalog.yaml", "task_type_router.yaml"],
        "required_outputs": ["role", "changed", "actions", "summary"],
        "forbidden_outputs": ["shell commands", "network access", "dependency installation", "filesystem paths"],
        "template": "Map fixable finding codes to allowed in-memory operations. Do not propose commands or file mutations.",
    },
    {
        "prompt_id": "revision_prompt",
        "role": "revision",
        "purpose": "Record deterministic in-memory changes applied by the patch planner.",
        "allowed_inputs": ["patch_plan", "patched task_catalog", "patched task_type_router"],
        "required_outputs": ["role", "changed", "changed_artifacts", "summary"],
        "forbidden_outputs": ["unplanned edits", "hidden unresolved findings", "runtime claims"],
        "template": "Summarize applied in-memory changes and changed artifacts from the patch plan.",
    },
    {
        "prompt_id": "gate_prompt",
        "role": "gate",
        "purpose": "Close the iteration with pass, patch-for-next-iteration, or no-patch stop reason.",
        "allowed_inputs": ["critic state", "patch_plan", "revision state", "review rubric threshold"],
        "required_outputs": ["role", "passed", "reason"],
        "forbidden_outputs": ["override critic errors", "ignore failed patch audits", "mark untraced execution as verified"],
        "template": "Return passed and reason from critic result, patch availability, and configured score gate.",
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    role: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if role:
        item["role"] = role
    findings.append(item)


def material_by_role() -> dict[str, dict[str, Any]]:
    return {str(material["role"]): material for material in PROMPT_MATERIALS}


def build_review_prompt_materials(
    request: dict[str, Any],
    review_prompt_contracts: dict[str, Any],
) -> dict[str, Any]:
    """Build and audit static prompt materials for review-loop roles."""
    findings: list[dict[str, Any]] = []
    contract_roles = {str(contract.get("role")) for contract in review_prompt_contracts.get("contracts", []) if contract.get("role")}
    material_roles = set(material_by_role())

    if review_prompt_contracts.get("status") != "pass":
        add_finding(findings, "error", "review_prompt_contracts_failed", "Prompt materials require passing review prompt contracts.")

    for role in sorted(contract_roles.difference(material_roles)):
        add_finding(findings, "error", "missing_prompt_material", "A review role lacks prompt material.", role)
    for role in sorted(material_roles.difference(contract_roles)):
        add_finding(findings, "error", "prompt_material_without_contract", "Prompt material has no matching review role contract.", role)

    contract_required = {
        str(contract.get("role")): set(contract.get("required_fields", []))
        for contract in review_prompt_contracts.get("contracts", [])
        if contract.get("role")
    }
    for material in PROMPT_MATERIALS:
        role = str(material.get("role"))
        missing_outputs = sorted(contract_required.get(role, set()).difference(material.get("required_outputs", [])))
        if missing_outputs:
            add_finding(
                findings,
                "error",
                "prompt_material_missing_contract_outputs",
                "Prompt material required_outputs must cover the matching role contract fields.",
                role,
            )
        for field in ["prompt_id", "purpose", "allowed_inputs", "required_outputs", "forbidden_outputs", "template"]:
            if not material.get(field):
                add_finding(
                    findings,
                    "error",
                    "prompt_material_missing_field",
                    "Prompt material is missing a required static field.",
                    role,
                )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_prompt_contracts_status": review_prompt_contracts.get("status"),
        "material_count": len(PROMPT_MATERIALS),
        "contract_role_count": len(contract_roles),
        "materials": PROMPT_MATERIALS,
        "findings": findings,
        "policy": [
            "Prompt materials are static run artifacts; they do not call a model or execute package code.",
            "Each review role with a state contract must have matching prompt material.",
            "Prompt material must declare allowed inputs, required outputs, and forbidden outputs before review duties are audited.",
        ],
    }
