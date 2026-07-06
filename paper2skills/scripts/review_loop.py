"""Agent-driven paper2skills review and patch loop."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from common import now_utc
from patch_planner import ALLOWED_AGENT_REVIEW_OPERATIONS, apply_agent_review_proposal
from review_rubric import score_artifacts
from self_review import self_review


REVIEW_LOOP_ROLES = [
    "analyst_error",
    "analyst_success",
    "merge_failure",
    "merge_success",
    "merge_final",
    "ranking",
    "slow_update",
]

REQUIRED_PROPOSAL_ROLES = [
    "analyst_error",
    "analyst_success",
    "merge_failure",
    "merge_success",
    "merge_final",
    "ranking",
    "slow_update",
]

RANKING_SELECTION_FIELDS = {"operation_ids", "selected_operations", "ranked_operations", "chosen_operations", "operation_indices"}
REQUIRED_TOP_LEVEL_PROPOSAL_FIELDS = {"iteration", "proposal_id", "rationale", "expected_improvement"}
ROLE_CONTENT_FIELDS = {
    "analyst_error": {"analysis", "error_analysis", "failure_patterns", "proposed_fixes", "findings"},
    "analyst_success": {"analysis", "success_patterns", "preserve", "preserved_behaviors", "findings"},
    "merge_failure": {"operations", "candidate_operations", "merged_operations", "edits"},
    "merge_success": {"operations", "candidate_operations", "preserved_constraints", "edits"},
    "merge_final": {"operations", "final_operations", "merged_operations", "selected_operations"},
    "ranking": RANKING_SELECTION_FIELDS,
    "slow_update": {"summary", "guidance", "lessons", "next_state", "longitudinal_update"},
}
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def operation_identity(operation: dict[str, Any]) -> str:
    value = operation.get("operation_id")
    if not isinstance(value, str):
        return ""
    return value.strip()


def operation_id_error(operation: dict[str, Any]) -> str | None:
    value = operation.get("operation_id")
    if not isinstance(value, str):
        return "operation_id_must_be_string"
    identity = value.strip()
    if value != identity:
        return "operation_id_not_canonical"
    if not identity:
        return "operation_id_empty"
    if not OPERATION_ID_RE.fullmatch(identity):
        return "operation_id_unsafe"
    return None


def merge_final_items(proposal: dict[str, Any]) -> list[Any]:
    merge_final = proposal.get("merge_final") if isinstance(proposal.get("merge_final"), dict) else {}
    items = (
        merge_final.get("operations")
        or merge_final.get("final_operations")
        or merge_final.get("merged_operations")
        or merge_final.get("selected_operations")
    )
    return items if isinstance(items, list) else []


def item_identity(item: Any) -> str:
    if isinstance(item, dict):
        return operation_identity(item)
    return str(item or "")


def selected_identities(selected: list[Any]) -> tuple[list[str], bool]:
    identities = []
    missing_identity = False
    for item in selected:
        identity = item_identity(item)
        if not identity:
            missing_identity = True
        identities.append(identity)
    return identities, missing_identity


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def focus_area(check: str) -> str:
    if check in {"source_grounding", "sources", "evidence", "evidence_refs", "api_grounding", "interface_grounding"}:
        return "evidence"
    if check in {"task_partition", "task_split", "task_routing", "routing"}:
        return "task_split_and_routing"
    if check in {"input_contracts", "output_contracts", "input_contract", "output_contract", "parameter_constraints", "operational_recipe", "operational_recipes"}:
        return "contracts"
    if check in {"refusal_boundaries", "refusal", "backend"}:
        return "refusal_boundaries"
    if check in {"validation_rules", "validation", "verification", "verification_labels"}:
        return "validation_and_verification"
    if check in {"environment_contract", "tutorial_catalog"}:
        return "supporting_context"
    return "other"


def critic_state(findings: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    focus_counts: dict[str, int] = {}
    for finding in findings:
        area = focus_area(str(finding.get("check") or finding.get("code") or "other"))
        focus_counts[area] = focus_counts.get(area, 0) + 1
    return {
        "role": "critic",
        "score": rubric["score"],
        "total": rubric["total"],
        "score_ratio": rubric["score_ratio"],
        "severity_counts": severity_counts(findings),
        "focus_counts": dict(sorted(focus_counts.items())),
        "item_results": rubric.get("item_results", []),
        "blocking_findings": [
            finding for finding in findings if finding.get("severity") == "error"
        ],
    }


def draft_snapshot(task_catalog: dict[str, Any], router: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "draft_snapshot",
        "task_types": [task.get("task_type") for task in task_catalog.get("tasks", [])],
        "route_count": len(router.get("routes", [])),
    }


def record_score_state(
    rubric: dict[str, Any],
    candidate_hash: str,
    iteration: int,
    stage: str = "pre_apply",
) -> dict[str, Any]:
    return {
        "role": "record_score",
        "stage": stage,
        "iteration": iteration,
        "candidate_hash": candidate_hash,
        "score": rubric.get("score"),
        "total": rubric.get("total"),
        "score_ratio": rubric.get("score_ratio"),
        "score_source": "static_rubric_selection_score",
        "strict_gate": "candidate score must be strictly greater than the previous accepted score",
    }


def rollout_plan_state(request: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "rollout_plan",
        "plan_only": True,
        "target_agent": request.get("target_agent"),
        "task_types": [task.get("task_type") for task in task_catalog.get("tasks", [])],
        "external_result_fields": ["agent_rollout_results", "eval_results", "e2e_acceptance_results"],
        "supplied_agent_rollout_result_count": len(request.get("agent_rollout_results", []) or []),
        "supplied_eval_result_count": len(request.get("eval_results", []) or []),
        "policy": "Python records the rollout contract; the agent supplies observed rollout/eval JSON outside this loop.",
    }


def revision_state(patch: dict[str, Any]) -> dict[str, Any]:
    changed_artifacts = sorted({action.get("artifact") for action in patch.get("actions", []) if action.get("artifact")})
    return {
        "role": "revision",
        "changed": patch["changed"],
        "changed_artifacts": changed_artifacts,
        "summary": patch["patch_summary"],
    }


def proposal_stage_state(role: str, proposal: dict[str, Any] | None) -> dict[str, Any]:
    payload = proposal.get(role) if isinstance(proposal, dict) else None
    if isinstance(payload, dict):
        status = "recorded"
        output_keys = sorted(payload)
    else:
        status = "awaiting_agent_json"
        output_keys = []
    return {
        "role": role,
        "status": status,
        "prompt_contract": f"{role}.md",
        "recorded_output_keys": output_keys,
        "required_agent_output": True,
    }


def review_loop_stage_states(proposal: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [proposal_stage_state(role, proposal) for role in REVIEW_LOOP_ROLES]


def missing_proposal_roles(proposal: dict[str, Any]) -> list[str]:
    return [role for role in REQUIRED_PROPOSAL_ROLES if not isinstance(proposal.get(role), dict)]


def proposal_validation_errors(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    operations = proposal.get("operations")
    operation_ids: list[str] = []
    missing_top_level = sorted(field for field in REQUIRED_TOP_LEVEL_PROPOSAL_FIELDS if not proposal.get(field))
    if missing_top_level:
        errors.append(
            {
                "code": "proposal_missing_top_level_fields",
                "fields": missing_top_level,
                "message": "Proposal is missing required top-level review-loop fields.",
            }
        )
    if not isinstance(operations, list) or not operations:
        errors.append({"code": "proposal_operations_missing", "message": "Proposal must include at least one bounded operation."})
    else:
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                errors.append({"code": "proposal_operation_not_mapping", "operation_index": index, "message": "Each proposal operation must be a mapping."})
                continue
            id_error = operation_id_error(operation)
            if id_error:
                errors.append(
                    {
                        "code": id_error,
                        "operation_index": index,
                        "message": "Each proposal operation must include a non-empty safe string operation_id.",
                    }
                )
            identity = operation_identity(operation)
            if not identity:
                errors.append({"code": "proposal_operation_missing_id", "operation_index": index, "message": "Each proposal operation must include a stable operation_id."})
            op_name = str(operation.get("operation") or "")
            if op_name not in ALLOWED_AGENT_REVIEW_OPERATIONS:
                errors.append(
                    {
                        "code": "proposal_operation_unsupported",
                        "operation_index": index,
                        "operation": op_name,
                        "allowed_operations": sorted(ALLOWED_AGENT_REVIEW_OPERATIONS),
                        "message": "Each selected proposal operation must use a declared bounded operation.",
                    }
                )
            finding_codes = operation.get("finding_codes")
            if not isinstance(finding_codes, list) or not any(str(code).strip() for code in finding_codes):
                errors.append(
                    {
                        "code": "proposal_operation_missing_finding_codes",
                        "operation_index": index,
                        "message": "Each proposal operation must include a non-empty finding_codes list.",
                    }
                )
            operation_ids.append(identity)
        duplicate_ids = sorted({identity for identity in operation_ids if identity and operation_ids.count(identity) > 1})
        if duplicate_ids:
            errors.append(
                {
                    "code": "proposal_operation_duplicate_ids",
                    "operation_ids": duplicate_ids,
                    "message": "Proposal operation_id values must be unique.",
                }
            )
    for role in REQUIRED_PROPOSAL_ROLES:
        payload = proposal.get(role)
        if not isinstance(payload, dict):
            errors.append({"code": "missing_required_review_loop_role", "role": role, "message": "Required paper2skills review loop role is missing."})
            continue
        if not payload:
            errors.append({"code": "empty_required_review_loop_role", "role": role, "message": "Required paper2skills review loop role payload must not be empty."})
            continue
        expected_fields = ROLE_CONTENT_FIELDS.get(role, set())
        if expected_fields and not expected_fields.intersection(payload):
            errors.append(
                {
                    "code": "role_payload_missing_content_field",
                    "role": role,
                    "expected_any_of": sorted(expected_fields),
                    "message": "Required paper2skills review loop role payload lacks role-specific content fields.",
                }
            )
    ranking = proposal.get("ranking")
    if isinstance(ranking, dict) and not any(field in ranking for field in RANKING_SELECTION_FIELDS):
        errors.append(
            {
                "code": "ranking_selection_missing",
                "role": "ranking",
                "message": "Ranking payload must identify selected or ranked operations before apply.",
            }
        )
    elif isinstance(ranking, dict) and operation_ids:
        selector_fields = [field for field in ("operation_ids", "selected_operations", "ranked_operations", "chosen_operations", "operation_indices") if field in ranking]
        if len(selector_fields) > 1:
            errors.append(
                {
                    "code": "ranking_mixed_selector_fields",
                    "role": "ranking",
                    "fields": selector_fields,
                    "message": "Ranking must use exactly one selector field so validation and apply use the same operation set.",
                }
            )
        selected_field = next((field for field in ("operation_ids", "selected_operations", "ranked_operations", "chosen_operations") if field in ranking), None)
        selected = ranking.get(selected_field) if selected_field else None
        indices = ranking.get("operation_indices")
        final_items = merge_final_items(proposal)
        final_ids, final_missing_ids = selected_identities(final_items)
        if not final_items:
            errors.append(
                {
                    "code": "merge_final_operations_missing",
                    "role": "merge_final",
                    "message": "merge_final must expose a non-empty final operation pool.",
                }
            )
        if final_missing_ids:
            errors.append(
                {
                    "code": "merge_final_operation_missing_id",
                    "role": "merge_final",
                    "message": "Every merge_final operation entry must identify an operation_id.",
                }
            )
        duplicate_final_ids = sorted({identity for identity in final_ids if identity and final_ids.count(identity) > 1})
        if duplicate_final_ids:
            errors.append(
                {
                    "code": "merge_final_operation_duplicate_ids",
                    "role": "merge_final",
                    "operation_ids": duplicate_final_ids,
                    "message": "merge_final operation_id values must be unique.",
                }
            )
        unknown_final = sorted(identity for identity in final_ids if identity and identity not in operation_ids)
        if unknown_final:
            errors.append(
                {
                    "code": "merge_final_references_unknown_operation_id",
                    "role": "merge_final",
                    "operation_ids": unknown_final,
                    "message": "merge_final must reference the same stable operation_id values declared in proposal.operations.",
                }
            )
        if isinstance(selected, list) and selected:
            selected_ids, missing_ids = selected_identities(selected)
            duplicate_selected_ids = sorted({identity for identity in selected_ids if identity and selected_ids.count(identity) > 1})
            if duplicate_selected_ids:
                errors.append(
                    {
                        "code": "ranking_selects_duplicate_operation_ids",
                        "role": "ranking",
                        "operation_ids": duplicate_selected_ids,
                        "message": "Ranking must not select the same operation_id more than once.",
                    }
                )
            if missing_ids:
                errors.append(
                    {
                        "code": "ranking_selected_operation_missing_id",
                        "role": "ranking",
                        "message": "Ranking selected operation objects must identify operations by operation_id.",
                    }
                )
            unknown = sorted(identity for identity in selected_ids if identity and identity not in operation_ids)
            if unknown:
                errors.append(
                    {
                        "code": "ranking_references_unknown_operation_id",
                        "role": "ranking",
                        "operation_ids": unknown,
                        "message": "Ranking selected operation_id values that are not present in proposal.operations.",
                    }
                )
            outside_final = sorted(identity for identity in selected_ids if identity and identity not in final_ids)
            if outside_final:
                errors.append(
                    {
                        "code": "ranking_selects_operation_outside_merge_final",
                        "role": "ranking",
                        "operation_ids": outside_final,
                        "message": "Ranking may select only operations present in merge_final's final operation pool.",
                    }
                )
        elif isinstance(selected, list):
            errors.append(
                {
                    "code": "ranking_selects_no_operations",
                    "role": "ranking",
                    "message": "Ranking selection field is present but empty.",
                }
            )
        elif selected_field is not None:
            errors.append(
                {
                    "code": "ranking_selection_must_be_list",
                    "role": "ranking",
                    "field": selected_field,
                    "message": "Ranking selected operation fields must be non-empty lists.",
                }
            )
        elif isinstance(indices, list) and indices:
            duplicate_indices = sorted({index for index in indices if type(index) is int and indices.count(index) > 1})
            if duplicate_indices:
                errors.append(
                    {
                        "code": "ranking_selects_duplicate_operation_indices",
                        "role": "ranking",
                        "operation_indices": duplicate_indices,
                        "message": "Ranking must not select the same operation index more than once.",
                    }
                )
            bad_indices = [index for index in indices if type(index) is not int or index < 0 or index >= len(final_ids)]
            if bad_indices:
                errors.append(
                    {
                        "code": "ranking_references_bad_operation_index",
                        "role": "ranking",
                        "operation_indices": bad_indices,
                        "message": "Ranking operation_indices must reference merge_final's final operation pool by zero-based index.",
                    }
                )
        elif isinstance(indices, list):
            errors.append(
                {
                    "code": "ranking_selects_no_operations",
                    "role": "ranking",
                    "message": "Ranking operation_indices field is present but empty.",
                }
            )
        elif "operation_indices" in ranking:
            errors.append(
                {
                    "code": "ranking_operation_indices_must_be_list",
                    "role": "ranking",
                    "message": "Ranking operation_indices must be a non-empty list of zero-based integers.",
                }
            )
    return errors


def selected_operations_from_ranking(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    operations = [operation for operation in proposal.get("operations", []) if isinstance(operation, dict)]
    by_id = {operation_identity(operation): operation for operation in operations if operation_identity(operation)}
    final_pool = [by_id[identity] for identity in [item_identity(item) for item in merge_final_items(proposal)] if identity in by_id]
    final_by_id = {operation_identity(operation): operation for operation in final_pool if operation_identity(operation)}
    ranking = proposal.get("ranking") if isinstance(proposal.get("ranking"), dict) else {}
    indices = ranking.get("operation_indices")
    if isinstance(indices, list) and indices:
        return [final_pool[index] for index in indices if type(index) is int and 0 <= index < len(final_pool)]
    selected = ranking.get("operation_ids") or ranking.get("selected_operations") or ranking.get("ranked_operations") or ranking.get("chosen_operations")
    if isinstance(selected, list) and selected:
        selected_operations: list[dict[str, Any]] = []
        for item in selected:
            if isinstance(item, dict):
                identity = operation_identity(item)
            else:
                identity = str(item)
            operation = final_by_id.get(identity)
            if operation:
                selected_operations.append(operation)
        seen: set[int] = set()
        deduped: list[dict[str, Any]] = []
        for operation in selected_operations:
            identity = id(operation)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(operation)
        return deduped
    return []


def agent_proposals_by_iteration(request: dict[str, Any]) -> dict[int, dict[str, Any]]:
    proposals: dict[int, dict[str, Any]] = {}
    for proposal in request.get("agent_review_proposals", []) or []:
        if not isinstance(proposal, dict):
            continue
        iteration = proposal.get("iteration")
        if type(iteration) is not int or iteration <= 0:
            continue
        proposals[iteration] = proposal
    return proposals


def agent_proposal_list_errors(request: dict[str, Any]) -> list[dict[str, Any]]:
    raw_proposals = request.get("agent_review_proposals", [])
    if not isinstance(raw_proposals, list):
        return [
            {
                "code": "agent_review_proposals_must_be_list",
                "message": "agent_review_proposals must be a list of proposal mappings.",
            }
        ]
    errors: list[dict[str, Any]] = []
    seen_iterations: set[int] = set()
    for index, proposal in enumerate(raw_proposals):
        if not isinstance(proposal, dict):
            errors.append(
                {
                    "code": "agent_review_proposal_must_be_mapping",
                    "proposal_index": index,
                    "message": "Every agent_review_proposals entry must be a mapping.",
                }
            )
            continue
        iteration = proposal.get("iteration")
        if type(iteration) is not int:
            errors.append(
                {
                    "code": "agent_review_proposal_iteration_invalid",
                    "proposal_index": index,
                    "message": "Every agent_review_proposals entry must declare a positive integer iteration.",
                }
            )
            continue
        if iteration <= 0:
            errors.append(
                {
                    "code": "agent_review_proposal_iteration_missing",
                    "proposal_index": index,
                    "message": "Every agent_review_proposals entry must declare a positive integer iteration.",
                }
            )
            continue
        if iteration in seen_iterations:
            errors.append(
                {
                    "code": "agent_review_proposal_duplicate_iteration",
                    "proposal_index": index,
                    "iteration": iteration,
                    "message": "agent_review_proposals must contain at most one proposal per iteration.",
                }
            )
        seen_iterations.add(iteration)
    return errors


def last_iteration_requires_confirmation(iterations: list[dict[str, Any]]) -> bool:
    if not iterations:
        return False
    last = iterations[-1]
    for state in last.get("states", []):
        if state.get("role") == "gate" and state.get("reason") == "agent_proposal_applied_for_next_iteration":
            return True
    return False


def proposal_template(iteration: int, findings: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    blocking = [finding for finding in findings if finding.get("severity") == "error"]
    focus_codes = []
    for finding in blocking or findings:
        code = str(finding.get("code") or finding.get("check") or "")
        if code and code not in focus_codes:
            focus_codes.append(code)
        if len(focus_codes) >= 8:
            break
    return {
        "iteration": iteration,
        "proposal_id": f"agent-review-iter-{iteration:03d}",
        "role": "agent_driven_review_loop",
        "target_score_ratio": rubric.get("score_ratio"),
        "focus_finding_codes": focus_codes,
        "required_fields": [
            "iteration",
            "proposal_id",
            "rationale",
            "analyst_error",
            "analyst_success",
            "merge_failure",
            "merge_success",
            "merge_final",
            "ranking",
            "slow_update",
            "operations",
            "expected_improvement",
        ],
        "review_loop_order": [
            "record_score",
            "rollout_plan",
            "analyst_error",
            "analyst_success",
            "merge_failure",
            "merge_success",
            "merge_final",
            "ranking",
            "apply",
            "record_score",
            "strict_greater_than_gate",
            "slow_update",
        ],
        "allowed_operations": [
            "ensure_refusal_boundaries",
            "ensure_contract_grounding_notes",
            "ensure_operational_recipe",
            "downgrade_execution_verification_without_trace",
            "rebuild_task_type_router",
        ],
        "operation_schema": {
            "operation_id": "stable unique id used by merge_final and ranking",
            "operation": "one allowed operation name",
            "task_type": "task_type to edit, or * for all task types",
            "rationale": "evidence-grounded reason for this operation",
            "finding_codes": "non-empty list of same-iteration finding codes that justify this operation",
        },
        "forbidden_actions": [
            "execute package code",
            "install dependencies",
            "perform network access",
            "edit files outside task_catalog or task_type_router",
            "mark execution_verified without trace_ref",
        ],
        "notes": [
            "The agent writes analyst/merge/ranking JSON in the proposal; Python validates and applies bounded in-memory operations only.",
            "Use supplied rollout observations when available; otherwise use current rubric findings as the failure minibatch.",
            "Ranking must choose operations by operation_ids or operation_indices inside the edit budget; ties or non-improving candidates are rejected after rescoring.",
        ],
    }


def next_step(iteration: int, findings: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": "awaiting_agent_review_loop",
        "iteration": iteration,
        "instruction": "Codex must supply a complete agent-driven paper2skills review loop proposal: analyst_error, analyst_success, merge_failure, merge_success, merge_final, ranking, then bounded operations.",
        "proposal_template": proposal_template(iteration, findings, rubric),
    }


def has_blocking_findings(findings: list[dict[str, Any]]) -> bool:
    return any(finding.get("severity") == "error" for finding in findings)


def gate_state(passed: bool, reason: str, candidate_hash: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    state = {
        "role": "gate",
        "passed": passed,
        "reason": reason,
        "strict_improvement_gate": True,
        "candidate_hash": candidate_hash,
    }
    if extra:
        state.update(extra)
    return state


def review_loop(
    request: dict[str, Any],
    discovery_report: dict[str, Any],
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
    max_iterations = int(request.get("review_iterations") or 3)
    min_score_ratio = float(request.get("review_min_score_ratio") or 0.875)
    proposal_list_errors = agent_proposal_list_errors(request)
    proposals = agent_proposals_by_iteration(request)
    iterations = []
    current_catalog = task_catalog
    current_router = router
    stop_reason = "iteration_budget_exhausted"
    pending_next_step: dict[str, Any] | None = None
    score_cache: dict[str, float] = {}
    rejected_buffer: list[dict[str, Any]] = []
    candidate_versions = [
        {
            "version_id": "agent-review:v000",
            "iteration": 0,
            "source": "initial_task_partition",
            "task_types": [task.get("task_type") for task in task_catalog.get("tasks", [])],
            "route_count": len(router.get("routes", [])),
        }
    ]

    for iteration in range(1, max_iterations + 1):
        checklist = self_review(request, discovery_report, source_grounding, current_catalog, current_router)
        rubric = score_artifacts(
            source_grounding,
            current_catalog,
            current_router,
            evidence_cards,
            api_grounding,
            interface_grounding,
            environment_spec,
            tutorial_catalog,
            parameter_catalog,
        )
        findings = checklist + rubric["findings"]
        candidate_hash = stable_hash({"task_catalog": current_catalog, "router": current_router})
        score_cache[candidate_hash] = float(rubric["score_ratio"])
        blocking = has_blocking_findings(findings)
        passed = not blocking and rubric["score_ratio"] >= min_score_ratio
        event = {
            "event": "review_iteration",
            "created_at": now_utc(),
            "iteration": iteration,
            "score": rubric["score"],
            "total": rubric["total"],
            "score_ratio": rubric["score_ratio"],
            "blocking": blocking,
            "passed": passed,
            "findings": findings,
            "states": [
                draft_snapshot(current_catalog, current_router),
                record_score_state(rubric, candidate_hash, iteration),
                rollout_plan_state(request, current_catalog),
                critic_state(findings, rubric),
            ],
        }

        if proposal_list_errors:
            event["patch"] = {
                "changed": False,
                "patch_summary": "Agent review proposal list failed required contracts.",
                "finding_count": len(findings),
                "actions": [],
                "proposal_source": "agent_review_proposals",
                "proposal_errors": proposal_list_errors,
            }
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch was applied because agent_review_proposals contains malformed or duplicate entries.",
                "proposal_errors": proposal_list_errors,
            }
            event["states"].append(event["patch_plan"])
            event["states"].append(gate_state(False, "agent_review_loop_invalid", candidate_hash))
            iterations.append(event)
            rejected_buffer.append(
                {
                    "iteration": iteration,
                    "reason": "invalid_agent_review_proposal_list",
                    "proposal_errors": proposal_list_errors,
                    "score_ratio": rubric.get("score_ratio"),
                }
            )
            stop_reason = "agent_proposal_rejected"
            break

        if passed:
            event["patch"] = {"changed": False, "patch_summary": "Selection score gate passed."}
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch needed because the selection score gate passed.",
            }
            event["states"].append(event["patch_plan"])
            event["states"].append(gate_state(True, "selection_score_gate_passed", candidate_hash))
            iterations.append(event)
            stop_reason = "rubric_gate_passed"
            break

        proposal = proposals.get(iteration)
        if not proposal:
            pending_next_step = next_step(iteration, findings, rubric)
            event["states"].extend(review_loop_stage_states(None))
            event["patch"] = {
                "changed": False,
                "patch_summary": "Awaiting agent-driven paper2skills review loop proposal.",
                "finding_count": len(findings),
                "actions": [],
                "agent_required": True,
            }
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No Python fallback patch was applied; Codex must supply a complete agent_review_proposals review-loop entry.",
                "agent_required": True,
                "next_step": pending_next_step,
            }
            event["states"].append(event["patch_plan"])
            event["states"].append(gate_state(False, "awaiting_agent_review_loop", candidate_hash))
            iterations.append(event)
            stop_reason = "awaiting_agent_proposal"
            break

        event["states"].extend(review_loop_stage_states(proposal))
        missing_roles = missing_proposal_roles(proposal)
        proposal_errors = proposal_validation_errors(proposal)
        if proposal_errors:
            rejected_buffer.append(
                {
                    "iteration": iteration,
                    "proposal_id": proposal.get("proposal_id"),
                    "reason": "invalid_required_review_loop_contract",
                    "missing_roles": missing_roles,
                    "proposal_errors": proposal_errors,
                    "score_ratio": rubric.get("score_ratio"),
                }
            )
            event["patch"] = {
                "changed": False,
                "patch_summary": "Agent paper2skills review loop proposal failed required contracts.",
                "finding_count": len(findings),
                "actions": [],
                "proposal_id": proposal.get("proposal_id"),
                "proposal_source": "agent_review_proposals",
                "rejected_operations": [],
                "missing_review_loop_roles": missing_roles,
                "proposal_errors": proposal_errors,
            }
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch was applied because the agent proposal failed required paper2skills review loop contracts.",
                "agent_proposal": {
                    "proposal_id": proposal.get("proposal_id"),
                    "iteration": proposal.get("iteration"),
                    "missing_review_loop_roles": missing_roles,
                    "proposal_errors": proposal_errors,
                },
            }
            event["states"].append(event["patch_plan"])
            event["states"].append(gate_state(False, "agent_review_loop_invalid", candidate_hash))
            iterations.append(event)
            stop_reason = "agent_proposal_rejected"
            break
        selected_proposal = dict(proposal)
        selected_proposal["operations"] = selected_operations_from_ranking(proposal)
        patch = apply_agent_review_proposal(current_catalog, current_router, selected_proposal, findings)
        event["patch"] = {
            "changed": patch["changed"],
            "patch_summary": patch["patch_summary"],
            "finding_count": patch["finding_count"],
            "actions": patch.get("actions", []),
            "proposal_id": patch.get("proposal_id"),
            "proposal_source": "agent_review_proposals",
            "rejected_operations": patch.get("rejected_operations", []),
        }
        event["patch_plan"] = {
            "role": "patch_plan",
            "changed": patch["changed"],
            "actions": patch.get("actions", []),
            "summary": patch["patch_summary"],
            "agent_proposal": {
                "proposal_id": proposal.get("proposal_id"),
                "iteration": proposal.get("iteration"),
                "rationale": proposal.get("rationale"),
                "operation_count": len(selected_proposal.get("operations", [])) if isinstance(selected_proposal.get("operations"), list) else 0,
                "review_loop_roles_recorded": [
                    role for role in REVIEW_LOOP_ROLES if isinstance(proposal.get(role), dict)
                ],
            },
        }
        event["states"].append(event["patch_plan"])

        if patch.get("rejected_operations"):
            rejected_buffer.append(
                {
                    "iteration": iteration,
                    "proposal_id": proposal.get("proposal_id"),
                    "reason": "selected_operation_rejected_by_patch_planner",
                    "score_ratio": rubric.get("score_ratio"),
                    "rejected_operations": patch.get("rejected_operations", []),
                }
            )
            event["patch"] = {
                "changed": False,
                "patch_summary": "Agent review-loop proposal was rejected because at least one selected operation failed patch-planner validation.",
                "finding_count": patch["finding_count"],
                "actions": [],
                "candidate_actions": patch.get("actions", []),
                "proposal_id": patch.get("proposal_id"),
                "proposal_source": "agent_review_proposals",
                "rejected_operations": patch.get("rejected_operations", []),
            }
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch was accepted because selected operations must all satisfy patch-planner contracts.",
                "agent_proposal": {
                    "proposal_id": proposal.get("proposal_id"),
                    "iteration": proposal.get("iteration"),
                    "rationale": proposal.get("rationale"),
                    "operation_count": len(selected_proposal.get("operations", [])) if isinstance(selected_proposal.get("operations"), list) else 0,
                    "rejected_operation_count": len(patch.get("rejected_operations", [])),
                },
            }
            event["states"] = [state for state in event["states"] if state.get("role") != "patch_plan"]
            event["states"].append(event["patch_plan"])
            event["states"].append(gate_state(False, "agent_selected_operation_rejected", candidate_hash))
            iterations.append(event)
            stop_reason = "agent_proposal_rejected"
            break

        if not patch["changed"]:
            rejected_buffer.append(
                {
                    "iteration": iteration,
                    "proposal_id": proposal.get("proposal_id"),
                    "reason": "agent_proposal_rejected_or_no_allowed_changes",
                    "score_ratio": rubric.get("score_ratio"),
                }
            )
            event["states"].append(gate_state(False, "agent_proposal_rejected", candidate_hash))
            iterations.append(event)
            stop_reason = "agent_proposal_rejected"
            break

        candidate_catalog = patch["task_catalog"]
        candidate_router = patch["router"]
        candidate_hash = stable_hash({"task_catalog": candidate_catalog, "router": candidate_router})
        candidate_checklist = self_review(request, discovery_report, source_grounding, candidate_catalog, candidate_router)
        candidate_rubric = score_artifacts(
            source_grounding,
            candidate_catalog,
            candidate_router,
            evidence_cards,
            api_grounding,
            interface_grounding,
            environment_spec,
            tutorial_catalog,
            parameter_catalog,
        )
        score_cache[candidate_hash] = float(candidate_rubric["score_ratio"])
        event["states"].append(record_score_state(candidate_rubric, candidate_hash, iteration, "post_apply_candidate"))
        improved = float(candidate_rubric["score_ratio"]) > float(rubric["score_ratio"])
        if not improved:
            rejected_buffer.append(
                {
                    "iteration": iteration,
                    "proposal_id": proposal.get("proposal_id"),
                    "reason": "candidate_score_not_strictly_greater",
                    "previous_score_ratio": rubric.get("score_ratio"),
                    "candidate_score_ratio": candidate_rubric.get("score_ratio"),
                    "candidate_hash": candidate_hash,
                }
            )
            event["patch"] = {
                "changed": False,
                "patch_summary": "Agent review-loop candidate was rejected because it did not strictly improve the score.",
                "finding_count": patch["finding_count"],
                "actions": [],
                "candidate_actions": patch.get("actions", []),
                "proposal_id": patch.get("proposal_id"),
                "proposal_source": "agent_review_proposals",
                "rejected_operations": patch.get("rejected_operations", []),
                "previous_score_ratio": rubric.get("score_ratio"),
                "candidate_score_ratio": candidate_rubric.get("score_ratio"),
                "candidate_hash": candidate_hash,
                "candidate_findings": candidate_checklist + candidate_rubric["findings"],
            }
            event["patch_plan"] = {
                "role": "patch_plan",
                "changed": False,
                "actions": [],
                "summary": "No patch was accepted because the candidate failed the strict improvement gate.",
                "agent_proposal": {
                    "proposal_id": proposal.get("proposal_id"),
                    "iteration": proposal.get("iteration"),
                    "rationale": proposal.get("rationale"),
                    "operation_count": len(selected_proposal.get("operations", [])) if isinstance(selected_proposal.get("operations"), list) else 0,
                    "rejected_action_count": len(patch.get("actions", [])),
                },
            }
            event["states"] = [state for state in event["states"] if state.get("role") != "patch_plan"]
            event["states"].append(event["patch_plan"])
            event["states"].append(
                gate_state(
                    False,
                    "agent_proposal_non_improving",
                    candidate_hash,
                    {
                        "previous_candidate_hash": stable_hash({"task_catalog": current_catalog, "router": current_router}),
                        "previous_score_ratio": rubric.get("score_ratio"),
                        "candidate_score_ratio": candidate_rubric.get("score_ratio"),
                    },
                )
            )
            iterations.append(event)
            stop_reason = "agent_proposal_rejected"
            break

        current_catalog = candidate_catalog
        current_router = candidate_router
        event["states"].append(revision_state(patch))

        candidate_versions.append(
            {
                "version_id": f"agent-review:v{iteration:03d}",
                "iteration": iteration,
                "source": "agent_review_loop_proposal",
                "proposal_id": proposal.get("proposal_id"),
                "task_types": [task.get("task_type") for task in current_catalog.get("tasks", [])],
                "route_count": len(current_router.get("routes", [])),
                "action_count": len(patch.get("actions", [])),
            }
        )
        event["states"].append(
            gate_state(
                False,
                "agent_proposal_applied_for_next_iteration",
                candidate_hash,
                {
                    "next_phase": "applied_awaiting_record_score",
                    "previous_score_ratio": rubric.get("score_ratio"),
                    "candidate_score_ratio": candidate_rubric.get("score_ratio"),
                },
            )
        )
        iterations.append(event)

    final_checklist = self_review(request, discovery_report, source_grounding, current_catalog, current_router)
    final_rubric = score_artifacts(
        source_grounding,
        current_catalog,
        current_router,
        evidence_cards,
        api_grounding,
        interface_grounding,
        environment_spec,
        tutorial_catalog,
        parameter_catalog,
    )
    final_findings = final_checklist + final_rubric["findings"]
    status = "passed" if final_rubric["score_ratio"] >= min_score_ratio and not has_blocking_findings(final_findings) else "needs_review"
    if stop_reason in {"awaiting_agent_proposal", "agent_proposal_rejected"}:
        status = "needs_agent"
    requires_confirming_iteration = last_iteration_requires_confirmation(iterations)
    if requires_confirming_iteration:
        status = "needs_agent"
        stop_reason = "awaiting_confirming_iteration"
        pending_next_step = {
            "phase": "awaiting_confirming_iteration",
            "action": "rerun_with_one_more_review_iteration_to_confirm_last_patch",
            "reason": "The last accepted patch improved the score but has not yet been observed as the starting state of a scored pass-gated iteration.",
            "proposal_template": proposal_template(len(iterations) + 1, final_findings, final_rubric),
        }
    return {
        "mode": "agent_driven_review_loop",
        "review_loop_version": "agent_driven_review_loop_v1",
        "agent_driven": True,
        "task_catalog": current_catalog,
        "router": current_router,
        "iterations": iterations,
        "candidate_versions": candidate_versions,
        "score_cache": score_cache,
        "rejected_buffer": rejected_buffer,
        "final_score": final_rubric,
        "final_findings": final_findings,
        "stop_reason": stop_reason,
        "requires_confirming_iteration": requires_confirming_iteration,
        "next_step": pending_next_step,
        "status": status,
    }
