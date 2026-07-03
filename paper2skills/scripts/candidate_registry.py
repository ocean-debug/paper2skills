"""Candidate-version registry for child-skill build outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, slugify
from constants import BUILDER_VERSION, REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


def build_candidate_registry(
    request: dict[str, Any],
    draft_candidates: dict[str, Any],
    review_result: dict[str, Any],
    child_skill_dir: Path,
    lint_report: dict[str, Any],
    publish_gate: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    method_name = str(request.get("method_name") or request.get("package_name"))
    files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    candidate = (draft_candidates.get("candidates") or [{}])[0]
    if draft_candidates.get("candidate_count") != 1:
        findings.append(
            {
                "severity": "error",
                "code": "unexpected_candidate_count",
                "message": "Candidate registry expects exactly one child-skill candidate per package.",
            }
        )
    if not candidate.get("candidate_id"):
        findings.append(
            {
                "severity": "error",
                "code": "missing_candidate_id",
                "message": "Candidate registry cannot create a stable version without a candidate_id.",
            }
        )
    version = {
        "version_id": f"candidate:{slugify(method_name)}:v001",
        "candidate_id": candidate.get("candidate_id"),
        "child_skill_path": str(child_skill_dir),
        "status": publish_gate.get("status"),
        "lint_status": lint_report.get("status"),
        "review_status": review_result.get("status"),
        "review_iteration_count": len(review_result.get("iterations", [])),
        "task_count": candidate.get("task_count", 0),
        "files": files,
        "blocking_findings": [
            finding for finding in publish_gate.get("findings", []) if finding.get("severity") == "error"
        ],
    }
    has_errors = any(finding.get("severity") == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": method_name,
        "status": "fail" if has_errors else "pass",
        "active_version_id": version["version_id"],
        "versions": [version],
        "findings": findings,
        "policy": [
            "Candidate registry is the release identity source for the generated child-skill candidate.",
            "Candidate versions record build outputs and gates without duplicating full child-skill text.",
            "A publishable candidate still remains source_grounded unless task traces explicitly verify execution.",
        ],
    }
