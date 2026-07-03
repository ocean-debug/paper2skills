"""Audit source parsing strategy, provenance, and non-execution boundaries."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


REQUIRED_STRATEGY_FIELDS = {
    "source_material",
    "repository_parse",
    "python_parse",
    "tutorial_parse",
    "document_parse",
    "execution_policy",
}

REQUIRED_INDEX_FIELDS = {"evidence_id", "relative_path", "kind", "status", "bytes"}
REQUIRED_INDEXED_FIELDS = REQUIRED_INDEX_FIELDS | {"parse_status", "sha256"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    source_path: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if source_path:
        item["source_path"] = source_path
    findings.append(item)


def indexed_records(source_index: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for record in source_index.get("files", []) if record.get("status") == "indexed"]


def kind_count(records: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for record in records if record.get("kind") == kind)


def build_source_parsing_audit(
    request: dict[str, Any],
    source_index: dict[str, Any],
    source_parse_report: dict[str, Any],
    source_parsing_coverage: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    tutorial_catalog: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    records = source_index.get("files", [])
    indexed = indexed_records(source_index)
    strategy = source_parse_report.get("strategy") or {}
    capability_matrix = source_parse_report.get("capability_matrix") or []

    missing_strategy = sorted(REQUIRED_STRATEGY_FIELDS.difference(strategy))
    if missing_strategy:
        add_finding(
            findings,
            "error",
            "missing_source_parsing_strategy_fields",
            "Source parse report is missing required strategy fields.",
        )

    execution_policy = str(strategy.get("execution_policy") or "").lower()
    if "never" not in execution_policy and "does not" not in execution_policy:
        add_finding(
            findings,
            "error",
            "unsafe_or_implicit_execution_policy",
            "Source parsing must explicitly state that it does not execute package code or tutorials.",
        )

    if not isinstance(capability_matrix, list) or not capability_matrix:
        add_finding(
            findings,
            "error",
            "missing_parser_capability_matrix",
            "Source parse report must declare parser capabilities by source kind.",
        )
        capability_matrix = []
    matrix_by_kind = {str(row.get("kind")): row for row in capability_matrix if isinstance(row, dict)}
    for required_kind in ("python", "notebook", "markdown", "r"):
        if required_kind not in matrix_by_kind:
            add_finding(
                findings,
                "error",
                "parser_capability_kind_missing",
                "Parser capability matrix is missing a required source kind.",
                required_kind,
            )
    for row in capability_matrix:
        if not isinstance(row, dict):
            continue
        if row.get("can_verify_execution") is not False:
            add_finding(
                findings,
                "error",
                "parser_capability_overclaims_execution",
                "Static parser capabilities must not claim execution verification.",
                str(row.get("kind") or ""),
            )

    for record in records[:500]:
        required = REQUIRED_INDEXED_FIELDS if record.get("status") == "indexed" else REQUIRED_INDEX_FIELDS
        missing_fields = sorted(field for field in required if field not in record)
        if missing_fields:
            add_finding(
                findings,
                "error",
                "source_record_missing_provenance_fields",
                "Source index record is missing provenance, parse, or hash fields.",
                str(record.get("relative_path") or ""),
            )
        if record.get("status") == "indexed" and record.get("kind") == "python":
            if record.get("functions") and not record.get("function_records"):
                add_finding(
                    findings,
                    "error",
                    "python_functions_without_function_records",
                    "Python source record has function symbols but no detailed function_records.",
                    str(record.get("relative_path") or ""),
                )
            if record.get("classes") and not record.get("class_records"):
                add_finding(
                    findings,
                    "error",
                    "python_classes_without_class_records",
                    "Python source record has class symbols but no detailed class_records.",
                    str(record.get("relative_path") or ""),
                )

    python_count = kind_count(indexed, "python")
    notebook_count = kind_count(indexed, "notebook")
    doc_count = kind_count(indexed, "markdown") + kind_count(indexed, "html")
    r_count = kind_count(indexed, "r")

    if python_count and interface_grounding.get("interface_count", 0) == 0:
        add_finding(
            findings,
            "warning",
            "python_sources_without_interface_grounding",
            "Python sources were indexed, but no static interfaces were inspected.",
        )
    if indexed and api_grounding.get("api_candidate_count", 0) == 0:
        add_finding(
            findings,
            "warning",
            "indexed_sources_without_api_grounding",
            "Indexed sources produced no API candidates.",
        )
    if notebook_count and tutorial_catalog.get("tutorial_count", 0) == 0:
        add_finding(
            findings,
            "warning",
            "notebooks_without_tutorial_catalog",
            "Notebook sources were indexed, but no tutorial steps were mined.",
        )
    if doc_count and not source_parse_report.get("parsed_records"):
        add_finding(
            findings,
            "warning",
            "documents_without_parsed_record_samples",
            "Documentation sources were indexed, but source_parse_report has no parsed record samples.",
        )
    if r_count:
        add_finding(
            findings,
            "warning",
            "r_sources_extension_reserved",
            "R sources were indexed as text only; the implemented backend remains Python-first.",
        )

    if source_parsing_coverage.get("status") == "fail":
        add_finding(
            findings,
            "error",
            "source_parsing_coverage_failed",
            "Source parsing coverage failed and must be resolved before publish.",
        )
    if source_parsing_coverage.get("file_count") != source_index.get("file_count"):
        add_finding(
            findings,
            "error",
            "source_index_coverage_count_mismatch",
            "source_index and source_parsing_coverage disagree on file_count.",
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "strategy_fields": sorted(strategy),
        "required_strategy_fields": sorted(REQUIRED_STRATEGY_FIELDS),
        "capability_kind_count": len(matrix_by_kind),
        "indexed_file_count": len(indexed),
        "python_file_count": python_count,
        "notebook_file_count": notebook_count,
        "document_file_count": doc_count,
        "r_file_count": r_count,
        "api_candidate_count": api_grounding.get("api_candidate_count", 0),
        "interface_count": interface_grounding.get("interface_count", 0),
        "tutorial_count": tutorial_catalog.get("tutorial_count", 0),
        "findings": findings,
        "policy": [
            "Source parsing must be static and non-executing.",
            "Every indexed source record must preserve evidence id, relative path, kind, size, parse status, and hash when available.",
            "Static parser outputs are grounding hints; execution verification requires explicit trace-backed execution grounding.",
        ],
    }
