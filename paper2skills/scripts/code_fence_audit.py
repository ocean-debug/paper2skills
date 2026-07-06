"""Audit generated child-skill markdown for unsafe code/API claims."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import now_utc, read_text
from constants import SCHEMA_VERSION


PATH_SEPARATOR_RE = r"(?:/|" + re.escape(chr(92)) + ")"
MACHINE_PATH_RE = re.compile(r"(file://|[A-Za-z]:" + PATH_SEPARATOR_RE + r"|/home/|/Users/|/tmp/|" + re.escape(chr(92) * 2) + r")")
PY_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\(")


def markdown_files(skill_dir: Path) -> list[Path]:
    return [path for path in skill_dir.rglob("*.md") if path.is_file()]


def code_fences(text: str) -> list[str]:
    return [match.group(2) for match in re.finditer(r"```([A-Za-z0-9_+-]*)\n(.*?)```", text, flags=re.S)]


def allowed_api_symbols(api_grounding: dict[str, Any], interface_grounding: dict[str, Any]) -> set[str]:
    symbols = set()
    for candidate in api_grounding.get("api_candidates", []):
        symbol = str(candidate.get("symbol") or "")
        if symbol:
            symbols.add(symbol)
            symbols.add(symbol.split(".")[-1])
    for interface in interface_grounding.get("interfaces", []):
        signature = str(interface.get("signature") or "")
        qualname = str(interface.get("qualname") or "")
        name = str(interface.get("name") or "")
        for value in (qualname, name, signature.split("(", 1)[0]):
            if value:
                symbols.add(value)
                symbols.add(value.split(".")[-1])
    return symbols


def audit_child_skill_code_fences(
    skill_dir: Path,
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
) -> dict[str, Any]:
    findings = []
    allowed = allowed_api_symbols(api_grounding, interface_grounding)
    for path in markdown_files(skill_dir):
        text = read_text(path)
        rel = str(path.relative_to(skill_dir))
        if MACHINE_PATH_RE.search(text):
            findings.append(
                {
                    "severity": "error",
                    "code": "machine_path_leak",
                    "path": rel,
                    "message": "Generated child skill contains a machine-local path.",
                }
            )
        for fence in code_fences(text):
            for call in PY_CALL_RE.findall(fence):
                short = call.split(".")[-1]
                if call not in allowed and short not in allowed:
                    findings.append(
                        {
                            "severity": "warning",
                            "code": "ungrounded_code_fence_api",
                            "path": rel,
                            "symbol": call,
                            "message": "Code fence contains an API call not found in API/interface grounding.",
                        }
                    )
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "allowed_symbol_count": len(allowed),
        "findings": findings,
    }
