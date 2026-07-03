"""Static interface inspection for parsed Python source files."""

from __future__ import annotations

import ast
from pathlib import Path
from copy import deepcopy
from typing import Any

from common import now_utc, read_text, slugify
from constants import SCHEMA_VERSION


def safe_unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def parameter_records(args: ast.arguments) -> list[dict[str, Any]]:
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    params = []
    for arg, default in zip(positional, defaults):
        params.append(
            {
                "name": arg.arg,
                "kind": "positional_or_keyword",
                "required": default is None,
                "default": safe_unparse(default),
                "annotation": safe_unparse(arg.annotation),
            }
        )
    if args.vararg:
        params.append(
            {
                "name": args.vararg.arg,
                "kind": "vararg",
                "required": False,
                "default": None,
                "annotation": safe_unparse(args.vararg.annotation),
            }
        )
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(
            {
                "name": arg.arg,
                "kind": "keyword_only",
                "required": default is None,
                "default": safe_unparse(default),
                "annotation": safe_unparse(arg.annotation),
            }
        )
    if args.kwarg:
        params.append(
            {
                "name": args.kwarg.arg,
                "kind": "kwarg",
                "required": False,
                "default": None,
                "annotation": safe_unparse(args.kwarg.annotation),
            }
        )
    return params


def string_values(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = []
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


def signature_text(name: str, params: list[dict[str, Any]]) -> str:
    pieces = []
    for param in params:
        text = param["name"]
        if param.get("annotation"):
            text += f": {param['annotation']}"
        if not param.get("required") and param.get("default") is not None:
            text += f"={param['default']}"
        if param.get("kind") == "vararg":
            text = "*" + text
        elif param.get("kind") == "kwarg":
            text = "**" + text
        pieces.append(text)
    return f"{name}({', '.join(pieces)})"


def doc_summary(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return " ".join(doc.strip().split())[:240]


def api_lookup(api_grounding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for candidate in api_grounding.get("api_candidates", []):
        symbol = str(candidate.get("symbol") or "")
        if not symbol:
            continue
        lookup.setdefault(symbol, candidate)
        lookup.setdefault(symbol.split(".")[-1], candidate)
    return lookup


def cards_by_record(evidence_cards: dict[str, Any] | None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if not evidence_cards:
        return grouped
    for card in evidence_cards.get("cards", []):
        key = (str(card.get("source_evidence_id")), str(card.get("source_path")))
        grouped.setdefault(key, []).append(card)
    return grouped


def fallback_tasks_and_refs(cards: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    tasks: list[str] = []
    refs: list[str] = []
    for card in cards:
        for task_type in card.get("task_type_candidates", []):
            if task_type not in tasks:
                tasks.append(task_type)
        if card.get("evidence_card_id"):
            refs.append(str(card["evidence_card_id"]))
    return tasks, refs[:8]


def inspect_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    record: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
    record_cards: list[dict[str, Any]],
    owner: str | None = None,
) -> dict[str, Any]:
    qualname = f"{owner}.{node.name}" if owner else node.name
    params = parameter_records(node.args)
    param_names = {param["name"] for param in params}
    candidate = lookup.get(qualname) or lookup.get(node.name) or {}
    fallback_tasks, fallback_refs = fallback_tasks_and_refs(record_cards)
    return {
        "interface_id": f"interface:{slugify(qualname)}:{slugify(str(record.get('relative_path')))}",
        "kind": "method" if owner else "function",
        "name": node.name,
        "qualname": qualname,
        "signature": signature_text(node.name, params),
        "parameters": params,
        "returns": safe_unparse(node.returns),
        "docstring_summary": doc_summary(node),
        "branch_parameter_values": branch_parameter_values(node, param_names),
        "source_evidence_id": record.get("evidence_id"),
        "source_path": record.get("relative_path"),
        "task_type_candidates": candidate.get("task_type_candidates") or fallback_tasks,
        "evidence_refs": candidate.get("evidence_refs") or fallback_refs,
        "confidence": "static_ast",
    }


def inspect_python_record(
    record: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
    record_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    path = Path(str(record.get("path") or ""))
    if not path.exists() or not path.is_file():
        return []
    try:
        tree = ast.parse(read_text(path))
    except Exception:
        return []

    interfaces: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            interfaces.append(inspect_function(node, record, lookup, record_cards))
        elif isinstance(node, ast.ClassDef):
            class_candidate = lookup.get(node.name) or {}
            fallback_tasks, fallback_refs = fallback_tasks_and_refs(record_cards)
            methods = [
                inspect_function(child, record, lookup, record_cards, owner=node.name)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            interfaces.append(
                {
                    "interface_id": f"interface:{slugify(node.name)}:{slugify(str(record.get('relative_path')))}",
                    "kind": "class",
                    "name": node.name,
                    "qualname": node.name,
                    "signature": node.name,
                    "parameters": [],
                    "returns": None,
                    "docstring_summary": doc_summary(node),
                    "branch_parameter_values": {},
                    "source_evidence_id": record.get("evidence_id"),
                    "source_path": record.get("relative_path"),
                    "task_type_candidates": class_candidate.get("task_type_candidates") or fallback_tasks,
                    "evidence_refs": class_candidate.get("evidence_refs") or fallback_refs,
                    "method_interfaces": [method["interface_id"] for method in methods],
                    "confidence": "static_ast",
                }
            )
            interfaces.extend(methods)
    return interfaces


def build_interface_grounding(
    request: dict[str, Any],
    source_index: dict[str, Any],
    api_grounding: dict[str, Any],
    evidence_cards: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lookup = api_lookup(api_grounding)
    record_cards = cards_by_record(evidence_cards)
    interfaces: list[dict[str, Any]] = []
    for record in source_index.get("files", []):
        if record.get("status") == "indexed" and record.get("kind") == "python":
            key = (str(record.get("evidence_id")), str(record.get("relative_path")))
            interfaces.extend(inspect_python_record(record, lookup, record_cards.get(key, [])))

    by_task_type: dict[str, dict[str, Any]] = {}
    for interface in interfaces:
        for task_type in interface.get("task_type_candidates", []):
            bucket = by_task_type.setdefault(task_type, {"interfaces": [], "evidence_refs": []})
            bucket["interfaces"].append(interface["interface_id"])
            for ref in interface.get("evidence_refs", []):
                if ref not in bucket["evidence_refs"]:
                    bucket["evidence_refs"].append(ref)

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "interface_count": len(interfaces),
        "interfaces": interfaces,
        "by_task_type": by_task_type,
        "notes": [
            "Interface inspection uses Python AST only and never imports package code.",
            "Signatures, defaults, annotations, docstrings, and branch parameter values are review hints.",
        ],
    }


def attach_interface_hints(
    task_catalog: dict[str, Any],
    interface_grounding: dict[str, Any],
    limit: int = 8,
) -> dict[str, Any]:
    catalog = deepcopy(task_catalog)
    interface_lookup = {
        interface.get("interface_id"): interface for interface in interface_grounding.get("interfaces", [])
    }
    for task in catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        refs = interface_grounding.get("by_task_type", {}).get(task_type, {}).get("interfaces", [])[:limit]
        observed = []
        for ref in refs:
            interface = interface_lookup.get(ref)
            if not interface:
                continue
            observed.append(
                {
                    "interface_ref": ref,
                    "signature": interface.get("signature"),
                    "source_path": interface.get("source_path"),
                    "docstring_summary": interface.get("docstring_summary"),
                    "branch_parameter_values": interface.get("branch_parameter_values", {}),
                }
            )
        task["interface_refs_observed"] = refs
        task.setdefault("output_contract", {})["interface_observed"] = observed
    return catalog
