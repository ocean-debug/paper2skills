"""Audit rubric scoring details and grounding signals."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION
from review_rubric import RUBRIC_ITEMS


ALLOWED_STATUSES = {"pass", "pass_with_warning", "warn", "fail"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    scope: str,
    item: str | None = None,
) -> None:
    finding: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
        "scope": scope,
    }
    if item:
        finding["item"] = item
    findings.append(finding)


def score_scope(name: str, score_record: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    item_results = score_record.get("item_results", [])
    result_by_item = {str(item.get("item")): item for item in item_results if item.get("item")}
    expected_items = set(RUBRIC_ITEMS)
    observed_items = set(result_by_item)

    missing_items = sorted(expected_items.difference(observed_items))
    extra_items = sorted(observed_items.difference(expected_items))
    for item in missing_items:
        add_finding(
            findings,
            "error",
            "rubric_item_missing",
            "Rubric score record is missing a required item result.",
            name,
            item,
        )
    for item in extra_items:
        add_finding(
            findings,
            "error",
            "unknown_rubric_item",
            "Rubric score record contains an unknown item.",
            name,
            item,
        )

    point_sum = 0
    supported_point_count = 0
    for item_name in sorted(observed_items.intersection(expected_items)):
        result = result_by_item[item_name]
        status = str(result.get("status") or "")
        points = result.get("points")
        evidence = result.get("evidence", [])
        if status not in ALLOWED_STATUSES:
            add_finding(
                findings,
                "error",
                "invalid_rubric_item_status",
                "Rubric item status is not recognized.",
                name,
                item_name,
            )
        if not isinstance(points, int) or points not in {0, 1}:
            add_finding(
                findings,
                "error",
                "invalid_rubric_item_points",
                "Rubric item points must be 0 or 1.",
                name,
                item_name,
            )
            continue
        point_sum += points
        if points and not evidence:
            add_finding(
                findings,
                "error",
                "rubric_points_without_grounding",
                "Rubric item received points without a grounding signal.",
                name,
                item_name,
            )
        if points and evidence:
            supported_point_count += 1
        if status == "fail" and points:
            add_finding(
                findings,
                "error",
                "failed_rubric_item_has_points",
                "Failed rubric item must not receive points.",
                name,
                item_name,
            )
        if status == "warn" and points:
            add_finding(
                findings,
                "error",
                "warning_rubric_item_has_points",
                "Warning rubric item should use pass_with_warning when it still receives points.",
                name,
                item_name,
            )

    score = score_record.get("score")
    total = score_record.get("total")
    score_ratio = score_record.get("score_ratio")
    if score != point_sum:
        add_finding(
            findings,
            "error",
            "rubric_score_sum_mismatch",
            "Rubric score does not equal the sum of item points.",
            name,
        )
    if total != len(RUBRIC_ITEMS):
        add_finding(
            findings,
            "error",
            "rubric_total_mismatch",
            "Rubric total does not equal the configured item count.",
            name,
        )
    if isinstance(score, (int, float)) and isinstance(total, (int, float)) and total:
        expected_ratio = score / total
        if not isinstance(score_ratio, (int, float)) or abs(score_ratio - expected_ratio) > 0.000001:
            add_finding(
                findings,
                "error",
                "rubric_score_ratio_mismatch",
                "Rubric score_ratio does not match score / total.",
                name,
            )

    return {
        "scope": name,
        "score": score,
        "total": total,
        "score_ratio": score_ratio,
        "item_count": len(item_results),
        "supported_point_count": supported_point_count,
        "missing_items": missing_items,
        "extra_items": extra_items,
    }


def build_rubric_grounding_audit(
    request: dict[str, Any],
    review_result: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    records.append(score_scope("final_score", review_result.get("final_score", {}), findings))
    for iteration in review_result.get("iterations", []):
        critic = next((state for state in iteration.get("states", []) if state.get("role") == "critic"), {})
        score_record = {
            "score": iteration.get("score"),
            "total": iteration.get("total"),
            "score_ratio": iteration.get("score_ratio"),
            "item_results": critic.get("item_results", []),
        }
        records.append(score_scope(f"iteration:{iteration.get('iteration')}", score_record, findings))

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "review_status": review_result.get("status"),
        "rubric_items": RUBRIC_ITEMS,
        "record_count": len(records),
        "records": records,
        "findings": findings,
        "policy": [
            "Rubric score records must expose per-item results.",
            "Every awarded point must have a grounding signal and the total score must equal the item-point sum.",
        ],
    }
