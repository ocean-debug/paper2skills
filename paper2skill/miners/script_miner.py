from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from paper2skill.miners.python_ast import classify_bio_signals, infer_object_flow, mine_python_source


R_LIBRARY_RE = re.compile(r"\b(?:library|require)\s*\(\s*['\"]?([A-Za-z0-9_.]+)['\"]?\s*\)")
R_FUNCTION_RE = re.compile(r"\b(?:(?P<package>[A-Za-z][A-Za-z0-9_.]*):::{0,1})?(?P<function>[A-Za-z][A-Za-z0-9_.]*)\s*\(")
R_ASSIGN_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.]*)\s*(?:<-|=)\s*(.+?)\s*$")
R_READ_RE = re.compile(r"\b(read\.[A-Za-z0-9_.]+|readRDS|read_h5ad)\s*\(\s*([A-Za-z][A-Za-z0-9_.]*|['\"][^'\"]+['\"])")
R_WRITE_RE = re.compile(r"\b(write\.[A-Za-z0-9_.]+|saveRDS|ggsave)\s*\((?:[^,\n]+,\s*)?([A-Za-z][A-Za-z0-9_.]*|['\"][^'\"]+['\"])")
R_FIGURE_RE = re.compile(r"\b(ggsave|pdf|png|jpeg|tiff|svg)\s*\(")
R_SOURCE_RE = re.compile(r"\bsource\s*\(\s*([^)]+)\)")
R_READ_NAMES = {"read.csv", "read.table", "read.delim", "readRDS", "read_h5ad", "Read10X"}
R_WRITE_NAMES = {"write.csv", "write.table", "saveRDS", "ggsave"}


def mine_r_source(source: str) -> dict[str, Any]:
    imports = R_LIBRARY_RE.findall(source)
    calls = []
    assignments = []
    parameters: dict[str, Any] = {}
    for lineno, line in enumerate(source.splitlines(), start=1):
        for match in R_FUNCTION_RE.finditer(line):
            package = match.group("package")
            function = match.group("function")
            if function not in {"if", "for", "while", "function"}:
                record = {"name": f"{package}::{function}" if package else function, "lineno": lineno, "function": function, "package": package}
                if package:
                    record["package"] = package
                    if package not in imports:
                        imports.append(package)
                calls.append(record)
        match = R_ASSIGN_RE.match(line)
        if match:
            name, value = match.groups()
            clean_value = _resolve_r_value(value, parameters)
            assignments.append({"name": name, "lineno": lineno, "value": clean_value})
            parameters[name] = clean_value
    file_reads = _r_call_paths(source, R_READ_NAMES, parameters, mode="read")
    file_reads.extend(_resolve_r_arg(match[1], parameters) for match in R_READ_RE.findall(source))
    file_writes = _r_call_paths(source, R_WRITE_NAMES, parameters, mode="write")
    file_writes.extend(_resolve_r_arg(match[1], parameters) for match in R_WRITE_RE.findall(source))
    source_files = [_resolve_r_value(match, parameters) for match in R_SOURCE_RE.findall(source)]
    return {
        "imports": imports,
        "functions": [],
        "top_level_steps": [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("#")],
        "function_calls": calls,
        "assignments": assignments,
        "parameters": parameters,
        "file_reads": sorted(dict.fromkeys(item for item in file_reads if item)),
        "file_writes": sorted(dict.fromkeys(item for item in file_writes if item)),
        "source_files": [item for item in source_files if isinstance(item, str)],
        "figures": R_FIGURE_RE.findall(source),
    }


def _resolve_r_arg(value: str, parameters: dict[str, Any]) -> str | None:
    resolved = _resolve_r_value(value, parameters)
    if isinstance(resolved, str):
        return resolved.strip().strip("'\"")
    return None


def _resolve_r_value(value: str, parameters: dict[str, Any]) -> Any:
    value = value.strip()
    if value.startswith("file.path(") and value.endswith(")"):
        inner = value[len("file.path(") : -1]
        parts = [_resolve_r_value(part, parameters) for part in _split_r_args(inner)]
        return "/".join(str(part).strip("/").strip("'\"") for part in parts if part is not None)
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return parameters.get(value, value.strip("'\""))


def _split_r_args(value: str) -> list[str]:
    args = []
    current = []
    quote: str | None = None
    depth = 0
    for char in value:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        args.append("".join(current).strip())
    return args


def _r_call_paths(source: str, names: set[str], parameters: dict[str, Any], mode: str) -> list[str]:
    paths = []
    for match in R_FUNCTION_RE.finditer(source):
        package = match.group("package")
        function = match.group("function")
        if function not in names:
            continue
        start = match.end()
        args_text = _balanced_call_args(source, start)
        if args_text is None:
            continue
        args = _split_r_args(args_text)
        if not args:
            continue
        index = 0
        if mode == "write" and function == "saveRDS" and len(args) > 1:
            index = 1
        target = _resolve_r_value(args[index], parameters)
        if isinstance(target, str):
            paths.append(target.strip("'\""))
    return paths


def _balanced_call_args(source: str, start: int) -> str | None:
    depth = 1
    quote: str | None = None
    chars = []
    for char in source[start:]:
        if quote:
            chars.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            chars.append(char)
        elif char == "(":
            depth += 1
            chars.append(char)
        elif char == ")":
            depth -= 1
            if depth == 0:
                return "".join(chars)
            chars.append(char)
        else:
            chars.append(char)
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
        "source_files": mined.get("source_files", []),
        "file_reads": mined.get("file_reads", []),
        "file_writes": mined.get("file_writes", []),
        "steps": steps,
        "workflow_steps": steps,
    }
