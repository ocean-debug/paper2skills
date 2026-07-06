"""Plan-only Codex publish adapter for generated child skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


REQUIRED_FILES = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
VALID_ACTIONS = {"create_new", "update_existing", "reuse_existing"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
) -> None:
    findings.append({"severity": severity, "code": code, "message": message})


def build_publish_steps(action: str, release_package: dict[str, Any]) -> list[dict[str, Any]]:
    child_skill_path = release_package.get("child_skill_path")
    target_existing_skill_path = release_package.get("target_existing_skill_path")
    if action == "reuse_existing":
        return [
            {
                "step": "reuse_existing_skill",
                "mode": "manual",
                "description": "Use the existing child skill; do not copy the generated candidate as a duplicate.",
                "source": target_existing_skill_path or "skill_update_plan target",
            }
        ]
    if action == "update_existing":
        return [
            {
                "step": "review_manual_merge",
                "mode": "manual",
                "description": "Review task_type deltas and merge generated files into the existing skill path.",
                "source": child_skill_path,
                "target": target_existing_skill_path,
            },
            {
                "step": "preserve_existing_contracts",
                "mode": "manual",
                "description": "Preserve existing task_type contracts unless newer evidence explicitly supersedes them.",
                "target": target_existing_skill_path,
            },
        ]
    return [
        {
            "step": "copy_child_skill_directory",
            "mode": "manual",
            "description": "Copy the generated child skill directory into the Codex skills directory selected by the user.",
            "source": child_skill_path,
            "target": "user-selected Codex skills directory",
        },
        {
            "step": "exclude_build_artifacts",
            "mode": "manual",
            "description": "Copy only the child skill folder contents; do not copy run artifacts or downloaded sources.",
            "source": child_skill_path,
        },
    ]


def build_codex_publish_adapter(
    request: dict[str, Any],
    release_package: dict[str, Any],
    skill_update_plan: dict[str, Any],
    candidate_promotion_audit: dict[str, Any],
    final_candidate_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    final_candidate_audit = final_candidate_audit or {}
    action = str(release_package.get("recommended_action") or skill_update_plan.get("recommended_action") or "")
    files = {str(item.get("path")): item for item in release_package.get("files", []) if item.get("path")}

    if action not in VALID_ACTIONS:
        add_finding(findings, "error", "invalid_publish_action", "Codex publish adapter received an unknown release action.")
    if release_package.get("status") != "ready":
        add_finding(findings, "error", "release_package_not_ready", "Release package must be ready before publish adapter planning.")
    if candidate_promotion_audit.get("status") != "pass":
        add_finding(findings, "error", "candidate_promotion_not_passed", "Candidate promotion audit must pass before publish adapter planning.")
    if final_candidate_audit.get("status") != "pass":
        add_finding(findings, "error", "final_candidate_audit_not_passed", "Final candidate audit must pass before publish adapter planning.")
    if skill_update_plan.get("recommended_action") != action:
        add_finding(findings, "error", "publish_action_mismatch", "Publish adapter action must match skill_update_plan recommended_action.")

    for rel in REQUIRED_FILES:
        record = files.get(rel)
        if not record or not record.get("exists"):
            add_finding(findings, "error", "missing_publish_file", f"Required child-skill file is missing from release package: {rel}.")
    if action == "update_existing" and not release_package.get("target_existing_skill_path"):
        add_finding(findings, "error", "update_without_target", "Update actions require a target existing skill path.")
    if action == "reuse_existing" and release_package.get("child_skill_path"):
        add_finding(findings, "warning", "reuse_has_generated_candidate", "Reuse action should treat generated candidate as review evidence only.")

    child_skill_path = release_package.get("child_skill_path")
    package_name = Path(str(child_skill_path)).name if child_skill_path else request.get("package_name")
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "plan_only": True,
        "target_agent": "codex",
        "adapter_name": "codex_skill_publish",
        "recommended_action": action,
        "child_skill_path": child_skill_path,
        "child_skill_folder_name": package_name,
        "target_existing_skill_path": release_package.get("target_existing_skill_path"),
        "final_candidate_audit_status": final_candidate_audit.get("status"),
        "required_files": REQUIRED_FILES,
        "publish_steps": build_publish_steps(action, release_package),
        "findings": findings,
        "policy": [
            "Codex publish adapter is plan-only; it does not copy files, install skills, or modify the user's Codex directory.",
            "Reuse actions must not publish a duplicate generated child skill.",
            "Update actions require manual merge review into the target existing child skill path.",
            "Create actions copy only the public child skill files, not build-run artifacts.",
        ],
    }
