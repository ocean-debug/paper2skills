"""Audit rendered API surface claims against parsed API/interface grounding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


PY_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\(")
INLINE_API_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)(?:\([^`]*\))?`")
FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", flags=re.S)
IGNORED_INLINE_PREFIXES = ("references.",)
IGNORED_CALL_PREFIXES = ("Path.", "os.path.", "dict.", "list.", "set.", "str.")


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    symbol: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = path
    if symbol:
        item["symbol"] = symbol
    findings.append(item)


def markdown_texts(skill_dir: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*.md")):
        if path.is_file():
            texts[str(path.relative_to(skill_dir)).replace("\\", "/")] = read_text(path)
    return texts


def allowed_api_symbols(api_grounding: dict[str, Any], interface_grounding: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for candidate in api_grounding.get("api_candidates", []):
        symbol = str(candidate.get("symbol") or "").strip()
        if symbol:
            symbols.add(symbol)
            symbols.add(symbol.split(".")[-1])
    for interface in interface_grounding.get("interfaces", []):
        signature = str(interface.get("signature") or "").strip()
        qualname = str(interface.get("qualname") or "").strip()
        name = str(interface.get("name") or "").strip()
        for value in (qualname, name, signature.split("(", 1)[0]):
            if value:
                symbols.add(value)
                symbols.add(value.split(".")[-1])
    return {symbol for symbol in symbols if symbol}


def is_allowed(symbol: str, allowed: set[str]) -> bool:
    short = symbol.split(".")[-1]
    return symbol in allowed or short in allowed


def is_ignored_call(symbol: str) -> bool:
    return any(symbol.startswith(prefix) for prefix in IGNORED_CALL_PREFIXES)


def is_ignored_inline(symbol: str) -> bool:
    return any(symbol.startswith(prefix) for prefix in IGNORED_INLINE_PREFIXES)


def audit_api_surface(
    skill_dir: Path,
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
    task_catalog: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    texts = markdown_texts(skill_dir)
    allowed = allowed_api_symbols(api_grounding, interface_grounding)
    code_fence_calls: list[dict[str, str]] = []
    inline_mentions: list[dict[str, str]] = []

    for rel, text in texts.items():
        for language, fence in FENCE_RE.findall(text):
            if language.lower() in {"", "text", "yaml", "json", "toml", "bash", "shell", "sh"}:
                continue
            for call in sorted(set(PY_CALL_RE.findall(fence))):
                code_fence_calls.append({"path": rel, "symbol": call})
                if not is_ignored_call(call) and not is_allowed(call, allowed):
                    add_finding(
                        findings,
                        "error",
                        "ungrounded_code_fence_api",
                        "Code fence contains an API call not found in API/interface grounding.",
                        rel,
                        call,
                    )
        for symbol in sorted(set(INLINE_API_RE.findall(text))):
            if is_ignored_inline(symbol):
                continue
            inline_mentions.append({"path": rel, "symbol": symbol})
            if "." in symbol and not is_allowed(symbol, allowed):
                add_finding(
                    findings,
                    "warning",
                    "ungrounded_inline_api_mention",
                    "Inline API-like mention was not found in API/interface grounding.",
                    rel,
                    symbol,
                )

    requested_api_names = [str(name) for name in request.get("api_names", []) if name]
    grounded_requested = []
    missing_requested = []
    for name in requested_api_names:
        if is_allowed(name, allowed):
            grounded_requested.append(name)
        else:
            missing_requested.append(name)
            add_finding(
                findings,
                "warning",
                "requested_api_name_not_grounded",
                "Build request named an API that was not found in parsed API/interface grounding.",
                symbol=name,
            )

    task_types = [str(task.get("task_type")) for task in task_catalog.get("tasks", []) if task.get("task_type")]
    by_task = api_grounding.get("by_task_type", {})
    task_without_surface = [
        task_type
        for task_type in task_types
        if not by_task.get(task_type, {}).get("api_candidates")
        and not interface_grounding.get("by_task_type", {}).get(task_type, {}).get("interfaces")
    ]
    for task_type in task_without_surface:
        add_finding(
            findings,
            "warning",
            "task_without_api_surface",
            "Task_type has no linked API candidate or inspected interface; generated guidance must stay conservative.",
            symbol=task_type,
        )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "allowed_symbol_count": len(allowed),
        "code_fence_call_count": len(code_fence_calls),
        "inline_api_mention_count": len(inline_mentions),
        "requested_api_count": len(requested_api_names),
        "grounded_requested_api_names": grounded_requested,
        "missing_requested_api_names": missing_requested,
        "task_without_api_surface": task_without_surface,
        "findings": findings,
        "policy": [
            "Rendered code-fence API calls must be grounded in parsed API or interface evidence.",
            "Inline API-like mentions and request-provided API names are audited so generated skills do not overstate package surfaces.",
        ],
    }
