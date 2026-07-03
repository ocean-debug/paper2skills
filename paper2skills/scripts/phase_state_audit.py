"""Audit phase ledger structure and output ownership."""

from __future__ import annotations

from collections import Counter
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    phase: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if phase:
        item["phase"] = phase
    findings.append(item)


def output_artifact_name(output: str) -> str | None:
    if not output.endswith(".yaml"):
        return None
    return output[:-5]


def build_phase_state_audit(
    request: dict[str, Any],
    phase_state: dict[str, Any],
    artifact_contracts: dict[str, Any],
) -> dict[str, Any]:
    """Audit the recorded build phase ledger without executing build steps."""
    findings: list[dict[str, Any]] = []
    phases = phase_state.get("phases", [])
    contracts = set((artifact_contracts.get("contracts") or {}).keys())
    phase_names = [str(phase.get("name") or "") for phase in phases]
    name_counts = Counter(phase_names)
    output_owners: dict[str, list[str]] = {}
    records: list[dict[str, Any]] = []

    for phase in phases:
        name = str(phase.get("name") or "")
        status = str(phase.get("status") or "")
        inputs = [str(item) for item in phase.get("inputs", [])]
        outputs = [str(item) for item in phase.get("outputs", [])]
        gates = [str(item) for item in phase.get("gates", [])]
        notes = [str(item) for item in phase.get("notes", [])]
        if not name:
            add_finding(findings, "error", "phase_missing_name", "Phase record is missing a name.")
        if status not in {"completed", "skipped"}:
            add_finding(findings, "error", "phase_invalid_status", "Phase status must be completed or skipped.", name)
        if status == "completed" and not outputs:
            add_finding(findings, "warning", "completed_phase_without_outputs", "Completed phase records no outputs.", name)
        if status == "completed" and not gates:
            add_finding(findings, "error", "completed_phase_without_gates", "Completed phase must declare gates.", name)
        if name_counts[name] > 1 and name:
            add_finding(findings, "error", "duplicate_phase_name", "Phase name appears more than once.", name)
        for output in outputs:
            output_owners.setdefault(output, []).append(name)
            artifact_name = output_artifact_name(output)
            if artifact_name and artifact_name not in contracts:
                add_finding(findings, "error", "phase_output_missing_artifact_contract", "Phase output has no artifact contract.", name)
        records.append(
            {
                "phase": name,
                "status": status,
                "input_count": len(inputs),
                "output_count": len(outputs),
                "gate_count": len(gates),
                "note_count": len(notes),
            }
        )

    for output, owners in sorted(output_owners.items()):
        if len(owners) > 1:
            add_finding(
                findings,
                "error",
                "phase_output_has_multiple_owners",
                f"Output {output} is declared by multiple phases: {', '.join(owners)}.",
            )

    if not phases:
        add_finding(findings, "error", "missing_phase_records", "Phase ledger has no phase records.")
    if phase_state.get("schema_version") != SCHEMA_VERSION:
        add_finding(findings, "error", "phase_state_schema_mismatch", "Phase ledger schema_version does not match builder schema.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "phase_count": len(phases),
        "unique_phase_count": len(set(phase_names)),
        "output_count": len(output_owners),
        "contract_count": len(contracts),
        "records": records,
        "findings": findings,
        "policy": [
            "Phase state audit checks the run ledger only; it does not execute build phases.",
            "Each completed phase must declare gates, and YAML phase outputs must have artifact contracts.",
            "Each output should have a single owning phase so downstream closure and timeline audits remain unambiguous.",
        ],
    }
