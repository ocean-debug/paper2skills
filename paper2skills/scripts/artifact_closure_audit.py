"""Audit artifact contract, write-plan, and phase-output closure."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    artifact: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if artifact:
        item["artifact"] = artifact
    findings.append(item)


def phase_outputs(phase_state: dict[str, Any]) -> set[str]:
    outputs: set[str] = set()
    for phase in phase_state.get("phases", []):
        for output in phase.get("outputs", []):
            outputs.add(str(output))
    return outputs


def build_artifact_closure_audit(
    request: dict[str, Any],
    required_top_level_artifacts: list[str],
    pre_publish_artifacts: list[str],
    artifact_contracts: dict[str, Any],
    phase_state: dict[str, Any],
    available_artifacts: dict[str, Any],
    planned_write_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """Check that required artifacts are contracted, planned, and phase-visible."""
    findings: list[dict[str, Any]] = []
    required = list(required_top_level_artifacts)
    pre_publish = list(pre_publish_artifacts)
    planned = set(planned_write_artifacts or required)
    contracts = set((artifact_contracts.get("contracts") or {}).keys())
    outputs = phase_outputs(phase_state)
    available = set(available_artifacts.keys())

    for artifact in required:
        if artifact not in contracts:
            add_finding(
                findings,
                "error",
                "required_artifact_missing_contract",
                "Required artifact has no artifact contract.",
                artifact,
            )
        if artifact not in planned:
            add_finding(
                findings,
                "error",
                "required_artifact_not_planned_for_write",
                "Required artifact is not listed in the run write plan.",
                artifact,
            )
        if artifact in available and f"{artifact}.yaml" not in outputs:
            add_finding(
                findings,
                "error",
                "available_artifact_without_phase_output",
                "Available required artifact is not recorded as a phase output.",
                artifact,
            )

    for artifact in pre_publish:
        if artifact not in required:
            add_finding(
                findings,
                "error",
                "pre_publish_artifact_not_required",
                "Pre-publish artifact must also be a required top-level artifact.",
                artifact,
            )
        if artifact not in available:
            add_finding(
                findings,
                "error",
                "pre_publish_artifact_not_available",
                "Pre-publish artifact was not available when closure was audited.",
                artifact,
            )

    for artifact in sorted(available.difference(contracts)):
        add_finding(
            findings,
            "error",
            "available_artifact_missing_contract",
            "Available artifact has no artifact contract.",
            artifact,
        )

    records = [
        {
            "artifact": artifact,
            "required": artifact in required,
            "pre_publish": artifact in pre_publish,
            "has_contract": artifact in contracts,
            "planned_write": artifact in planned,
            "available_at_audit": artifact in available,
            "phase_output_recorded": f"{artifact}.yaml" in outputs,
        }
        for artifact in required
    ]
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "required_artifact_count": len(required),
        "pre_publish_artifact_count": len(pre_publish),
        "contract_count": len(contracts),
        "planned_write_count": len(planned),
        "available_artifact_count": len(available),
        "phase_output_count": len(outputs),
        "records": records,
        "findings": findings,
        "policy": [
            "Every required top-level artifact must have a declared artifact contract.",
            "Every required top-level artifact must be listed in the run write plan.",
            "Every available required top-level artifact must be recorded as a phase output.",
            "Every pre-publish artifact must be available before publish gating.",
            "Closure audit is static and never executes package code, installs dependencies, or mutates child skills.",
        ],
    }
