"""Decision log for capability-to-task_type partitioning."""

from __future__ import annotations

from typing import Any

from common import as_list, lower_join, now_utc, slugify
from constants import SCHEMA_VERSION, TASK_HEURISTICS
from task_partition_audit import TUTORIAL_SPLIT_TERMS


def requested_candidates(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate": slugify(str(item), "task"),
            "source": "requested_task_types",
            "evidence_ref": None,
            "reason": "Explicitly requested in build request.",
        }
        for item in as_list(request.get("requested_task_types"))
    ]


def heuristic_candidates(request: dict[str, Any], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = lower_join(
        [request.get("package_name"), request.get("method_name"), request.get("repo_url")]
        + [source.get("uri") for source in sources]
    )
    records = []
    for task_type, needles in TASK_HEURISTICS.items():
        matched = [needle for needle in needles if needle in text]
        if matched:
            records.append(
                {
                    "candidate": task_type,
                    "source": "heuristic",
                    "evidence_ref": None,
                    "reason": "Matched package/source text: " + ", ".join(matched[:6]),
                }
            )
    return records


def evidence_candidates(evidence_cards: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for card in evidence_cards.get("cards", []):
        for task_type in card.get("task_type_candidates", []):
            records.append(
                {
                    "candidate": str(task_type),
                    "source": "evidence_card",
                    "evidence_ref": card.get("evidence_card_id"),
                    "reason": f"Evidence card claim_type={card.get('claim_type')}",
                }
            )
    return records


def tutorial_candidates(tutorial_catalog: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for tutorial in tutorial_catalog.get("tutorials", []):
        source_path = str(tutorial.get("source_path") or tutorial.get("tutorial_id") or "")
        candidate = slugify(source_path, "tutorial")
        if candidate:
            records.append(
                {
                    "candidate": candidate,
                    "source": "tutorial_shape",
                    "evidence_ref": tutorial.get("source_evidence_id"),
                    "reason": "Tutorial/example file is evidence, not a standalone child skill or task_type by itself.",
                }
            )
    return records


def is_tutorial_shaped(candidate: str) -> bool:
    tokens = set(candidate.lower().replace("-", "_").split("_"))
    return bool(tokens.intersection(TUTORIAL_SPLIT_TERMS))


def build_task_partition_decision_log(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
    evidence_cards: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    task_catalog: dict[str, Any],
) -> dict[str, Any]:
    accepted = {str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")}
    candidate_records = (
        requested_candidates(request)
        + heuristic_candidates(request, sources)
        + evidence_candidates(evidence_cards)
        + tutorial_candidates(tutorial_catalog)
    )
    decisions = []
    seen_keys = set()
    for record in candidate_records:
        candidate = str(record.get("candidate") or "")
        key = (candidate, record.get("source"), record.get("evidence_ref"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if candidate in accepted:
            decision = "accepted"
            rationale = "Candidate is represented as a task_type inside the single child skill."
        elif is_tutorial_shaped(candidate) or record.get("source") == "tutorial_shape":
            decision = "rejected"
            rationale = "Tutorial/demo/notebook-shaped candidates must remain evidence, not task_type splits."
        else:
            decision = "merged_or_deferred"
            rationale = "Candidate was not selected as a separate task_type; preserve as evidence for review."
        decisions.append({**record, "decision": decision, "rationale": rationale})

    if not decisions and accepted:
        for task_type in sorted(accepted):
            decisions.append(
                {
                    "candidate": task_type,
                    "source": "fallback",
                    "evidence_ref": None,
                    "reason": "Default task_type fallback.",
                    "decision": "accepted",
                    "rationale": "Fallback is represented as a task_type inside the single child skill.",
                }
            )

    accepted_decisions = [item for item in decisions if item["decision"] == "accepted"]
    rejected_tutorial_splits = [item for item in decisions if item["decision"] == "rejected"]
    findings = []
    if not accepted:
        findings.append(
            {
                "severity": "error",
                "code": "no_accepted_task_types",
                "message": "No accepted task_type entries are present in task_catalog.",
            }
        )
    if not accepted_decisions:
        findings.append(
            {
                "severity": "error",
                "code": "no_accepted_partition_decision",
                "message": "Decision log has no accepted task_type decision.",
            }
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "accepted_task_types": sorted(accepted),
        "decision_count": len(decisions),
        "accepted_decision_count": len(accepted_decisions),
        "rejected_tutorial_split_count": len(rejected_tutorial_splits),
        "decisions": decisions,
        "findings": findings,
        "policy": [
            "Capabilities become task_type entries inside one child skill.",
            "Tutorials, examples, demos, notebooks, and quickstarts are evidence sources, not split boundaries.",
            "Unselected candidates should be merged into accepted task contracts or deferred for manual review.",
        ],
    }
