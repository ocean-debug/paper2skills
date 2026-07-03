"""Source parsing summary built from safe index and static inspectors."""

from __future__ import annotations

from collections import Counter
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def compact_file_record(record: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "evidence_id": record.get("evidence_id"),
        "relative_path": record.get("relative_path"),
        "kind": record.get("kind"),
        "status": record.get("status"),
        "parse_status": record.get("parse_status"),
        "bytes": record.get("bytes"),
        "sha256": record.get("sha256"),
    }
    for key in ("functions", "classes", "imports", "api_calls", "headings", "code_fence_languages"):
        values = record.get(key)
        if values:
            compact[key] = values[:20]
    for key in ("function_records", "class_records"):
        values = record.get(key)
        if values:
            compact[key] = values[:20]
    if record.get("code_cell_count") is not None:
        compact["code_cell_count"] = record.get("code_cell_count")
    if record.get("markdown_cell_count") is not None:
        compact["markdown_cell_count"] = record.get("markdown_cell_count")
    return compact


def count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(key) or "missing") for record in records).items()))


def interface_samples(interface_grounding: dict[str, Any], limit: int = 40) -> list[dict[str, Any]]:
    samples = []
    for item in interface_grounding.get("interfaces", [])[:limit]:
        samples.append(
            {
                "interface_id": item.get("interface_id"),
                "qualname": item.get("qualname"),
                "kind": item.get("kind"),
                "signature": item.get("signature"),
                "source_path": item.get("source_path"),
                "confidence": item.get("confidence"),
            }
        )
    return samples


def parser_capability_matrix(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed_kinds = {str(record.get("kind") or "text") for record in records}
    known = {
        "python": {
            "parser": "static_ast",
            "extracted_fields": ["functions", "classes", "imports", "api_calls", "signatures", "docstring_summaries", "branch_parameter_values"],
            "grounding_roles": ["api_surface", "interface_contract_hints", "parameter_constraints"],
            "backend_support": "implemented_python",
            "limitations": ["does_not_import_package", "does_not_execute_functions", "cannot_prove_runtime_semantics"],
        },
        "notebook": {
            "parser": "json_cells",
            "extracted_fields": ["code_cell_count", "markdown_cell_count", "imports", "api_calls"],
            "grounding_roles": ["tutorial_steps", "workflow_order_hints", "api_usage_hints"],
            "backend_support": "implemented_python_tutorial_static",
            "limitations": ["does_not_execute_cells", "outputs_are_not_recomputed", "hidden_state_not_inferred"],
        },
        "markdown": {
            "parser": "heading_and_code_fence_scan",
            "extracted_fields": ["headings", "code_fence_languages"],
            "grounding_roles": ["documentation_sections", "tutorial_headings", "example_code_language_hints"],
            "backend_support": "implemented_static_docs",
            "limitations": ["does_not_execute_code_fences", "does_not_treat_prose_as_verified_behavior"],
        },
        "html": {
            "parser": "heading_and_code_fence_scan",
            "extracted_fields": ["headings", "code_fence_languages"],
            "grounding_roles": ["documentation_sections", "tutorial_headings"],
            "backend_support": "implemented_static_docs",
            "limitations": ["html_is_not_rendered", "does_not_execute_embedded_code"],
        },
        "r": {
            "parser": "text_index",
            "extracted_fields": ["terms", "sha256"],
            "grounding_roles": ["extension_boundary", "source_presence"],
            "backend_support": "reserved_extension",
            "limitations": ["r_backend_not_implemented", "cannot_generate_execution_verified_r_tasks"],
        },
        "config": {
            "parser": "text_index",
            "extracted_fields": ["terms", "sha256"],
            "grounding_roles": ["environment_hint", "dependency_hint"],
            "backend_support": "implemented_static_text",
            "limitations": ["does_not_resolve_dependencies", "does_not_install_environment"],
        },
        "text": {
            "parser": "text_index",
            "extracted_fields": ["terms", "sha256"],
            "grounding_roles": ["weak_context_hint"],
            "backend_support": "implemented_static_text",
            "limitations": ["cannot_ground_api_contracts_without_stronger_sources"],
        },
    }
    matrix = []
    for kind in sorted(observed_kinds.union({"python", "notebook", "markdown", "r"})):
        entry = known.get(kind, known["text"])
        matrix.append(
            {
                "kind": kind,
                "observed_file_count": sum(1 for record in records if record.get("kind") == kind),
                **entry,
                "can_ground_api": kind in {"python", "notebook"},
                "can_ground_task_type": kind in {"python", "notebook", "markdown", "html"},
                "can_ground_contract": kind in {"python", "notebook", "markdown", "html"},
                "can_verify_execution": False,
            }
        )
    return matrix


def build_source_parse_report(
    request: dict[str, Any],
    source_index: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    tutorial_catalog: dict[str, Any],
) -> dict[str, Any]:
    records = source_index.get("files", [])
    indexed = [record for record in records if record.get("status") == "indexed"]
    skipped = [record for record in records if record.get("status") != "indexed"]
    python_records = [record for record in indexed if record.get("kind") == "python"]
    notebook_records = [record for record in indexed if record.get("kind") == "notebook"]
    doc_records = [record for record in indexed if record.get("kind") in {"markdown", "html"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "strategy": {
            "source_material": "registered local material or bounded optional remote fetch",
            "repository_parse": "archive or local tree is indexed without executing code",
            "python_parse": "Python files are parsed with AST for symbols, imports, signatures, defaults, docstrings, and branch hints",
            "tutorial_parse": "notebooks and Markdown tutorials are parsed for compact steps and API-call hints",
            "document_parse": "Markdown, RST, and HTML are parsed for headings and code-fence metadata",
            "execution_policy": "source parsing never imports package code and never runs tutorials",
        },
        "counts": {
            "file_count": len(records),
            "indexed_file_count": len(indexed),
            "skipped_file_count": len(skipped),
            "python_file_count": len(python_records),
            "notebook_file_count": len(notebook_records),
            "document_file_count": len(doc_records),
            "api_candidate_count": api_grounding.get("api_candidate_count", 0),
            "interface_count": interface_grounding.get("interface_count", 0),
            "tutorial_count": tutorial_catalog.get("tutorial_count", 0),
        },
        "kind_counts": count_by(records, "kind"),
        "parse_status_counts": count_by(records, "parse_status"),
        "capability_matrix": parser_capability_matrix(records),
        "skipped_records": [
            {
                "evidence_id": record.get("evidence_id"),
                "relative_path": record.get("relative_path"),
                "kind": record.get("kind"),
                "status": record.get("status"),
                "bytes": record.get("bytes"),
            }
            for record in skipped[:80]
        ],
        "parsed_records": [compact_file_record(record) for record in indexed[:200]],
        "interface_samples": interface_samples(interface_grounding),
        "limitations": [
            "Static parsing can identify candidate APIs and contracts, but cannot prove runtime behavior.",
            "Docstrings and signatures are evidence hints; biological semantics still require official tutorial, documentation, paper, or execution evidence.",
            "R source files can be indexed as text, but the implemented backend is currently Python-first.",
        ],
    }
