"""Safety audit for deterministic review patch actions."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


ALLOWED_PATCH_ARTIFACTS = {"task_catalog", "task_type_router"}
FORBIDDEN_ACTION_TERMS = {
    "shell",
    "command",
    "execute",
    "install",
    "pip",
    "conda",
    "download",
    "delete",
    "remove file",
    "write file",
    "copy file",
    "network",
}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    iteration: int | None = None,
) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if iteration is not None:
        finding["iteration"] = iteration
    findings.append(finding)


def iter_actions(review_result: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for iteration in review_result.get("iterations", []):
        for action in (iteration.get("patch") or {}).get("actions", []):
            records.append(
                {
                    "iteration": iteration.get("iteration"),
                    "artifact": action.get("artifact"),
                    "task_type": action.get("task_type"),
                    "action": action.get("action"),
                    "raw": action,
                }
            )
    return records


def audit_patch_safety(
    request: dict[str, Any],
    review_result: dict[str, Any],
    review_optimizer_state: dict[str, Any],
) -> dict[str, Any]:
    """Check that review patches stay inside deterministic artifact boundaries."""
    findings: list[dict[str, Any]] = []
    records = iter_actions(review_result)
    for record in records:
        iteration = int(record.get("iteration") or 0)
        artifact = str(record.get("artifact") or "")
        action_text = str(record.get("action") or "").lower()
        raw = record.get("raw") or {}

        if artifact not in ALLOWED_PATCH_ARTIFACTS:
            add_finding(
                findings,
                "error",
                "patch_artifact_not_allowed",
                "Review patch action targets an artifact outside the allowed deterministic set.",
                iteration,
            )
        if any(key in raw for key in ("path", "file", "command", "cmd", "shell", "url")):
            add_finding(
                findings,
                "error",
                "patch_action_contains_external_target",
                "Review patch action must not contain file paths, commands, shell snippets, or URLs.",
                iteration,
            )
        if any(term in action_text for term in FORBIDDEN_ACTION_TERMS):
            add_finding(
                findings,
                "error",
                "patch_action_contains_forbidden_term",
                "Review patch action describes execution, installation, network, or file mutation behavior.",
                iteration,
            )

    if review_optimizer_state.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "optimizer_state_failed",
            "Review optimizer state failed; patch safety cannot pass.",
        )
    if review_optimizer_state.get("strict_improvement_gate") is not True:
        add_finding(
            findings,
            "error",
            "missing_strict_improvement_gate",
            "Review optimizer state must declare a strict improvement gate.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "optimizer_state_status": review_optimizer_state.get("status"),
        "allowed_patch_artifacts": sorted(ALLOWED_PATCH_ARTIFACTS),
        "patch_action_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Review patches are deterministic edits to in-memory build artifacts only.",
            "Patch records must not contain shell commands, network actions, package installation, file paths, or file mutation instructions.",
            "Task catalog and task router are the only patchable artifacts in the current builder loop.",
        ],
    }
