"""Plan-only smoke test scenarios and supplied-result audit."""

from __future__ import annotations

from typing import Any

from common import as_list, now_utc, slugify
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


PASS_STATUSES = {"pass", "passed", "ok", "success"}
FAIL_STATUSES = {"fail", "failed", "error"}
KNOWN_STATUSES = PASS_STATUSES | FAIL_STATUSES | {"unknown", "not_run"}


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
    purpose: str,
    artifact_refs: list[str],
    pass_checks: list[str],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "purpose": purpose,
        "artifact_refs": artifact_refs,
        "pass_checks": pass_checks,
        "result_contract": {
            "required_success_fields": ["scenario_id", "status", "artifact_refs", "completed_checks"],
            "required_failure_fields": ["scenario_id", "status", "failure_reason"],
        },
    }


def build_scenarios(task_catalog: dict[str, Any]) -> list[dict[str, Any]]:
    references = [f"child_skill/references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    scenarios = [
        scenario(
            "smoke:child-skill-files",
            "Confirm the generated child skill has exactly the required lightweight public files.",
            ["child_skill/SKILL.md", *references, "release_package.yaml", "install_readiness.yaml"],
            [
                "SKILL.md exists and is non-empty",
                "all required reference files exist and are non-empty",
                "no build-run artifacts are inside the public child skill",
            ],
        ),
        scenario(
            "smoke:task-router",
            "Confirm task_type routing metadata is present for every generated task.",
            ["task_catalog.yaml", "task_type_router.yaml", "routing_metadata_audit.yaml"],
            [
                "task_catalog contains at least one task_type",
                "each task_type has a router entry",
                "unsupported requests have a refusal path",
            ],
        ),
        scenario(
            "smoke:contracts-and-refusals",
            "Confirm generated task contracts and refusal boundaries are visible to an agent.",
            [
                "child_skill/references/input-output-contracts.md",
                "child_skill/references/limitations-and-refusal.md",
                "acceptance_suite.yaml",
            ],
            [
                "each task_type has required input fields",
                "each task_type has expected outputs",
                "each task_type has at least one structured refusal case",
            ],
        ),
        scenario(
            "smoke:verification-labels",
            "Confirm verification labels do not overclaim execution evidence.",
            ["task_catalog.yaml", "verification_claim_audit.yaml", "child_skill/references/validation.md"],
            [
                "source_grounded tasks are not labeled execution_verified",
                "execution_verified tasks have trace_ref",
                "validation reference renders verification status",
            ],
        ),
        scenario(
            "smoke:publish-plan",
            "Confirm release and publish-plan artifacts agree on create/update/reuse action.",
            ["publish_gate.yaml", "release_package.yaml", "codex_publish_adapter.yaml", "publish_manifest_audit.yaml"],
            [
                "publish action matches skill update plan",
                "Codex publish adapter is plan-only",
                "reuse action does not copy a duplicate child skill",
            ],
        ),
    ]
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type") or "task")
        scenarios.append(
            scenario(
                f"smoke:task:{slugify(task_type, 'task')}",
                "Confirm an agent can locate core instructions for this task_type without running code.",
                ["child_skill/SKILL.md", "child_skill/references/task-types.md", "acceptance_suite.yaml"],
                [
                    "task_type appears in SKILL.md or task-types reference",
                    "task_type has a routing cue",
                    "task_type has a contract or refusal case",
                ],
            )
        )
    return scenarios


def result_status(result: dict[str, Any]) -> str:
    return str(result.get("status") or "").strip().lower()


def result_success(result: dict[str, Any]) -> bool:
    return result_status(result) in PASS_STATUSES


def missing_fields(result: dict[str, Any]) -> list[str]:
    required = ["scenario_id", "status", "artifact_refs", "completed_checks"] if result_success(result) else ["scenario_id", "status", "failure_reason"]
    missing = [field for field in required if not result.get(field)]
    if result_success(result):
        if not isinstance(result.get("artifact_refs"), list):
            missing.append("artifact_refs:list")
        if not isinstance(result.get("completed_checks"), list):
            missing.append("completed_checks:list")
    return missing


def result_record(index: int, result: Any, scenario_ids: set[str]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "result_index": index,
            "scenario_id": None,
            "status": "invalid",
            "known_scenario": False,
            "success": False,
            "missing_fields": ["result_object"],
        }
    scenario_id = str(result.get("scenario_id") or "")
    status = result_status(result) or "missing"
    return {
        "result_index": index,
        "scenario_id": scenario_id,
        "status": status,
        "known_scenario": scenario_id in scenario_ids,
        "success": result_success(result),
        "missing_fields": missing_fields(result),
        "artifact_ref_count": len(result.get("artifact_refs", [])) if isinstance(result.get("artifact_refs"), list) else 0,
        "completed_check_count": len(result.get("completed_checks", [])) if isinstance(result.get("completed_checks"), list) else 0,
    }


def build_smoke_test_plan(request: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    """Return plan-only smoke test scenarios and audit any supplied results."""
    scenarios = build_scenarios(task_catalog)
    scenario_ids = {str(item.get("scenario_id")) for item in scenarios}
    results = as_list(request.get("smoke_test_results"))
    records = [result_record(index, result, scenario_ids) for index, result in enumerate(results, start=1)]
    findings: list[dict[str, Any]] = []

    for record in records:
        scenario_id = str(record.get("scenario_id") or "")
        status = str(record.get("status") or "")
        if status == "invalid":
            add_finding(findings, "error", "invalid_smoke_result_object", "Smoke test result must be a mapping.")
            continue
        if status not in KNOWN_STATUSES:
            add_finding(findings, "error", "unknown_smoke_result_status", "Smoke test result status is not recognized.", scenario_id)
        if not record.get("known_scenario"):
            add_finding(findings, "error", "unknown_smoke_scenario", "Smoke test result references an unknown scenario_id.", scenario_id)
        if record.get("missing_fields"):
            add_finding(findings, "error", "smoke_result_missing_fields", "Smoke test result is missing required fields.", scenario_id)
        if status in FAIL_STATUSES:
            add_finding(findings, "error", "smoke_result_reported_fail", "Supplied smoke test result reported failure.", scenario_id)

    passed_ids = {
        str(record.get("scenario_id"))
        for record in records
        if record.get("known_scenario") and record.get("success") and not record.get("missing_fields")
    }
    missing_required = sorted(scenario_ids.difference(passed_ids))
    smoke_verdict = "not_run"
    if records:
        smoke_verdict = "passed" if not missing_required and all(record.get("success") for record in records if record.get("known_scenario")) else "partial"
    if any(str(record.get("status")) in FAIL_STATUSES for record in records):
        smoke_verdict = "failed"
    if request.get("require_smoke_test") and smoke_verdict != "passed":
        add_finding(findings, "error", "required_smoke_test_not_passed", "require_smoke_test is true, but smoke test results are not fully passed.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "require_smoke_test": bool(request.get("require_smoke_test")),
        "smoke_verdict": smoke_verdict,
        "scenario_count": len(scenarios),
        "result_count": len(records),
        "passed_scenario_count": len(passed_ids),
        "missing_required_scenarios": missing_required,
        "scenarios": scenarios,
        "result_records": records,
        "findings": findings,
        "policy": [
            "Smoke test planning is static and plan-only; it never runs package code locally.",
            "Smoke results must be supplied as external observed evidence from the approved execution environment.",
            "A passing smoke test confirms builder and child-skill package shape, not scientific correctness.",
        ],
    }
