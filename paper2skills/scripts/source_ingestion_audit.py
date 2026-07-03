"""Audit source ingestion lineage across grounding, fetch, index, parse, and evidence cards."""

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
    evidence_id: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if evidence_id:
        item["evidence_id"] = evidence_id
    findings.append(item)


def evidence_ids(items: list[dict[str, Any]], key: str = "evidence_id") -> list[str]:
    return [str(item.get(key)) for item in items if item.get(key)]


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def count_indexed_by_evidence(source_index: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in source_index.get("files", []):
        evidence_id = str(record.get("evidence_id") or "")
        if not evidence_id:
            continue
        if record.get("status") == "indexed":
            counts[evidence_id] = counts.get(evidence_id, 0) + 1
    return dict(sorted(counts.items()))


def card_count_by_source(evidence_cards: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in evidence_cards.get("cards", []):
        evidence_id = str(card.get("source_evidence_id") or "")
        if not evidence_id:
            continue
        counts[evidence_id] = counts.get(evidence_id, 0) + 1
    return dict(sorted(counts.items()))


def build_source_ingestion_audit(
    request: dict[str, Any],
    source_grounding: dict[str, Any],
    source_fetch_report: dict[str, Any],
    source_index: dict[str, Any],
    source_parse_report: dict[str, Any],
    source_parsing_coverage: dict[str, Any],
    source_parsing_audit: dict[str, Any],
    source_manifest: dict[str, Any],
    evidence_cards: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit that source-ingestion artifacts agree on identity and counts."""
    findings: list[dict[str, Any]] = []

    grounding_sources = source_grounding.get("sources", [])
    fetch_sources = source_fetch_report.get("sources", [])
    manifest_sources = source_manifest.get("sources", [])
    index_records = source_index.get("files", [])
    indexed_records = [record for record in index_records if record.get("status") == "indexed"]

    grounding_ids = evidence_ids(grounding_sources)
    fetch_ids = evidence_ids(fetch_sources)
    manifest_ids = evidence_ids(manifest_sources)
    indexed_ids = evidence_ids(index_records)
    card_source_ids = evidence_ids(evidence_cards.get("cards", []), "source_evidence_id")

    if not grounding_ids:
        add_finding(findings, "error", "missing_grounding_sources", "Source grounding must contain at least one source.")

    for evidence_id in duplicate_values(grounding_ids):
        add_finding(findings, "error", "duplicate_grounding_evidence_id", "Source grounding evidence_id values must be unique.", evidence_id)

    for evidence_id in sorted(set(fetch_ids) - set(grounding_ids)):
        add_finding(findings, "error", "fetch_source_without_grounding", "Fetched or registered source has no source grounding record.", evidence_id)
    for evidence_id in sorted(set(grounding_ids) - set(fetch_ids)):
        add_finding(findings, "error", "grounding_source_without_fetch_record", "Source grounding record has no fetch/register report.", evidence_id)
    for evidence_id in sorted(set(manifest_ids) - set(grounding_ids)):
        add_finding(findings, "error", "manifest_source_without_grounding", "Source manifest contains a source missing from grounding.", evidence_id)
    for evidence_id in sorted(set(indexed_ids) - set(grounding_ids)):
        add_finding(findings, "error", "indexed_file_without_grounding", "Indexed file references an unknown grounding evidence_id.", evidence_id)
    for evidence_id in sorted(set(card_source_ids) - set(grounding_ids)):
        add_finding(findings, "error", "evidence_card_without_grounding", "Evidence card references an unknown source_evidence_id.", evidence_id)

    if set(manifest_ids) != set(grounding_ids):
        add_finding(findings, "error", "manifest_grounding_id_mismatch", "Source manifest source ids must match source grounding ids.")

    if source_index.get("file_count") != len(index_records):
        add_finding(findings, "error", "source_index_file_count_mismatch", "source_index.file_count must match files length.")
    if len(fetch_sources) != len(grounding_sources):
        add_finding(findings, "error", "source_fetch_count_mismatch", "source_fetch_report must contain one record for each grounded source.")
    parse_counts = source_parse_report.get("counts") or {}
    if parse_counts.get("file_count") != len(index_records):
        add_finding(findings, "error", "parse_report_file_count_mismatch", "source_parse_report counts must match source_index files length.")
    if parse_counts.get("indexed_file_count") != len(indexed_records):
        add_finding(findings, "error", "parse_report_indexed_count_mismatch", "source_parse_report indexed_file_count must match indexed source records.")
    if source_manifest.get("source_count") != len(manifest_sources):
        add_finding(findings, "error", "source_manifest_count_mismatch", "source_manifest.source_count must match sources length.")
    if source_manifest.get("indexed_file_count") != source_index.get("file_count"):
        add_finding(findings, "error", "source_manifest_index_count_mismatch", "source_manifest indexed_file_count must match source_index.file_count.")
    if evidence_cards.get("card_count") != len(evidence_cards.get("cards", [])):
        add_finding(findings, "error", "evidence_card_count_mismatch", "evidence_cards.card_count must match cards length.")
    if source_manifest.get("evidence_card_count") != evidence_cards.get("card_count"):
        add_finding(findings, "error", "source_manifest_card_count_mismatch", "source_manifest evidence_card_count must match evidence_cards.card_count.")

    indexed_by_source = count_indexed_by_evidence(source_index)
    cards_by_source = card_count_by_source(evidence_cards)
    for source in manifest_sources:
        evidence_id = str(source.get("evidence_id") or "")
        if source.get("indexed_file_count") != indexed_by_source.get(evidence_id, 0):
            add_finding(findings, "error", "manifest_indexed_count_mismatch", "Manifest indexed_file_count must match source_index records.", evidence_id)
        if source.get("evidence_card_count") != cards_by_source.get(evidence_id, 0):
            add_finding(findings, "error", "manifest_card_count_mismatch", "Manifest evidence_card_count must match evidence_cards records.", evidence_id)

    strategy = source_parse_report.get("strategy") or {}
    execution_policy = str(strategy.get("execution_policy") or "").lower()
    fetch_notes = " ".join(str(item).lower() for item in source_fetch_report.get("notes", []))
    if "never" not in execution_policy and "does not" not in execution_policy:
        add_finding(findings, "error", "parse_execution_policy_missing", "Source parse report must explicitly state a non-execution policy.")
    if "never executes" not in fetch_notes:
        add_finding(findings, "error", "fetch_execution_policy_missing", "Source fetch report must state that fetching never executes source code.")
    if source_parsing_coverage.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_coverage_failed", "Source parsing coverage failed.")
    if source_parsing_audit.get("status") == "fail":
        add_finding(findings, "error", "source_parsing_audit_failed", "Source parsing audit failed.")

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "source_count": len(grounding_ids),
        "fetch_source_count": len(fetch_ids),
        "manifest_source_count": len(manifest_ids),
        "indexed_file_count": len(index_records),
        "indexed_record_count": len(indexed_records),
        "evidence_card_count": len(evidence_cards.get("cards", [])),
        "indexed_by_source": indexed_by_source,
        "cards_by_source": cards_by_source,
        "source_parsing_coverage_status": source_parsing_coverage.get("status"),
        "source_parsing_audit_status": source_parsing_audit.get("status"),
        "findings": findings,
        "policy": [
            "Source ingestion audit is static and never imports, installs, or executes package code.",
            "Source identity must stay consistent from grounding through fetch, index, manifest, parse report, and evidence cards.",
            "Count mismatches block publishing because they make downstream evidence and task contracts non-auditable.",
        ],
    }
