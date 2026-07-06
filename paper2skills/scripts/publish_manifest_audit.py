"""Audit publish manifest consistency with discovery and release decisions."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def build_publish_manifest_audit(
    request: dict[str, Any],
    publish_manifest: dict[str, Any],
    publish_gate: dict[str, Any],
    release_package: dict[str, Any],
    skill_update_plan: dict[str, Any],
    install_readiness: dict[str, Any],
    codex_publish_adapter: dict[str, Any] | None = None,
    final_candidate_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    update_action = skill_update_plan.get("recommended_action")
    manifest_action = publish_manifest.get("recommended_action")
    release_action = release_package.get("recommended_action")

    if manifest_action != publish_gate.get("recommended_action"):
        add_finding(
            findings,
            "error",
            "manifest_gate_action_mismatch",
            "Publish manifest recommended_action must mirror publish_gate.",
        )
    if release_action != update_action:
        add_finding(
            findings,
            "error",
            "release_update_action_mismatch",
            "Release package recommended_action must mirror skill_update_plan.",
        )
    if publish_manifest.get("release_recommended_action") != release_action:
        add_finding(
            findings,
            "error",
            "manifest_release_action_mismatch",
            "Publish manifest must record the release package recommended_action.",
        )
    if publish_manifest.get("skill_update_recommended_action") != update_action:
        add_finding(
            findings,
            "error",
            "manifest_update_action_mismatch",
            "Publish manifest must record the skill_update_plan recommended_action.",
        )
    if update_action == "update_existing" and not release_package.get("target_existing_skill_path"):
        add_finding(
            findings,
            "error",
            "update_without_release_target",
            "Update release package must include target_existing_skill_path.",
        )
    if update_action == "update_existing" and not publish_manifest.get("target_existing_skill_path"):
        add_finding(
            findings,
            "error",
            "update_without_manifest_target",
            "Update publish manifest must include target_existing_skill_path.",
        )
    if update_action == "reuse_existing" and publish_manifest.get("status") == "publishable":
        add_finding(
            findings,
            "error",
            "reuse_marked_publishable",
            "Reuse recommendations must not publish a duplicate child skill.",
        )
    if publish_manifest.get("install_readiness_status") != install_readiness.get("status"):
        add_finding(
            findings,
            "error",
            "install_readiness_status_mismatch",
            "Publish manifest must record the install_readiness status.",
        )
    final_candidate_audit = final_candidate_audit or {}
    if final_candidate_audit.get("status") != "pass":
        add_finding(
            findings,
            "error",
            "final_candidate_audit_not_passed",
            "Final candidate audit must pass.",
        )
    codex_publish_adapter = codex_publish_adapter or {}
    if codex_publish_adapter.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "codex_publish_adapter_failed",
            "Codex publish adapter failed.",
        )
    if codex_publish_adapter:
        if codex_publish_adapter.get("recommended_action") != update_action:
            add_finding(
                findings,
                "error",
                "codex_adapter_action_mismatch",
                "Codex publish adapter action must mirror skill_update_plan.",
            )
        if publish_manifest.get("codex_publish_adapter_status") != codex_publish_adapter.get("status"):
            add_finding(
                findings,
                "error",
                "codex_adapter_status_mismatch",
                "Publish manifest must record the Codex publish adapter status.",
            )
    if not publish_manifest.get("run_manifest_path"):
        add_finding(
            findings,
            "error",
            "missing_run_manifest_path",
            "Publish manifest must point to run_manifest.yaml.",
        )
    if not publish_manifest.get("output_retention_path"):
        add_finding(
            findings,
            "error",
            "missing_output_retention_path",
            "Publish manifest must point to the retained output_retention.yaml lifecycle artifact.",
        )
    if not publish_manifest.get("generation_process_doc"):
        add_finding(
            findings,
            "error",
            "missing_generation_process_doc",
            "Publish manifest must point to the human-readable generation process document.",
        )
    if publish_manifest.get("output_retention_status") not in {None, "pass"}:
        add_finding(
            findings,
            "error",
            "output_retention_failed",
            "Publish manifest records a non-passing output retention status.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "publish_status": publish_manifest.get("status"),
        "publish_gate_status": publish_gate.get("status"),
        "install_readiness_status": install_readiness.get("status"),
        "codex_publish_adapter_status": codex_publish_adapter.get("status"),
        "final_candidate_audit_status": final_candidate_audit.get("status"),
        "skill_update_recommended_action": update_action,
        "release_recommended_action": release_action,
        "manifest_recommended_action": manifest_action,
        "manifest_release_recommended_action": publish_manifest.get("release_recommended_action"),
        "manifest_skill_update_recommended_action": publish_manifest.get("skill_update_recommended_action"),
        "target_existing_skill_path": release_package.get("target_existing_skill_path"),
        "manifest_target_existing_skill_path": publish_manifest.get("target_existing_skill_path"),
        "run_manifest_path": publish_manifest.get("run_manifest_path"),
        "output_retention_path": publish_manifest.get("output_retention_path"),
        "output_retention_status": publish_manifest.get("output_retention_status"),
        "generation_process_doc": publish_manifest.get("generation_process_doc"),
        "findings": findings,
        "policy": [
            "Publish manifest is an audit record, not an installer.",
            "Codex publish adapter must stay plan-only and mirror the reuse/update/create decision.",
            "Final candidate audit must pass before publish metadata is trusted.",
            "Reuse must not produce a duplicate publishable child skill.",
            "Update actions must preserve the target existing skill path for manual merge review.",
        ],
    }
