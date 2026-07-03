"""Build a provenance graph from sources to generated child-skill files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc, slugify
from constants import REQUIRED_CHILD_REFERENCES, SCHEMA_VERSION


CONTRACT_FILE_BY_KIND = {
    "required_input": "references/input-output-contracts.md",
    "must_confirm": "references/input-output-contracts.md",
    "expected_output": "references/input-output-contracts.md",
    "validation_check": "references/validation.md",
    "refusal_boundary": "references/limitations-and-refusal.md",
}


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, kind: str, **attrs: Any) -> None:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "kind": kind}
    nodes[node_id].update(attrs)


def add_edge(edges: list[dict[str, Any]], source: str, target: str, relation: str, **attrs: Any) -> None:
    edges.append({"source": source, "target": target, "relation": relation, **attrs})


def child_file_nodes(child_skill_dir: Path) -> list[dict[str, Any]]:
    required_files = ["SKILL.md"] + [f"references/{name}" for name in REQUIRED_CHILD_REFERENCES]
    files = []
    for rel in required_files:
        path = child_skill_dir / rel
        files.append(
            {
                "node_id": f"child_file:{rel}",
                "path": rel,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else None,
            }
        )
    return files


def contract_node_id(record: dict[str, Any]) -> str:
    task_type = slugify(str(record.get("task_type") or "task"))
    kind = slugify(str(record.get("contract_kind") or record.get("kind") or "contract"))
    subject = slugify(str(record.get("subject") or record.get("text") or record.get("reason_key") or "item"))
    return f"contract:{task_type}:{kind}:{subject}"


def build_lineage_graph(
    request: dict[str, Any],
    source_manifest: dict[str, Any],
    evidence_cards: dict[str, Any],
    task_catalog: dict[str, Any],
    contract_traceability: dict[str, Any],
    skill_spec: dict[str, Any],
    child_skill_dir: Path,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for source in source_manifest.get("sources", []):
        evidence_id = str(source.get("evidence_id"))
        add_node(
            nodes,
            f"source:{evidence_id}",
            "source",
            evidence_id=evidence_id,
            source_type=source.get("type"),
            priority=source.get("priority"),
            official=source.get("official"),
            indexed_file_count=source.get("indexed_file_count", 0),
            evidence_card_count=source.get("evidence_card_count", 0),
        )

    card_by_id: dict[str, dict[str, Any]] = {}
    for card in evidence_cards.get("cards", []):
        card_id = str(card.get("evidence_card_id"))
        card_by_id[card_id] = card
        add_node(
            nodes,
            card_id,
            "evidence_card",
            claim_type=card.get("claim_type"),
            source_type=card.get("source_type"),
            task_type_candidates=card.get("task_type_candidates", []),
        )
        source_ref = card.get("source_evidence_id")
        if source_ref:
            add_edge(
                edges,
                f"source:{source_ref}",
                card_id,
                "produces_evidence_card",
                claim_type=card.get("claim_type"),
            )

    task_ids = []
    for task in task_catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        task_id = f"task:{task_type}"
        task_ids.append(task_id)
        add_node(
            nodes,
            task_id,
            "task_type",
            task_type=task_type,
            verification_status=task.get("verification_status"),
        )
        inbound_evidence = 0
        for ref in task.get("evidence_refs", []):
            ref = str(ref)
            if ref in card_by_id:
                add_edge(edges, ref, task_id, "supports_task_type", evidence_ref=ref)
                inbound_evidence += 1
            elif f"source:{ref}" in nodes:
                add_edge(edges, f"source:{ref}", task_id, "supports_task_type", evidence_ref=ref)
                inbound_evidence += 1
        for card in evidence_cards.get("cards", []):
            if task_type in card.get("task_type_candidates", []) and card.get("evidence_card_id"):
                card_id = str(card["evidence_card_id"])
                add_edge(edges, card_id, task_id, "candidate_supports_task_type", evidence_ref=card_id)
                inbound_evidence += 1
        if inbound_evidence == 0:
            findings.append(
                {
                    "severity": "error",
                    "code": "task_without_lineage_evidence",
                    "task_type": task_type,
                    "message": "Task_type has no source or evidence-card lineage edge.",
                }
            )

    contract_records_by_task: dict[str, list[dict[str, Any]]] = {}
    for record in contract_traceability.get("records", []):
        task_type = str(record.get("task_type"))
        record_id = contract_node_id(record)
        contract_records_by_task.setdefault(task_type, []).append(record)
        add_node(
            nodes,
            record_id,
            "contract_record",
            task_type=task_type,
            contract_kind=record.get("contract_kind") or record.get("kind"),
            subject=record.get("subject") or record.get("text"),
            evidence_refs=record.get("evidence_refs", []),
        )
        add_edge(edges, f"task:{task_type}", record_id, "has_contract_record")
        if not record.get("evidence_refs"):
            findings.append(
                {
                    "severity": "error",
                    "code": "contract_record_without_evidence_refs",
                    "task_type": task_type,
                    "message": "Contract record has no evidence_refs.",
                }
            )
        for ref in record.get("evidence_refs", []):
            ref = str(ref)
            if ref in card_by_id:
                add_edge(edges, ref, record_id, "supports_contract_record", evidence_ref=ref)
            elif f"source:{ref}" in nodes:
                add_edge(edges, f"source:{ref}", record_id, "supports_contract_record", evidence_ref=ref)

    for task_id in task_ids:
        task_type = task_id.split(":", 1)[1]
        if not contract_records_by_task.get(task_type):
            findings.append(
                {
                    "severity": "error",
                    "code": "task_without_contract_lineage",
                    "task_type": task_type,
                    "message": "Task_type has no contract traceability records.",
                }
            )

    for file_record in child_file_nodes(child_skill_dir):
        add_node(
            nodes,
            file_record["node_id"],
            "child_skill_file",
            path=file_record["path"],
            exists=file_record["exists"],
            bytes=file_record["bytes"],
        )
        if not file_record["exists"]:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_child_skill_file",
                    "path": file_record["path"],
                    "message": "Required child skill file is missing from lineage graph.",
                }
            )
    for task_id in task_ids:
        for rel in ("SKILL.md", "references/task-types.md", "references/evidence.md"):
            add_edge(edges, task_id, f"child_file:{rel}", "rendered_in_child_file")
    for record in contract_traceability.get("records", []):
        record_id = contract_node_id(record)
        target_file = CONTRACT_FILE_BY_KIND.get(str(record.get("contract_kind") or record.get("kind")), "references/evidence.md")
        add_edge(edges, record_id, f"child_file:{target_file}", "rendered_in_child_file")

    if source_manifest.get("source_count", 0) == 0:
        findings.append(
            {
                "severity": "error",
                "code": "no_source_nodes",
                "message": "Lineage graph has no source nodes.",
            }
        )
    if skill_spec.get("child_skill", {}).get("path") is None and not str(child_skill_dir):
        findings.append(
            {
                "severity": "warning",
                "code": "missing_skill_spec_path",
                "message": "Skill spec did not record a child skill path.",
            }
        )

    edge_keys = set()
    deduped_edges = []
    for edge in edges:
        key = (edge.get("source"), edge.get("target"), edge.get("relation"), edge.get("evidence_ref"))
        if key in edge_keys:
            continue
        edge_keys.add(key)
        deduped_edges.append(edge)

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "node_count": len(nodes),
        "edge_count": len(deduped_edges),
        "nodes": sorted(nodes.values(), key=lambda item: str(item.get("id"))),
        "edges": sorted(deduped_edges, key=lambda item: (str(item.get("source")), str(item.get("target")), str(item.get("relation")))),
        "findings": findings,
        "policy": "Lineage graph records compact source-to-skill provenance; it does not store long excerpts or execution logs.",
    }
