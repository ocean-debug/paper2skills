"""Index fetched or registered source files into compact parse records."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import DEFAULT_MAX_INDEX_BYTES, DEFAULT_MAX_INDEX_FILES, SCHEMA_VERSION, TEXT_FILE_SUFFIXES


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def decode_text(path: Path, max_bytes: int) -> str | None:
    if path.stat().st_size > max_bytes:
        return None
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def detect_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".r", ".R"}:
        return "r"
    if suffix == ".ipynb":
        return "notebook"
    if suffix in {".md", ".rst"}:
        return "markdown"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".yaml", ".yml", ".toml", ".json"}:
        return "config"
    return "text"


def safe_unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    pieces = []
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        annotation = safe_unparse(arg.annotation)
        if annotation:
            text += f": {annotation}"
        if default is not None:
            text += f"={safe_unparse(default)}"
        pieces.append(text)
    if node.args.vararg:
        text = "*" + node.args.vararg.arg
        annotation = safe_unparse(node.args.vararg.annotation)
        if annotation:
            text += f": {annotation}"
        pieces.append(text)
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        annotation = safe_unparse(arg.annotation)
        if annotation:
            text += f": {annotation}"
        if default is not None:
            text += f"={safe_unparse(default)}"
        pieces.append(text)
    if node.args.kwarg:
        text = "**" + node.args.kwarg.arg
        annotation = safe_unparse(node.args.kwarg.annotation)
        if annotation:
            text += f": {annotation}"
        pieces.append(text)
    return f"{node.name}({', '.join(pieces)})"


def doc_summary(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return " ".join(doc.strip().split())[:240]


def string_values(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for element in node.elts:
            values.extend(string_values(element))
        return values
    return []


def branch_parameter_values(function_node: ast.AST, param_names: set[str]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id not in param_names:
            continue
        for comparator in node.comparators:
            for value in string_values(comparator):
                bucket = values.setdefault(node.left.id, [])
                if value not in bucket:
                    bucket.append(value)
    return values


def parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    params = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    names = {param.arg for param in params}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def function_record(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    owner: str | None = None,
) -> dict[str, Any]:
    qualname = f"{owner}.{node.name}" if owner else node.name
    return {
        "name": node.name,
        "qualname": qualname,
        "kind": "method" if owner else "function",
        "signature": signature_text(node),
        "returns": safe_unparse(node.returns),
        "docstring_summary": doc_summary(node),
        "branch_parameter_values": branch_parameter_values(node, parameter_names(node)),
        "decorators": [text for text in (safe_unparse(item) for item in node.decorator_list) if text],
        "is_async": isinstance(node, ast.AsyncFunctionDef),
    }


def parse_python(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {
            "parse_status": "syntax_error",
            "functions": [],
            "classes": [],
            "imports": [],
            "api_calls": [],
            "function_records": [],
            "class_records": [],
        }
    functions = []
    classes = []
    imports = []
    function_records = []
    class_records = []
    api_calls = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
            function_records.append(function_record(node))
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
            methods = [
                function_record(child, owner=node.name)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            functions.extend(method["name"] for method in methods)
            function_records.extend(methods)
            class_records.append(
                {
                    "name": node.name,
                    "qualname": node.name,
                    "docstring_summary": doc_summary(node),
                    "method_count": len(methods),
                    "methods": [method["qualname"] for method in methods[:40]],
                    "bases": [text for text in (safe_unparse(item) for item in node.bases) if text],
                }
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name:
                api_calls.append(name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return {
        "parse_status": "parsed",
        "functions": sorted(set(functions))[:80],
        "classes": sorted(set(classes))[:80],
        "imports": sorted(set(imports))[:80],
        "api_calls": sorted(set(api_calls))[:120],
        "function_records": function_records[:80],
        "class_records": class_records[:80],
    }


def parse_notebook(text: str) -> dict[str, Any]:
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_status": "json_error", "code_cell_count": 0, "markdown_cell_count": 0}
    code_cells = []
    markdown_cells = 0
    for cell in notebook.get("cells", []):
        source = cell.get("source") or []
        source_text = "".join(source) if isinstance(source, list) else str(source)
        if cell.get("cell_type") == "code":
            code_cells.append(source_text)
        elif cell.get("cell_type") == "markdown":
            markdown_cells += 1
    joined = "\n".join(code_cells)
    return {
        "parse_status": "parsed",
        "code_cell_count": len(code_cells),
        "markdown_cell_count": markdown_cells,
        "imports": sorted(set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", joined, flags=re.M)))[:80],
        "api_calls": sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_\.]+)\(", joined)))[:120],
    }


def parse_markdown_like(text: str) -> dict[str, Any]:
    headings = re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", text, flags=re.M)
    code_fences = re.findall(r"```([A-Za-z0-9_+-]*)", text)
    return {
        "parse_status": "parsed",
        "headings": [heading.strip()[:160] for heading in headings[:80]],
        "code_fence_languages": sorted(set(lang or "plain" for lang in code_fences))[:40],
    }


def parse_file(path: Path, root: Path, evidence_id: str, max_bytes: int) -> dict[str, Any] | None:
    if path.suffix not in TEXT_FILE_SUFFIXES and path.suffix.lower() not in TEXT_FILE_SUFFIXES:
        return None
    text = decode_text(path, max_bytes)
    if text is None:
        return {
            "evidence_id": evidence_id,
            "path": str(path),
            "relative_path": str(path.relative_to(root)),
            "kind": detect_kind(path),
            "status": "skipped_too_large_or_binary",
            "bytes": path.stat().st_size,
        }
    kind = detect_kind(path)
    parsed: dict[str, Any]
    if kind == "python":
        parsed = parse_python(text)
    elif kind == "notebook":
        parsed = parse_notebook(text)
    elif kind in {"markdown", "html"}:
        parsed = parse_markdown_like(text)
    else:
        parsed = {"parse_status": "text_indexed"}
    return {
        "evidence_id": evidence_id,
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "kind": kind,
        "status": "indexed",
        "bytes": path.stat().st_size,
        "sha256": sha256_text(text),
        "terms": sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)))[:300],
        **parsed,
    }


def source_roots(fetch_report: dict[str, Any]) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for source in fetch_report.get("sources", []):
        evidence_id = str(source.get("evidence_id"))
        for key in ("extract_path", "local_path"):
            value = source.get(key)
            if value and Path(value).exists():
                roots.append((evidence_id, Path(value)))
                break
    return roots


def index_sources(
    fetch_report: dict[str, Any],
    max_files: int = DEFAULT_MAX_INDEX_FILES,
    max_bytes: int = DEFAULT_MAX_INDEX_BYTES,
) -> dict[str, Any]:
    records = []
    scanned = 0
    truncated = False
    for evidence_id, root in source_roots(fetch_report):
        paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in paths:
            if scanned >= max_files:
                truncated = True
                break
            scanned += 1
            parsed = parse_file(path, root.parent if root.is_file() else root, evidence_id, max_bytes)
            if parsed:
                records.append(parsed)
        if truncated:
            break
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "file_count": len(records),
        "scanned_file_count": scanned,
        "max_files": max_files,
        "max_index_bytes": max_bytes,
        "truncated": truncated,
        "files": records,
        "notes": [
            "Index records compact metadata and symbols, not long source excerpts.",
            "max_files is a global scan budget across all registered source roots.",
            "Source indexing does not execute code.",
        ],
    }
