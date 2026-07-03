"""Audit review finding remediation across deterministic review iterations."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REMEDIATED = "remediated_by_patch"
FINAL_UNRESOLVED = "final_unresolved"
SUPERSEDED = "superseded_or_cleared"
GATE_ACCEPTED = "gate_accepted"


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        item["iteration"] = iteration
    findings.append(item)


def finding_code(finding: dict[str, Any]) -> str:
    return str(finding.get("code") or finding.get("check") or "uncoded")


def finding_key(finding: dict[str, Any]) -> str:
    task_type = str(finding.get("task_type") or "")
    return f"{finding_code(finding)}::{task_type}"


def patch_codes(iteration: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    patch = iteration.get("patch") or {}
    for action in patch.get("actions", []):
        for code in action.get("finding_codes", []) or []:
            codes.add(str(code))
    return codes


def final_finding_keys(review_result: dict[str, Any]) -> set[str]:
    return {
        finding_key(finding)
        for finding in review_result.get("final_findings", [])
        if finding.get("severity") in {"error", "warning"}
    }


def status_for_finding(
    finding: dict[str, Any],
    codes_patched: set[str],
    unresolved_keys: set[str],
    gate_passed: bool,
) -> str:
    code = finding_code(finding)
    if code in codes_patched:
        return REMEDIATED
    if gate_passed:
        return GATE_ACCEPTED
    if finding_key(finding) in unresolved_keys:
        return FINAL_UNRESOLVED
    return SUPERSEDED


def remediation_records(review_result: dict[str, Any]) -> list[dict[str, Any]]:
    unresolved_keys = final_finding_keys(review_result)
    records: list[dict[str, Any]] = []
    for iteration in review_result.get("iterations", []):
        codes_patched = patch_codes(iteration)
        gate = next((state for state in iteration.get("states", []) if state.get("role") == "gate"), {})
        gate_passed = bool(gate.get("passed"))
        for finding in iteration.get("findings", []):
            if finding.get("severity") == "info":
                continue
            record_status = status_for_finding(finding, codes_patched, unresolved_keys, gate_passed)
            records.append(
                {
                    "iteration": iteration.get("iteration"),
                    "severity": finding.get("severity"),
                    "code": finding_code(finding),
                    "task_type": finding.get("task_type"),
                    "status": record_status,
                    "patched_in_iteration": finding_code(finding) in codes_patched,
                    "present_in_final_findings": finding_key(finding) in unresolved_keys,
                    "message": finding.get("message"),
                }
            )
    return records


def audit_patch_traces(
    review_result: dict[str, Any],
    patch_application: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    if patch_application.get("status") == "fail":
        add_finding(findings, "error", "patch_application_failed", "Patch application must pass before remediation audit.")

    iteration_codes = {
        item.get("iteration"): {finding_code(finding) for finding in item.get("findings", [])}
        for item in review_result.get("iterations", [])
    }
    for record in patch_application.get("records", []):
        iteration_id = record.get("iteration")
        known_codes = iteration_codes.get(iteration_id, set())
        for action in record.get("actions", []):
            action_codes = {str(code) for code in action.get("finding_codes", []) or []}
            if record.get("changed") and not action_codes:
                add_finding(
                    findings,
                    "error",
                    "patch_action_without_finding_codes",
                    "Changed review patch action must cite same-iteration finding codes.",
                    iteration_id,
                )
            missing = sorted(code for code in action_codes if code not in known_codes)
            if missing:
                add_finding(
                    findings,
                    "error",
                    "patch_action_unknown_finding_code",
                    "Review patch action cites finding codes absent from the same iteration.",
                    iteration_id,
                )


def build_review_remediation_audit(
    request: dict[str, Any],
    review_result: dict[str, Any],
    patch_application: dict[str, Any],
) -> dict[str, Any]:
    """Build a machine-checkable account of review finding remediation."""
    findings: list[dict[str, Any]] = []
    records = remediation_records(review_result)
    audit_patch_traces(review_result, patch_application, findings)

    final_errors = [
        finding
        for finding in review_result.get("final_findings", [])
        if finding.get("severity") == "error"
    ]
    for finding in final_errors:
        add_finding(
            findings,
            "error",
            "unresolved_final_review_error",
            "A blocking review finding remains unresolved after the review loop.",
        )
    if review_result.get("status") == "passed" and final_errors:
        add_finding(
            findings,
            "error",
            "passed_review_with_final_errors",
            "Review result cannot pass while final blocking findings remain.",
        )

    counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "stop_reason": review_result.get("stop_reason"),
        "iteration_count": len(review_result.get("iterations", [])),
        "record_count": len(records),
        "remediation_status_counts": dict(sorted(counts.items())),
        "final_error_count": len(final_errors),
        "records": records,
        "findings": findings,
        "policy": [
            "Every non-info review finding is accounted for as patched, cleared, accepted by a passing gate, or still unresolved.",
            "Changed patch actions must cite finding codes from the same review iteration.",
            "Final blocking review findings fail this audit and block publication through downstream gates.",
        ],
    }
