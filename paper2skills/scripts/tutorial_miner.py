"""Static tutorial and workflow-step mining from indexed source material."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text, slugify
from constants import SCHEMA_VERSION


def source_type_lookup(source_grounding: dict[str, Any]) -> dict[str, str]:
    return {str(source.get("evidence_id")): str(source.get("type")) for source in source_grounding.get("sources", [])}


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source") or []
    return "".join(source) if isinstance(source, list) else str(source)


def notebook_steps(record: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(str(record.get("path") or ""))
    if not path.exists() or not path.is_file():
        return []
    try:
        notebook = json.loads(read_text(path))
    except Exception:
        return []
    steps = []
    for index, cell in enumerate(notebook.get("cells", []), start=1):
        text = cell_source(cell)
        if cell.get("cell_type") == "markdown":
            heading = re.search(r"^\s{0,3}#{1,6}\s+(.+)$", text, flags=re.M)
            if heading:
                steps.append(
                    {
                        "step_index": index,
                        "kind": "markdown_heading",
                        "summary": heading.group(1).strip()[:160],
                        "api_calls": [],
                    }
                )
        elif cell.get("cell_type") == "code":
            calls = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_\.]+)\(", text)))[:20]
            imports = sorted(set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", text, flags=re.M)))[:20]
            if calls or imports:
                steps.append(
                    {
                        "step_index": index,
                        "kind": "code_cell",
                        "summary": f"code cell with {len(calls)} API call hints and {len(imports)} imports",
                        "api_calls": calls,
                        "imports": imports,
                    }
                )
    return steps[:80]


def markdown_steps(record: dict[str, Any]) -> list[dict[str, Any]]:
    headings = record.get("headings", [])
    return [
        {
            "step_index": index,
            "kind": "heading",
            "summary": str(heading)[:160],
            "api_calls": [],
        }
        for index, heading in enumerate(headings, start=1)
    ][:80]


def tutorial_records(source_index: dict[str, Any], source_grounding: dict[str, Any]) -> list[dict[str, Any]]:
    types = source_type_lookup(source_grounding)
    tutorials = []
    for record in source_index.get("files", []):
        source_type = types.get(str(record.get("evidence_id")), "")
        path_text = str(record.get("relative_path") or "").lower()
        if source_type != "official_tutorial" and "tutorial" not in path_text and "example" not in path_text:
            continue
        if record.get("kind") == "notebook":
            steps = notebook_steps(record)
        elif record.get("kind") in {"markdown", "html"}:
            steps = markdown_steps(record)
        else:
            continue
        if not steps:
            continue
        tutorials.append(
            {
                "tutorial_id": f"tutorial:{slugify(str(record.get('relative_path')))}",
                "source_evidence_id": record.get("evidence_id"),
                "source_path": record.get("relative_path"),
                "source_type": source_type or "source_path_hint",
                "step_count": len(steps),
                "steps": steps,
            }
        )
    return tutorials


def build_tutorial_catalog(
    request: dict[str, Any],
    source_index: dict[str, Any],
    source_grounding: dict[str, Any],
) -> dict[str, Any]:
    tutorials = tutorial_records(source_index, source_grounding)
    findings = []
    if not tutorials:
        findings.append(
            {
                "severity": "warning",
                "code": "no_tutorial_steps_found",
                "message": "No indexed tutorial or example steps were found.",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "tutorial_count": len(tutorials),
        "tutorials": tutorials,
        "findings": findings,
        "notes": [
            "Tutorial mining records compact step summaries and API hints only.",
            "Tutorial mining does not execute notebooks or scripts.",
        ],
    }
