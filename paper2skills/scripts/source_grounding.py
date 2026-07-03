"""Official source cataloging and source-grounding artifacts."""

from __future__ import annotations

from typing import Any

from common import as_list, now_utc
from constants import EVIDENCE_PRIORITY, SCHEMA_VERSION


def source_entries(request: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    repo_url = request.get("repo_url")
    if repo_url:
        sources.append(
            {
                "evidence_id": "repo:main",
                "type": "repository",
                "uri": repo_url,
                "official": True,
                "priority": "source_code_or_api",
            }
        )
    for index, uri in enumerate(as_list(request.get("tutorial_links")), start=1):
        sources.append(
            {
                "evidence_id": f"tutorial:{index:02d}",
                "type": "official_tutorial",
                "uri": uri,
                "official": True,
                "priority": "official_tutorial_or_docs",
            }
        )
    for index, uri in enumerate(as_list(request.get("doc_links")), start=1):
        sources.append(
            {
                "evidence_id": f"docs:{index:02d}",
                "type": "official_docs",
                "uri": uri,
                "official": True,
                "priority": "official_tutorial_or_docs",
            }
        )
    for index, uri in enumerate(as_list(request.get("paper_links")), start=1):
        sources.append(
            {
                "evidence_id": f"paper:{index:02d}",
                "type": "paper",
                "uri": uri,
                "official": False,
                "priority": "paper",
            }
        )
    for index, uri in enumerate(as_list(request.get("source_material_paths")), start=1):
        sources.append(
            {
                "evidence_id": f"local:{index:02d}",
                "type": "local_source_material",
                "uri": uri,
                "official": False,
                "priority": "official_tutorial_or_docs",
            }
        )
    return sources


def build_source_grounding(
    request: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "repo_url": request.get("repo_url"),
        "evidence_priority": EVIDENCE_PRIORITY,
        "sources": sources,
        "copyright_policy": "Store concise source references only; do not store long excerpts.",
    }
