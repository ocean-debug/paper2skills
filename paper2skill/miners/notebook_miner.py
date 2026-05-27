from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper2skill.miners.python_ast import mine_python_source


def _source_to_text(source: str | list[str]) -> str:
    if isinstance(source, list):
        return "".join(source)
    return source


def mine_notebook(path: str | Path) -> dict[str, Any]:
    notebook_path = Path(path)
    data = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = []
    steps = []
    for index, cell in enumerate(data.get("cells", [])):
        source = _source_to_text(cell.get("source", ""))
        record: dict[str, Any] = {
            "index": index,
            "cell_type": cell.get("cell_type", "unknown"),
            "source": source,
            "imports": [],
            "assignments": [],
            "function_calls": [],
            "file_reads": [],
            "file_writes": [],
            "parameters": {},
            "plots": [],
        }
        if record["cell_type"] == "code":
            mined = mine_python_source(source)
            record.update({key: mined.get(key, record.get(key)) for key in record if key in mined})
            steps.append(
                {
                    "id": f"notebook-cell-{index}",
                    "name": f"Notebook cell {index}",
                    "description": source.strip().splitlines()[0] if source.strip() else "Empty code cell",
                    "source": str(notebook_path),
                    "source_type": "tutorial_notebook",
                    "evidence_id": f"{notebook_path.name}:cell:{index}",
                    "inputs": record["file_reads"],
                    "outputs": record["file_writes"],
                    "parameters": record["parameters"],
                    "command_or_code": source,
                    "confidence": "high",
                }
            )
        cells.append(record)
    return {"path": str(notebook_path), "language": "python", "cells": cells, "workflow_steps": steps}
