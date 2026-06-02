from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper2skill.miners.python_ast import classify_bio_signals, infer_object_flow, mine_python_source


def _source_to_text(source: str | list[str]) -> str:
    if isinstance(source, list):
        return "".join(source)
    return source


def mine_notebook(path: str | Path) -> dict[str, Any]:
    notebook_path = Path(path)
    data = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = []
    steps = []
    title = None
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
            flow = infer_object_flow(source)
            code_preview = source.strip().splitlines()[0] if source.strip() else "Empty code cell"
            step_id = f"tutorial_001:cell_{index:03d}"
            function_calls = [call["name"] for call in record["function_calls"]]
            steps.append(
                {
                    "id": step_id,
                    "step_id": step_id,
                    "name": f"Notebook cell {index}",
                    "description": code_preview,
                    "source": f"{notebook_path}:cell:{index}",
                    "source_type": "tutorial_notebook",
                    "evidence_id": f"{notebook_path.name}:cell:{index}",
                    "language": "python",
                    "code_preview": code_preview,
                    "imports": record["imports"],
                    "function_calls": function_calls,
                    "read_files": record["file_reads"],
                    "write_files": record["file_writes"],
                    "inputs": record["file_reads"],
                    "outputs": record["file_writes"],
                    "input_objects": flow["input_objects"],
                    "output_objects": flow["output_objects"],
                    "parameters": record["parameters"],
                    "figures": [call["name"] for call in record["plots"]],
                    "bio_signals": classify_bio_signals(source, record["function_calls"]),
                    "command_or_code": source,
                    "confidence": "high",
                }
            )
        elif record["cell_type"] == "markdown" and title is None:
            for line in source.splitlines():
                if line.strip().startswith("#"):
                    title = line.strip().lstrip("#").strip()
                    break
        cells.append(record)
    return {"path": str(notebook_path), "title": title, "language": "python", "cells": cells, "steps": steps, "workflow_steps": steps}
