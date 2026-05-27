from __future__ import annotations

import ast
from typing import Any


READ_NAMES = {"open", "read_csv", "read_table", "read_excel", "read_h5ad", "load", "loadtxt"}
WRITE_NAMES = {"to_csv", "write", "write_csv", "save", "savefig", "save_npz", "dump"}
PLOT_NAMES = {"plot", "scatter", "hist", "imshow", "show", "savefig"}


def call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def mine_python_source(source: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "imports": [],
        "assignments": [],
        "function_calls": [],
        "functions": [],
        "classes": [],
        "file_reads": [],
        "file_writes": [],
        "parameters": {},
        "plots": [],
    }
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        result["parse_error"] = str(exc)
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}" if module else alias.name)
        elif isinstance(node, ast.FunctionDef):
            result["functions"].append(
                {
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node),
                }
            )
        elif isinstance(node, ast.ClassDef):
            result["classes"].append({"name": node.name, "lineno": node.lineno, "docstring": ast.get_docstring(node)})
        elif isinstance(node, ast.Assign):
            targets = [call_name(target) for target in node.targets]
            value = literal_value(node.value)
            for target in [t for t in targets if t]:
                result["assignments"].append({"name": target, "lineno": node.lineno, "value": value})
                if isinstance(value, (str, int, float, bool)) or value is None:
                    result["parameters"][target] = value
        elif isinstance(node, ast.Call):
            name = call_name(node.func)
            if not name:
                continue
            args = [literal_value(arg) for arg in node.args]
            record = {"name": name, "lineno": getattr(node, "lineno", None), "args": args}
            result["function_calls"].append(record)
            short_name = name.split(".")[-1]
            if short_name in READ_NAMES and args and isinstance(args[0], str):
                result["file_reads"].append(args[0])
            if short_name in WRITE_NAMES and args and isinstance(args[0], str):
                result["file_writes"].append(args[0])
            if short_name in PLOT_NAMES:
                result["plots"].append(record)
    return result
