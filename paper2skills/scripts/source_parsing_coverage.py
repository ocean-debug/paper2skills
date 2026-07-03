"""Coverage audit for static source parsing."""

from __future__ import annotations

from collections import Counter
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PARSER_CAPABILITIES = {
    "python": "AST symbols, imports, signatures, defaults, docstrings, and branch hints",
    "notebook": "JSON notebook cells, imports, and API-call hints",
    "markdown": "headings and fenced-code language metadata",
    "html": "heading-like text and fenced-code language metadata after text decoding",
    "config": "dependency and configuration text indexing",
    "r": "text indexing only; R backend remains extension-reserved",
    "text": "bounded term indexing",
}


def count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(key) or "missing") for record in records).items()))


def source_status_counts(fetch_report: dict[str, Any]) -> dict[str, int]:
    return count_by(fetch_report.get("sources", []), "status")


def parseable_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("status") == "indexed"
        and record.get("kind") in {"python", "notebook", "markdown", "html", "config", "r", "text"}
    ]


def coverage_by_kind(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kinds = sorted({str(record.get("kind") or "missing") for record in records})
    rows = []
    for kind in kinds:
        kind_records = [record for record in records if str(record.get("kind") or "missing") == kind]
        indexed = [record for record in kind_records if record.get("status") == "indexed"]
        parsed = [record for record in indexed if str(record.get("parse_status") or "").startswith("parsed")]
        rows.append(
            {
                "kind": kind,
                "file_count": len(kind_records),
                "indexed_count": len(indexed),
                "parsed_count": len(parsed),
                "parse_status_counts": count_by(kind_records, "parse_status"),
                "capability": PARSER_CAPABILITIES.get(kind, "bounded text metadata only"),
            }
        )
    return rows


def build_source_parsing_coverage(
    request: dict[str, Any],
    source_fetch_report: dict[str, Any],
    source_index: dict[str, Any],
    source_parse_report: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    tutorial_catalog: dict[str, Any],
) -> dict[str, Any]:
    records = source_index.get("files", [])
    indexed = [record for record in records if record.get("status") == "indexed"]
    parseable = parseable_records(records)
    findings = []
    fetch_status = source_status_counts(source_fetch_report)
    if source_fetch_report.get("fetch_enabled") and not indexed:
        findings.append(
            {
                "severity": "error",
                "code": "fetch_enabled_but_no_indexed_sources",
                "message": "Source fetch was enabled, but no source files were indexed.",
            }
        )
    if not source_fetch_report.get("fetch_enabled") and fetch_status.get("skipped_fetch_disabled", 0) > 0:
        findings.append(
            {
                "severity": "warning",
                "code": "remote_sources_not_fetched",
                "message": "Remote sources were registered but not fetched; parsing coverage is limited to local source material.",
            }
        )
    if indexed and not parseable:
        findings.append(
            {
                "severity": "warning",
                "code": "indexed_sources_not_parseable",
                "message": "Indexed source files did not match parser-supported text kinds.",
            }
        )
    if api_grounding.get("api_candidate_count", 0) == 0 and indexed:
        findings.append(
            {
                "severity": "warning",
                "code": "indexed_sources_without_api_candidates",
                "message": "Indexed source files produced no API candidates.",
            }
        )
    if api_grounding.get("api_candidate_count", 0) > 0 and interface_grounding.get("interface_count", 0) == 0:
        findings.append(
            {
                "severity": "warning",
                "code": "api_candidates_without_interface_parse",
                "message": "API candidates exist, but no interfaces were statically inspected.",
            }
        )
    if tutorial_catalog.get("tutorial_count", 0) == 0 and indexed:
        findings.append(
            {
                "severity": "warning",
                "code": "indexed_sources_without_tutorial_steps",
                "message": "Indexed source files produced no tutorial/example steps.",
            }
        )
    if source_index.get("truncated"):
        findings.append(
            {
                "severity": "warning",
                "code": "source_index_truncated",
                "message": "Source indexing reached max_index_files; parsing coverage is incomplete.",
            }
        )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "fetch_enabled": bool(source_fetch_report.get("fetch_enabled")),
        "source_status_counts": fetch_status,
        "file_count": len(records),
        "scanned_file_count": source_index.get("scanned_file_count"),
        "source_index_truncated": bool(source_index.get("truncated")),
        "indexed_file_count": len(indexed),
        "parseable_file_count": len(parseable),
        "api_candidate_count": api_grounding.get("api_candidate_count", 0),
        "interface_count": interface_grounding.get("interface_count", 0),
        "tutorial_count": tutorial_catalog.get("tutorial_count", 0),
        "source_parse_counts": source_parse_report.get("counts", {}),
        "coverage_by_kind": coverage_by_kind(records),
        "findings": findings,
        "policy": [
            "Source parsing coverage is static and non-executing.",
            "Warnings describe limited evidence coverage; only explicit execution traces can verify runtime behavior.",
        ],
    }
