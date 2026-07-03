"""Release package manifest for generated child skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from action_policy import REUSE_EXISTING, UPDATE_EXISTING, is_publish_status_acceptable
from common import now_utc
from constants import BUILDER_VERSION, REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def build_release_package(
    request: dict[str, Any],
    child_skill_dir: Path,
    publish_gate: dict[str, Any],
    candidate_registry: dict[str, Any],
    skill_update_plan: dict[str, Any],
    candidate_promotion_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    required_files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    files = []
    for rel in required_files:
        path = child_skill_dir / rel
        files.append(
            {
                "path": rel,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else None,
            }
        )
    recommended_action = skill_update_plan.get("recommended_action") or publish_gate.get("recommended_action")
    if recommended_action == REUSE_EXISTING:
        install_plan = [
            "Do not copy the generated candidate as a new child skill.",
            "Use the existing child skill identified by skill_update_plan.yaml.",
            "Review the generated candidate only as evidence for future manual maintenance.",
            "Do not copy build-run artifacts unless the user explicitly wants provenance records.",
        ]
    elif recommended_action == UPDATE_EXISTING:
        install_plan = [
            "Review skill_update_plan.yaml before changing the existing child skill.",
            "Merge the generated candidate files into the target existing skill path instead of copying a duplicate folder.",
            "Preserve existing task_type contracts unless the new evidence explicitly supersedes them.",
            "Do not copy build-run artifacts unless the user explicitly wants provenance records.",
        ]
    else:
        install_plan = [
            "Copy the child skill directory as one folder into the target Codex skills directory.",
            "Do not copy build-run artifacts unless the user explicitly wants provenance records.",
            "Keep execution traces outside the public child skill unless summarized in references/evidence.md.",
        ]
    candidate_promotion_audit = candidate_promotion_audit or {}
    has_target = bool(skill_update_plan.get("target_existing_skill_path"))
    ready = (
        is_publish_status_acceptable(recommended_action, publish_gate.get("status"))
        and candidate_promotion_audit.get("status", "pass") == "pass"
        and (recommended_action != REUSE_EXISTING or has_target)
        and (recommended_action != UPDATE_EXISTING or has_target)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "child_skill_path": str(child_skill_dir),
        "status": "ready" if ready else "blocked",
        "publish_gate_status": publish_gate.get("status"),
        "candidate_promotion_audit_status": candidate_promotion_audit.get("status"),
        "recommended_action": recommended_action,
        "action_publish_status_accepted": is_publish_status_acceptable(recommended_action, publish_gate.get("status")),
        "candidate_version": candidate_registry.get("active_version_id"),
        "target_existing_skill_path": skill_update_plan.get("target_existing_skill_path"),
        "install_target": "Codex skills directory selected by the user",
        "run_manifest_path": "run_manifest.yaml",
        "files": files,
        "install_plan": install_plan,
        "provenance_review": [
            "Review run_manifest.yaml before copying the child skill to confirm generated file hashes.",
            "Do not include downloaded sources or long traces in the public child skill package.",
        ],
        "policy": "Release package is a manifest only; it does not copy files or modify the user's skills directory.",
    }
