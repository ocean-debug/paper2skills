"""Audit builder version and schema-version consistency across core artifacts."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import BUILDER_VERSION, SCHEMA_VERSION


REQUIRED_VERSIONED_ARTIFACTS = [
    "request",
    "request_audit",
    "request_fingerprint",
    "external_result_contracts",
    "builder_runtime_audit",
    "agent_metadata_audit",
    "public_origin_audit",
    "module_inventory_audit",
    "builder_baseline_audit",
    "skill_package_audit",
    "request_template_audit",
    "child_package_purity_audit",
    "source_grounding",
    "source_fetch_boundary_audit",
    "discovery_resolution_audit",
    "source_manifest",
    "evidence_claim_taxonomy_audit",
    "key_api_coverage_audit",
    "eval_leakage_audit",
    "agent_rollout_result_judge",
    "e2e_acceptance",
    "smoke_test_plan",
    "completion_evidence_audit",
    "acceptance_handoff",
    "protocol_compliance_audit",
    "execution_replay_orchestrator",
    "task_catalog",
    "task_type_router",
    "biological_claim_boundary_audit",
    "review_summary",
    "draft_candidates",
    "candidate_registry",
    "candidate_selection_audit",
    "candidate_promotion_audit",
    "release_package",
    "final_candidate_audit",
    "candidate_evolution_audit",
    "codex_publish_adapter",
    "install_readiness",
    "publish_manifest_audit",
    "skill_spec",
    "publish_manifest",
]

REQUIRED_BUILDER_VERSION_ARTIFACTS = [
    "builder_runtime_audit",
    "builder_baseline_audit",
    "candidate_registry",
    "release_package",
    "skill_spec",
    "publish_manifest",
]


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


def build_builder_version_audit(
    request: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Return a static version consistency report for core build artifacts."""
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for name in REQUIRED_VERSIONED_ARTIFACTS:
        artifact = artifacts.get(name)
        if artifact is None:
            add_finding(
                findings,
                "error",
                "missing_versioned_artifact",
                "Required versioned artifact is missing.",
                name,
            )
            records.append(
                {
                    "artifact": name,
                    "present": False,
                    "schema_version": None,
                    "schema_version_matches": False,
                    "builder_version": None,
                    "builder_version_matches": None,
                }
            )
            continue
        schema_version = artifact.get("schema_version")
        builder_version = artifact.get("builder_version")
        schema_matches = schema_version == SCHEMA_VERSION
        if not schema_matches:
            add_finding(
                findings,
                "error",
                "schema_version_mismatch",
                "Artifact schema_version does not match the builder schema version.",
                name,
            )
        builder_matches: bool | None
        if builder_version is None:
            builder_matches = None
            if name in REQUIRED_BUILDER_VERSION_ARTIFACTS:
                add_finding(
                    findings,
                    "error",
                    "missing_builder_version",
                    "Release-facing artifact is missing builder_version.",
                    name,
                )
        else:
            builder_matches = builder_version == BUILDER_VERSION
            if not builder_matches:
                add_finding(
                    findings,
                    "error",
                    "builder_version_mismatch",
                    "Artifact builder_version does not match the active builder version.",
                    name,
                )
        records.append(
            {
                "artifact": name,
                "present": True,
                "schema_version": schema_version,
                "schema_version_matches": schema_matches,
                "builder_version": builder_version,
                "builder_version_matches": builder_matches,
            }
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "required_artifacts": REQUIRED_VERSIONED_ARTIFACTS,
        "required_builder_version_artifacts": REQUIRED_BUILDER_VERSION_ARTIFACTS,
        "record_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Builder version audit is static and does not execute package code.",
            "schema_version identifies artifact shape; builder_version identifies the builder release that produced release-facing metadata.",
            "Core artifacts must share the active schema version before publish and completion gates can be trusted.",
        ],
    }
