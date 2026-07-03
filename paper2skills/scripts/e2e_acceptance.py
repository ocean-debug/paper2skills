"""Plan and audit real end-to-end acceptance evidence."""

from __future__ import annotations

from typing import Any

from common import as_list, now_utc, slugify
from constants import SCHEMA_VERSION


PASS_STATUSES = {"pass", "passed", "ok", "success"}
FAIL_STATUSES = {"fail", "failed", "error"}
KNOWN_STATUSES = PASS_STATUSES | FAIL_STATUSES | {"unknown", "not_run"}

REQUIRED_SUCCESS_FIELDS = [
    "scenario_id",
    "status",
    "artifact_refs",
    "observed_outputs",
    "completed_checks",
]
REQUIRED_FAILURE_FIELDS = [
    "scenario_id",
    "status",
    "failure_reason",
]


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    scenario_id: str | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if scenario_id:
        finding["scenario_id"] = scenario_id
    findings.append(finding)


def scenario(
    scenario_id: str,
    kind: str,
    purpose: str,
    required: bool,
    artifact_refs: list[str],
    pass_checks: list[str],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "kind": kind,
        "purpose": purpose,
        "required_for_full_e2e": required,
        "artifact_refs": artifact_refs,
        "pass_checks": pass_checks,
        "result_contract": {
            "required_success_fields": REQUIRED_SUCCESS_FIELDS,
            "required_failure_fields": REQUIRED_FAILURE_FIELDS,
        },
    }


def task_scenario(task: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type") or "task")
    return scenario(
        f"e2e:task-type:{slugify(task_type)}",
        "task_type_acceptance",
        "Confirm one task_type can be selected, planned, refused for invalid inputs, and validated from the generated child skill.",
        True,
        [
            "child_skill/SKILL.md",
            "child_skill/references/task-types.md",
            "child_skill/references/input-output-contracts.md",
            "child_skill/references/limitations-and-refusal.md",
            "task_catalog.yaml",
            "task_type_router.yaml",
            "acceptance_suite.yaml",
        ],
        [
            "agent selects this task_type for a matching user goal",
            "agent asks for missing required inputs instead of inventing them",
            "agent returns a structured refusal for at least one invalid-input case",
            "agent names expected outputs and validation checks from references",
        ],
    )


def build_scenarios(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    acceptance_suite: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = task_catalog.get("tasks", [])
    scenarios = [
        scenario(
            "e2e:full-build-artifacts",
            "build_artifact_acceptance",
            "Confirm a full builder run produced the child skill and required run artifacts.",
            True,
            [
                "child_skill/SKILL.md",
                "child_skill/references/task-types.md",
                "child_skill/references/input-output-contracts.md",
                "child_skill/references/limitations-and-refusal.md",
                "child_skill/references/validation.md",
                "child_skill/references/troubleshooting.md",
                "child_skill/references/evidence.md",
                "child_skill/references/environment.md",
                "run_manifest.yaml",
            ],
            [
                "exactly one child skill directory is produced",
                "required child skill markdown files exist",
                "run manifest records build artifacts",
            ],
        ),
        scenario(
            "e2e:one-package-one-skill",
            "child_skill_shape_acceptance",
            "Confirm capabilities stay inside one child skill as task_type entries.",
            True,
            ["task_catalog.yaml", "skill_spec.yaml", "child_metadata_audit.yaml", "child_package_purity_audit.yaml"],
            [
                "task_catalog one_package_one_skill is true",
                "child package contains only SKILL.md and standard references",
                "no separate task-selector child skill is produced",
            ],
        ),
        scenario(
            "e2e:structured-refusal",
            "refusal_acceptance",
            "Confirm invalid or unsupported inputs produce structured refusal instead of unsafe execution.",
            True,
            ["acceptance_suite.yaml", "forward_test_plan.yaml", "agent_rollout_harness.yaml"],
            [
                "at least one structured_refusal case is exercised",
                "refusal contains reason_key",
                "fixable refusals include what the user must provide",
            ],
        ),
        scenario(
            "e2e:no-unverified-execution-claims",
            "verification_claim_acceptance",
            "Confirm source-grounded tasks are not described as execution verified without execution evidence.",
            True,
            ["task_catalog.yaml", "verification_claim_audit.yaml", "execution_trace_validation.yaml"],
            [
                "untraced task_type entries remain source_grounded",
                "execution_verified entries include a validated trace_ref",
                "child skill validation reference renders verification status",
            ],
        ),
        scenario(
            "e2e:agent-rollout",
            "agent_rollout_acceptance",
            "Confirm an independent agent can use the generated child skill for routing, contracts, refusal, and execution-boundary prompts.",
            True,
            ["agent_rollout_harness.yaml", "agent_rollout_result_judge.yaml", "eval_leakage_audit.yaml"],
            [
                "rollout result evidence references rollout_id or scenario_id",
                "observed decisions match static expectations",
                "agent-visible prompts do not include hidden expected answers",
            ],
        ),
    ]
    scenarios.extend(task_scenario(task) for task in tasks)

    if request.get("execution_grounded") or execution_replay_orchestrator.get("job_count", 0) > 0:
        scenarios.append(
            scenario(
                "e2e:execution-grounded-replay",
                "execution_grounding_acceptance",
                "Confirm optional execution grounding only promotes successfully replayed task_type paths.",
                bool(request.get("execution_grounded")),
                ["execution_replay_orchestrator.yaml", "tutorial_reproduction_plan.yaml", "verification_claim_audit.yaml"],
                [
                    "ready replay jobs are explicitly approved before execution",
                    "successful replay results include trace_ref and validation checks",
                    "failed replay paths update troubleshooting without claiming verified status",
                ],
            )
        )

    scenarios.append(
        scenario(
            "e2e:publish-install-readiness",
            "release_acceptance",
            "Confirm publish and install artifacts agree with the selected create, update, or reuse action.",
            True,
            ["publish_gate.yaml", "release_package.yaml", "install_readiness.yaml", "publish_manifest.yaml"],
            [
                "publish gate is publishable or reuse_ready",
                "release package action matches skill update plan",
                "install readiness action matches publish manifest",
            ],
        )
    )

    if acceptance_suite.get("case_count", 0) == 0 or agent_rollout_harness.get("rollout_count", 0) == 0:
        scenarios.append(
            scenario(
                "e2e:acceptance-coverage-repair",
                "coverage_repair_acceptance",
                "Confirm missing acceptance or rollout coverage is repaired before claiming full end-to-end acceptance.",
                True,
                ["acceptance_suite.yaml", "agent_rollout_harness.yaml"],
                [
                    "acceptance suite has routing, contract, refusal, and execution-boundary cases",
                    "rollout harness covers every task_type",
                ],
            )
        )

    return scenarios


def result_template(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": scenario.get("scenario_id"),
        "kind": scenario.get("kind"),
        "status": None,
        "artifact_refs": [],
        "artifact_refs_to_review": scenario.get("artifact_refs", []),
        "observed_outputs": [],
        "completed_checks": [],
        "checks_to_complete": scenario.get("pass_checks", []),
        "failure_reason": None,
        "notes": [],
        "source_run_id": None,
    }


def result_status(result: dict[str, Any]) -> str:
    return str(result.get("status") or "").lower()


def result_is_success(result: dict[str, Any]) -> bool:
    return result_status(result) in PASS_STATUSES


def missing_result_fields(result: dict[str, Any]) -> list[str]:
    fields = REQUIRED_SUCCESS_FIELDS if result_is_success(result) else REQUIRED_FAILURE_FIELDS
    missing = [field for field in fields if not result.get(field)]
    if result_is_success(result):
        if not isinstance(result.get("artifact_refs"), list):
            missing.append("artifact_refs:list")
        if not isinstance(result.get("completed_checks"), list):
            missing.append("completed_checks:list")
    return missing


def result_record(
    index: int,
    result: Any,
    scenarios_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "result_index": index,
            "scenario_id": None,
            "status": "invalid",
            "known_scenario": False,
            "success": False,
            "required_for_full_e2e": None,
            "missing_fields": ["result_object"],
        }
    scenario_id = str(result.get("scenario_id") or "")
    matched = scenarios_by_id.get(scenario_id, {})
    status = result_status(result) or "missing"
    return {
        "result_index": index,
        "scenario_id": scenario_id,
        "status": status,
        "known_scenario": bool(matched),
        "success": result_is_success(result),
        "required_for_full_e2e": matched.get("required_for_full_e2e"),
        "missing_fields": missing_result_fields(result),
        "artifact_ref_count": len(result.get("artifact_refs", [])) if isinstance(result.get("artifact_refs"), list) else 0,
        "completed_check_count": len(result.get("completed_checks", [])) if isinstance(result.get("completed_checks"), list) else 0,
        "has_failure_reason": bool(result.get("failure_reason") or result.get("error") or result.get("message")),
    }


def build_e2e_acceptance(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    acceptance_suite: dict[str, Any],
    eval_splits: dict[str, Any],
    forward_test_plan: dict[str, Any],
    agent_rollout_harness: dict[str, Any],
    agent_rollout_result_judge: dict[str, Any],
    execution_replay_orchestrator: dict[str, Any],
    verification_claim_audit: dict[str, Any],
) -> dict[str, Any]:
    """Return end-to-end acceptance scenarios and audit supplied results."""
    findings: list[dict[str, Any]] = []
    scenarios = build_scenarios(
        request,
        task_catalog,
        acceptance_suite,
        agent_rollout_harness,
        execution_replay_orchestrator,
    )
    scenarios_by_id = {str(item.get("scenario_id")): item for item in scenarios}
    result_templates = [result_template(item) for item in scenarios]
    required_ids = {
        str(item.get("scenario_id"))
        for item in scenarios
        if item.get("required_for_full_e2e")
    }

    results = as_list(request.get("e2e_acceptance_results"))
    records = [result_record(index, result, scenarios_by_id) for index, result in enumerate(results, start=1)]

    if acceptance_suite.get("case_count", 0) == 0:
        add_finding(findings, "error", "missing_acceptance_cases", "E2E acceptance requires static acceptance cases.")
    if eval_splits.get("status") == "fail":
        add_finding(findings, "error", "eval_splits_failed", "E2E acceptance requires valid eval splits.")
    if forward_test_plan.get("status") != "pass":
        add_finding(findings, "error", "forward_test_plan_failed", "E2E acceptance requires a passing forward-test plan.")
    if agent_rollout_harness.get("status") != "pass":
        add_finding(findings, "error", "agent_rollout_harness_failed", "E2E acceptance requires a passing agent rollout harness.")
    if agent_rollout_result_judge.get("status") == "fail":
        add_finding(findings, "error", "agent_rollout_result_judge_failed", "Supplied agent rollout results failed.")
    if verification_claim_audit.get("status") != "pass":
        add_finding(findings, "error", "verification_claim_audit_failed", "Verification claim audit must pass before E2E acceptance.")
    if execution_replay_orchestrator.get("status") != "pass":
        add_finding(findings, "error", "execution_replay_orchestrator_failed", "Execution replay orchestration must pass before E2E acceptance.")

    for record in records:
        scenario_id = str(record.get("scenario_id") or "")
        status = str(record.get("status") or "")
        if status == "invalid":
            add_finding(findings, "error", "invalid_e2e_result_object", "E2E result must be a mapping.")
            continue
        if status not in KNOWN_STATUSES:
            add_finding(findings, "error", "unknown_e2e_result_status", "E2E result status is not recognized.", scenario_id)
        if not record.get("known_scenario"):
            add_finding(findings, "error", "unknown_e2e_scenario", "E2E result references an unknown scenario_id.", scenario_id)
        if record.get("missing_fields"):
            severity = "error" if record.get("success") else "warning"
            add_finding(findings, severity, "e2e_result_missing_fields", "E2E result is missing required fields.", scenario_id)
        if status in FAIL_STATUSES:
            add_finding(findings, "error", "e2e_result_reported_fail", "Supplied E2E acceptance result reported failure.", scenario_id)
        if not record.get("success") and status in FAIL_STATUSES and not record.get("has_failure_reason"):
            add_finding(findings, "warning", "failed_e2e_without_reason", "Failed E2E result should include failure_reason.", scenario_id)

    passed_required_ids = {
        str(record.get("scenario_id"))
        for record in records
        if record.get("known_scenario")
        and record.get("required_for_full_e2e")
        and record.get("success")
        and not record.get("missing_fields")
    }
    missing_required_ids = sorted(required_ids.difference(passed_required_ids))

    e2e_verdict = "not_run"
    if records:
        e2e_verdict = "passed" if not missing_required_ids and all(record.get("success") for record in records if record.get("known_scenario")) else "partial"
    if any(str(record.get("status")) in FAIL_STATUSES for record in records):
        e2e_verdict = "failed"

    if request.get("require_e2e_acceptance") and missing_required_ids:
        add_finding(
            findings,
            "error",
            "required_e2e_acceptance_not_passed",
            "require_e2e_acceptance is true, but required E2E scenarios have no passing supplied result.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "require_e2e_acceptance": bool(request.get("require_e2e_acceptance")),
        "e2e_verdict": e2e_verdict,
        "scenario_count": len(scenarios),
        "required_scenario_count": len(required_ids),
        "result_count": len(records),
        "result_template_count": len(result_templates),
        "passed_required_scenario_count": len(passed_required_ids),
        "missing_required_scenarios": missing_required_ids,
        "scenarios": scenarios,
        "result_templates": result_templates,
        "result_records": records,
        "findings": findings,
        "policy": [
            "E2E acceptance is plan-only; it never runs package code or launches agents.",
            "Full E2E acceptance requires explicit supplied results for all required scenarios.",
            "Static build gates can pass without E2E results unless require_e2e_acceptance is true.",
        ],
    }
