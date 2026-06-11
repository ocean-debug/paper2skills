from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Any

from paper2skill.miners.python_ast import classify_bio_signals, infer_object_flow, mine_python_source
from paper2skill.miners.script_miner import mine_r_source


READ_NAMES = {"open", "read_csv", "read_table", "read_excel", "read_h5ad", "load", "loadtxt", "read_10x_mtx"}
WRITE_NAMES = {"to_csv", "write", "write_csv", "save", "savefig", "save_npz", "dump"}
CELL_MAGIC_RE = re.compile(r"^\s*%%([A-Za-z0-9_]+)\b[^\n]*\n?(.*)$", re.S)
LINE_MAGIC_RE = re.compile(r"^\s*%([A-Za-z0-9_]+)\b(.*)$")
SHELL_LINE_RE = re.compile(r"^\s*!(.+)$")
NETWORK_WORDS = ("wget ", "curl ", "gsutil ", "aws s3", "http://", "https://")
INSTALL_WORDS = ("pip install", "conda install", "mamba install")
PYTHON_WRAPPER_CELL_MAGICS = {"capture", "time", "timeit", "prun"}


def _source_to_text(source: str | list[str]) -> str:
    if isinstance(source, list):
        return "".join(source)
    return source


def default_execution_policy() -> dict[str, Any]:
    return {
        "will_execute": False,
        "reason": "static_analysis_only",
        "shell_magics": [],
        "line_magics": [],
        "cell_magics": [],
        "parameter_cells": [],
        "large_outputs": [],
        "risks": [],
    }


def mine_notebook(path: str | Path) -> dict[str, Any]:
    notebook_path = Path(path)
    data = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = []
    steps = []
    title = None
    parameters: dict[str, Any] = {}
    known_values: dict[str, Any] = {}
    policy = default_execution_policy()
    for index, cell in enumerate(data.get("cells", [])):
        source = _source_to_text(cell.get("source", ""))
        metadata = cell.get("metadata", {}) or {}
        tags = set(metadata.get("tags", []) or [])
        parameter_cell = "parameters" in tags or _looks_like_parameter_cell(source, index)
        if parameter_cell:
            policy["parameter_cells"].append(index)
        _record_output_policy(index, cell.get("outputs", []) or [], policy)
        shell_lines, line_magics, clean_source = _split_python_magics(source)
        for command in shell_lines:
            policy["shell_magics"].append({"cell": index, "command": command})
            _record_command_risks(command, policy)
        for magic in line_magics:
            policy["line_magics"].append({"cell": index, **magic})
        cell_magic = _cell_magic(source)
        if cell_magic:
            policy["cell_magics"].append({"cell": index, "magic": cell_magic["magic"]})
            if cell_magic["magic"].lower() in {"bash", "sh"}:
                _record_command_risks(cell_magic["body"], policy)
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
            language = "python"
            command_or_code = clean_source
            if cell_magic and cell_magic["magic"].lower() == "r":
                language = "r"
                command_or_code = cell_magic["body"]
                mined = mine_r_source(command_or_code)
            elif cell_magic and cell_magic["magic"].lower() in {"bash", "sh"}:
                language = "bash"
                command_or_code = cell_magic["body"]
                mined = {"imports": [], "assignments": [], "function_calls": [], "file_reads": [], "file_writes": [], "parameters": {}, "plots": []}
            else:
                mined = mine_python_source(clean_source)
                io_summary = _python_io_with_context(clean_source, known_values)
                mined["file_reads"] = sorted(dict.fromkeys((mined.get("file_reads", []) or []) + io_summary["file_reads"]))
                mined["file_writes"] = sorted(dict.fromkeys((mined.get("file_writes", []) or []) + io_summary["file_writes"]))
                mined["assignments"] = (mined.get("assignments", []) or []) + io_summary["assignments"]
                mined["parameters"] = {**(mined.get("parameters", {}) or {}), **io_summary["parameters"]}
                known_values.update(io_summary["parameters"])
                if io_summary["hidden_state"]:
                    _add_risk(policy, "hidden_state")
            record.update({key: mined.get(key, record.get(key)) for key in record if key in mined})
            if parameter_cell:
                parameters.update({key: value for key, value in record["parameters"].items() if isinstance(value, (str, int, float, bool)) or value is None})
                known_values.update(parameters)
            flow = infer_object_flow(command_or_code) if language == "python" else {"input_objects": [], "output_objects": []}
            code_preview = command_or_code.strip().splitlines()[0] if command_or_code.strip() else "Empty code cell"
            step_id = f"tutorial_001:cell_{index:03d}"
            if command_or_code.strip():
                function_calls = [call["name"] if isinstance(call, dict) else str(call) for call in record["function_calls"]]
                steps.append(
                    {
                        "id": step_id,
                        "step_id": step_id,
                        "name": f"Notebook cell {index}",
                        "description": code_preview,
                        "source": f"{notebook_path}:cell:{index}",
                        "source_type": "tutorial_notebook",
                        "evidence_id": f"{notebook_path.name}:cell:{index}",
                        "language": language,
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
                        "figures": [call["name"] if isinstance(call, dict) else str(call) for call in record["plots"]],
                        "bio_signals": classify_bio_signals(command_or_code, record["function_calls"]),
                        "command_or_code": command_or_code,
                        "confidence": "high" if language in {"python", "r"} else "low",
                    }
                )
        elif record["cell_type"] == "markdown" and title is None:
            for line in source.splitlines():
                if line.strip().startswith("#"):
                    title = line.strip().lstrip("#").strip()
                    break
        cells.append(record)
    policy["risks"] = sorted(policy["risks"])
    return {
        "path": str(notebook_path),
        "title": title,
        "language": "python",
        "cells": cells,
        "steps": steps,
        "workflow_steps": steps,
        "parameters": parameters,
        "execution_policy": policy,
    }


def _cell_magic(source: str) -> dict[str, str] | None:
    match = CELL_MAGIC_RE.match(source)
    if not match:
        return None
    return {"magic": match.group(1), "body": match.group(2)}


def _split_python_magics(source: str) -> tuple[list[str], list[dict[str, str]], str]:
    shell_lines = []
    line_magics = []
    clean_lines = []
    cell_magic = _cell_magic(source)
    if cell_magic:
        if cell_magic["magic"].lower() in {"r", "bash", "sh"}:
            return shell_lines, line_magics, ""
        if cell_magic["magic"].lower() in PYTHON_WRAPPER_CELL_MAGICS:
            return shell_lines, line_magics, cell_magic["body"]
        return shell_lines, line_magics, ""
    for line in source.splitlines():
        shell = SHELL_LINE_RE.match(line)
        if shell:
            shell_lines.append(shell.group(1).strip())
            continue
        magic = LINE_MAGIC_RE.match(line)
        if magic:
            line_magics.append({"magic": magic.group(1), "args": magic.group(2).strip()})
            continue
        clean_lines.append(line)
    return shell_lines, line_magics, "\n".join(clean_lines) + ("\n" if clean_lines else "")


def _looks_like_parameter_cell(source: str, index: int) -> bool:
    if index != 0:
        return False
    mined = mine_python_source(source)
    return bool(mined.get("parameters")) and not mined.get("function_calls")


def _record_output_policy(index: int, outputs: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    for output in outputs:
        data = output.get("data", {}) if isinstance(output, dict) else {}
        for mime, value in data.items():
            size = len(value) if isinstance(value, str) else len(json.dumps(value))
            if mime.startswith("image/") and size > 100_000:
                policy["large_outputs"].append({"cell": index, "mime": mime, "size": size})
                _add_risk(policy, "large_output")
            elif size > 200_000:
                policy["large_outputs"].append({"cell": index, "mime": mime, "size": size})
                _add_risk(policy, "large_output")


def _record_command_risks(command: str, policy: dict[str, Any]) -> None:
    lower = command.lower()
    if any(word in lower for word in INSTALL_WORDS):
        _add_risk(policy, "install_command")
    if any(word in lower for word in NETWORK_WORDS):
        _add_risk(policy, "network_download")
    if re.search(r">\s*\S+", command):
        _add_risk(policy, "shell_file_write")


def _add_risk(policy: dict[str, Any], risk: str) -> None:
    if risk not in policy["risks"]:
        policy["risks"].append(risk)


def _python_io_with_context(source: str, context: dict[str, Any]) -> dict[str, Any]:
    summary = {"file_reads": [], "file_writes": [], "parameters": {}, "assignments": [], "hidden_state": False}
    if not source.strip():
        return summary
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return summary
    values = dict(context)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = _resolve_py_value(node.value, values)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        summary["parameters"][target.id] = value
                    summary["assignments"].append({"name": target.id, "lineno": node.lineno, "value": value})
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if not name:
                continue
            short = name.split(".")[-1]
            if not node.args:
                continue
            first = _resolve_py_value(node.args[0], values)
            if short in READ_NAMES and isinstance(first, str):
                summary["file_reads"].append(first)
            if short in WRITE_NAMES and isinstance(first, str):
                summary["file_writes"].append(first)
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id not in values:
                    summary["hidden_state"] = True
    summary["file_reads"] = sorted(dict.fromkeys(summary["file_reads"]))
    summary["file_writes"] = sorted(dict.fromkeys(summary["file_writes"]))
    return summary


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _resolve_py_value(node: ast.AST, values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_py_value(node.left, values)
        right = _resolve_py_value(node.right, values)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    try:
        return ast.literal_eval(node)
    except Exception:
        return None
