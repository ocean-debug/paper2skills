from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from paper2skill.miners.python_ast import classify_bio_signals, infer_object_flow, mine_python_source


R_LIBRARY_RE = re.compile(r"\b(?:library|require)\s*\(\s*['\"]?([A-Za-z0-9_.]+)['\"]?\s*\)")
R_FUNCTION_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_.]*)\s*\(")
R_ASSIGN_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.]*)\s*(?:<-|=)\s*(.+?)\s*$")
R_READ_RE = re.compile(r"\b(read\.[A-Za-z0-9_.]+|readRDS|read_h5ad)\s*\(\s*([A-Za-z][A-Za-z0-9_.]*|['\"][^'\"]+['\"])")
R_WRITE_RE = re.compile(r"\b(write\.[A-Za-z0-9_.]+|saveRDS|ggsave)\s*\((?:[^,\n]+,\s*)?([A-Za-z][A-Za-z0-9_.]*|['\"][^'\"]+['\"])")
R_FIGURE_RE = re.compile(r"\b(ggsave|pdf|png|jpeg|tiff|svg)\s*\(")


def mine_r_source(source: str) -> dict[str, Any]:
    imports = R_LIBRARY_RE.findall(source)
    calls = []
    assignments = []
    parameters: dict[str, Any] = {}
    for lineno, line in enumerate(source.splitlines(), start=1):
        for call in R_FUNCTION_RE.findall(line):
            if call not in {"if", "for", "while", "function"}:
                calls.append({"name": call, "lineno": lineno})
        match = R_ASSIGN_RE.match(line)
        if match:
            name, value = match.groups()
            clean_value = value.strip().strip("'\"")
            assignments.append({"name": name, "lineno": lineno, "value": clean_value})
            parameters[name] = clean_value
    file_reads = [_resolve_r_arg(match[1], parameters) for match in R_READ_RE.findall(source)]
    file_writes = [_resolve_r_arg(match[1], parameters) for match in R_WRITE_RE.findall(source)]
    return {
        "imports": imports,
        "functions": [],
        "top_level_steps": [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("#")],
        "function_calls": calls,
        "assignments": assignments,
        "parameters": parameters,
        "file_reads": [item for item in file_reads if item],
        "file_writes": [item for item in file_writes if item],
        "figures": R_FIGURE_RE.findall(source),
    }


def _resolve_r_arg(value: str, parameters: dict[str, Any]) -> str | None:
    value = value.strip().strip("'\"")
    resolved = parameters.get(value, value)
    if isinstance(resolved, str):
        return resolved.strip().strip("'\"")
    return None


def mine_script(path: str | Path) -> dict[str, Any]:
    script_path = Path(path)
    source = script_path.read_text(encoding="utf-8", errors="replace")
    suffix = script_path.suffix.lower()
    if suffix == ".py":
        mined = mine_python_source(source)
        language = "python"
        top_level_steps = [
            line.strip()
            for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith(("def ", "class "))
        ]
    elif suffix in {".r", ".rmd"}:
        mined = mine_r_source(source)
        language = "r"
        top_level_steps = mined.get("top_level_steps", [])
    else:
        mined = {"imports": [], "functions": [], "function_calls": [], "file_reads": [], "file_writes": [], "parameters": {}}
        language = "unknown"
        top_level_steps = []
    steps = []
    for index, step in enumerate(top_level_steps, start=1):
        step_id = f"tutorial_001:line_{index:03d}"
        if language == "python":
            flow = infer_object_flow(step)
            calls = mine_python_source(step).get("function_calls", [])
            function_calls = [call["name"] for call in calls]
            bio_signals = classify_bio_signals(step, calls)
        else:
            flow = {"input_objects": [], "output_objects": [name for name, _line, _value in []]}
            function_calls = [call["name"] for call in mined.get("function_calls", []) if call.get("lineno") == index]
            bio_signals = classify_bio_signals(step, function_calls)
        steps.append(
            {
                "id": step_id,
                "step_id": step_id,
                "name": f"Script step {index}",
                "description": step[:120],
                "source": f"{script_path}:line:{index}",
                "source_type": "tutorial_script",
                "evidence_id": step_id,
                "language": language,
                "code_preview": step[:200],
                "imports": mined.get("imports", []),
                "function_calls": function_calls,
                "read_files": mined.get("file_reads", []),
                "write_files": mined.get("file_writes", []),
                "inputs": mined.get("file_reads", []),
                "outputs": mined.get("file_writes", []),
                "input_objects": flow["input_objects"],
                "output_objects": flow["output_objects"],
                "parameters": mined.get("parameters", {}),
                "figures": mined.get("figures", []),
                "bio_signals": bio_signals,
                "command_or_code": step,
                "confidence": "medium",
            }
        )
    return {
        "path": str(script_path),
        "language": language,
        "imports": mined.get("imports", []),
        "functions": mined.get("functions", []),
        "top_level_steps": top_level_steps,
        "function_calls": mined.get("function_calls", []),
        "assignments": mined.get("assignments", []),
        "parameters": mined.get("parameters", {}),
        "file_reads": mined.get("file_reads", []),
        "file_writes": mined.get("file_writes", []),
        "steps": steps,
        "workflow_steps": steps,
    }
