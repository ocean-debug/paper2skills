"""Prompt/state contracts for the SkillOpt-style review loop."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


CONTRACTS: list[dict[str, Any]] = [
    {
        "role": "draft_snapshot",
        "purpose": "Capture the current task catalog and router shape before critique.",
        "required_fields": ["role", "task_types", "route_count"],
        "allowed_actions": ["read current in-memory artifacts"],
        "forbidden_actions": ["execute package code", "modify files", "claim verification"],
    },
    {
        "role": "critic",
        "purpose": "Score evidence, contracts, routing, refusals, validation, and verification boundaries.",
        "required_fields": ["role", "score", "total", "score_ratio", "severity_counts", "focus_counts", "item_results", "blocking_findings"],
        "allowed_actions": ["read review artifacts", "emit findings", "emit rubric item results"],
        "forbidden_actions": ["patch artifacts", "run tutorials", "downgrade refusal requirements"],
    },
    {
        "role": "patch_plan",
        "purpose": "Describe bounded agent-authored edit proposals for fixable findings.",
        "required_fields": ["role", "changed", "actions", "summary"],
        "allowed_actions": ["plan task_catalog edits", "plan task_type_router rebuilds", "request Codex-authored proposal"],
        "forbidden_actions": ["shell commands", "filesystem mutations", "network access", "dependency installation"],
    },
    {
        "role": "revision",
        "purpose": "Record the in-memory artifact changes applied from an accepted agent proposal.",
        "required_fields": ["role", "changed", "changed_artifacts", "summary"],
        "allowed_actions": ["record applied in-memory changes"],
        "forbidden_actions": ["edit generated child files directly", "hide unresolved findings"],
    },
    {
        "role": "gate",
        "purpose": "Close an iteration with a pass, patch-for-next-iteration, or no-patch stop reason.",
        "required_fields": ["role", "passed", "reason"],
        "allowed_actions": ["record stop reason", "record iteration pass/fail"],
        "forbidden_actions": ["override failed critic state", "mark execution_verified without trace_ref"],
    },
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
    role: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        item["iteration"] = iteration
    if role:
        item["role"] = role
    findings.append(item)


def contract_by_role() -> dict[str, dict[str, Any]]:
    return {contract["role"]: contract for contract in CONTRACTS}


def states_by_role(iteration: dict[str, Any]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for state in iteration.get("states", []):
        role = state.get("role")
        if role:
            states[str(role)] = state
    return states


def build_review_prompt_contracts(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    required_roles = set(contract_by_role())
    required_every_iteration = {"draft_snapshot", "critic", "patch_plan", "gate"}

    for iteration in review_result.get("iterations", []):
        iteration_index = int(iteration.get("iteration") or 0)
        states = states_by_role(iteration)
        missing_roles = sorted(required_every_iteration.difference(states))
        for role in missing_roles:
            add_finding(
                findings,
                "error",
                "missing_review_contract_role",
                "Review iteration is missing a required contract role.",
                iteration_index,
                role,
            )
        unknown_roles = sorted(set(states).difference(required_roles))
        for role in unknown_roles:
            add_finding(
                findings,
                "error",
                "unknown_review_contract_role",
                "Review iteration contains a state role without a declared contract.",
                iteration_index,
                role,
            )
        for role, contract in contract_by_role().items():
            state = states.get(role)
            if not state:
                continue
            missing_fields = sorted(field for field in contract["required_fields"] if field not in state)
            if missing_fields:
                add_finding(
                    findings,
                    "error",
                    "review_state_missing_contract_field",
                    "Review state is missing one or more contract-required fields.",
                    iteration_index,
                    role,
                )
        if (iteration.get("patch") or {}).get("changed") and "revision" not in states:
            add_finding(
                findings,
                "error",
                "changed_patch_without_revision_state",
                "Changed review patches must record a revision state.",
                iteration_index,
                "revision",
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "contract_count": len(CONTRACTS),
        "required_every_iteration": sorted(required_every_iteration),
        "contracts": CONTRACTS,
        "iteration_count": len(review_result.get("iterations", [])),
        "findings": findings,
        "policy": [
            "Review prompt contracts define allowed state roles and required fields for each self-review iteration.",
            "The contract layer is static and non-executing; it audits the review loop shape before publish.",
            "Patch planning must be agent-authored, bounded to declared operations, and applied only through audited in-memory artifacts.",
        ],
    }
