"""Static source and tutorial grounding for the Paper2Skills MVP."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Iterator

from common import (
    Paper2SkillsError,
    as_list,
    dump_yaml,
    load_yaml,
    stable_id,
    unique_strings,
    write_text,
)


TEXT_EXTENSIONS = {".md", ".rst", ".txt", ".py", ".ipynb"}
IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
CALL_PATTERN = re.compile(
    r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\("
)
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _iter_files(path: Path, max_files: int) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    count = 0
    for candidate in sorted(path.rglob("*")):
        if count >= max_files:
            return
        if not candidate.is_file() or candidate.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(part in IGNORED_PARTS for part in candidate.parts):
            continue
        count += 1
        yield candidate


def _read_text(path: Path, max_bytes: int) -> tuple[str, bool]:
    size = path.stat().st_size
    truncated = size > max_bytes
    with path.open("rb") as stream:
        raw = stream.read(max_bytes)
    return raw.decode("utf-8", errors="replace"), truncated


def _notebook_text(raw: str) -> str:
    try:
        notebook = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    cells = notebook.get("cells", []) if isinstance(notebook, dict) else []
    chunks: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        source = cell.get("source", [])
        if isinstance(source, list):
            chunks.append("".join(str(item) for item in source))
        elif isinstance(source, str):
            chunks.append(source)
    return "\n\n".join(chunks)


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    arguments: list[str] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults_offset = len(positional) - len(node.args.defaults)
    for index, argument in enumerate(positional):
        rendered = argument.arg
        if index >= defaults_offset:
            default = node.args.defaults[index - defaults_offset]
            try:
                rendered += f"={ast.unparse(default)}"
            except Exception:
                rendered += "=<default>"
        arguments.append(rendered)
    if node.args.vararg:
        arguments.append(f"*{node.args.vararg.arg}")
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        rendered = argument.arg
        if default is not None:
            try:
                rendered += f"={ast.unparse(default)}"
            except Exception:
                rendered += "=<default>"
        arguments.append(rendered)
    if node.args.kwarg:
        arguments.append(f"**{node.args.kwarg.arg}")
    return f"({', '.join(arguments)})"


def _python_symbols(path: Path, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    symbols: list[dict[str, Any]] = []
    module = path.stem
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            symbols.append(
                {
                    "symbol": f"{module}.{node.name}",
                    "signature": _signature(node),
                    "line": node.lineno,
                    "summary": (ast.get_docstring(node) or "").split("\n", 1)[0][
                        :240
                    ],
                }
            )
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            symbols.append(
                {
                    "symbol": f"{module}.{node.name}",
                    "signature": "class",
                    "line": node.lineno,
                    "summary": (ast.get_docstring(node) or "").split("\n", 1)[0][
                        :240
                    ],
                }
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
                    symbols.append(
                        {
                            "symbol": f"{module}.{node.name}.{child.name}",
                            "signature": _signature(child),
                            "line": child.lineno,
                            "summary": (ast.get_docstring(child) or "").split(
                                "\n", 1
                            )[0][:240],
                        }
                    )
    return symbols


def _source_kind(path: Path, tutorial_roots: set[Path]) -> str:
    resolved = path.resolve()
    for root in tutorial_roots:
        if root == resolved or (root.is_dir() and root in resolved.parents):
            return "tutorial"
    if path.suffix.lower() == ".py":
        return "source"
    return "documentation"


def _public_location(path: Path, roots: list[Path], kind: str) -> str:
    """Return a portable provenance label without a machine-specific root."""

    resolved = path.resolve()
    for root in roots:
        if root.is_file() and root.resolve() == resolved:
            return f"{kind}:{root.name}"
        if root.is_dir():
            try:
                relative = resolved.relative_to(root.resolve())
            except ValueError:
                continue
            return f"{kind}:{relative.as_posix()}"
    return f"{kind}:{path.name}"


def _prefix(kind: str) -> str:
    return {
        "tutorial": "E-TUT",
        "source": "E-SRC",
        "documentation": "E-DOC",
        "paper": "E-PAPER",
        "execution": "E-RUN",
    }[kind]


def collect_grounding(run_dir: Path) -> dict[str, Any]:
    """Collect compact static grounding from the normalized run request."""

    request = load_yaml(run_dir / "request.yaml")
    max_files = int(request.get("max_files", 500))
    max_bytes = int(request.get("max_file_bytes", 250_000))
    if max_files < 1 or max_bytes < 1:
        raise Paper2SkillsError("max_files and max_file_bytes must be positive")

    source_roots = [Path(item).expanduser().resolve() for item in as_list(request.get("source_paths"))]
    tutorial_roots = {
        Path(item).expanduser().resolve()
        for item in as_list(request.get("tutorial_paths"))
    }
    missing_paths = [
        str(path) for path in [*source_roots, *tutorial_roots] if not path.exists()
    ]

    evidence: list[dict[str, Any]] = []
    grounded_apis: list[str] = []
    indexed_files: list[dict[str, Any]] = []
    seen_files: set[Path] = set()

    for root in [*source_roots, *sorted(tutorial_roots)]:
        if not root.exists():
            continue
        for path in _iter_files(root, max_files):
            resolved = path.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            text, truncated = _read_text(path, max_bytes)
            if path.suffix.lower() == ".ipynb":
                text = _notebook_text(text)
            kind = _source_kind(path, tutorial_roots)
            public_location = _public_location(
                path,
                [*source_roots, *sorted(tutorial_roots)],
                kind,
            )
            record: dict[str, Any] = {
                "path": str(resolved),
                "kind": kind,
                "bytes_read": len(text.encode("utf-8")),
                "truncated": truncated,
            }

            symbols = _python_symbols(path, text) if path.suffix.lower() == ".py" else []
            record["symbol_count"] = len(symbols)
            for symbol in symbols:
                evidence_id = stable_id(
                    _prefix("source"), resolved, symbol["symbol"], symbol["line"]
                )
                evidence.append(
                    {
                        "id": evidence_id,
                        "kind": "source",
                        "location": f"{resolved}:{symbol['line']}",
                        "public_location": f"{public_location}:{symbol['line']}",
                        "claim_type": "public_api",
                        **symbol,
                    }
                )
                grounded_apis.append(symbol["symbol"])
                symbol_parts = symbol["symbol"].split(".")
                if len(symbol_parts) >= 2:
                    grounded_apis.append(".".join(symbol_parts[-2:]))
                if symbol.get("signature") == "class":
                    grounded_apis.append(symbol_parts[-1])

            calls = unique_strings(match.group(1) for match in CALL_PATTERN.finditer(text))
            headings = unique_strings(HEADING_PATTERN.findall(text))[:20]
            if kind != "source" or calls or headings:
                evidence_id = stable_id(_prefix(kind), resolved, "file")
                evidence.append(
                    {
                        "id": evidence_id,
                        "kind": kind,
                        "location": str(resolved),
                        "public_location": public_location,
                        "claim_type": "workflow_or_usage" if calls else "source_context",
                        "summary": headings[0] if headings else path.name,
                        "headings": headings,
                        "api_calls": calls,
                        "truncated": truncated,
                    }
                )
                grounded_apis.extend(calls)
            indexed_files.append(record)

    external_groups = (
        ("tutorial", "tutorial_urls"),
        ("documentation", "documentation_urls"),
        ("paper", "paper_urls"),
    )
    for kind, field in external_groups:
        for url in unique_strings(as_list(request.get(field))):
            evidence.append(
                {
                    "id": stable_id(_prefix(kind), url),
                    "kind": kind,
                    "location": url,
                    "claim_type": "external_reference_uninspected",
                    "summary": "Registered external source; content must be inspected before use.",
                }
            )

    repo_url = str(request.get("repo_url") or "").strip()
    if repo_url:
        evidence.append(
            {
                "id": stable_id("E-SRC", repo_url, request.get("source_revision")),
                "kind": "source",
                "location": repo_url,
                "claim_type": "external_repository_uninspected",
                "summary": (
                    "Registered official repository reference; obtain and inspect the "
                    f"requested revision {request.get('source_revision', 'unresolved')} before use."
                ),
            }
        )

    report = {
        "schema_version": "paper2skills.source-report.v1",
        "package_name": request.get("package_name"),
        "source_revision": request.get("source_revision", "unresolved"),
        "evidence_priority": ["tutorial", "source", "documentation", "paper"],
        "static_only": True,
        "missing_paths": missing_paths,
        "indexed_files": indexed_files,
        "grounded_apis": unique_strings(grounded_apis),
        "requested_key_apis": unique_strings(as_list(request.get("key_apis"))),
        "evidence": evidence,
        "limitations": [
            "External URLs were registered but not fetched or interpreted by the static grounder.",
            "AST signatures do not prove that a workflow executes successfully.",
            "Tutorial API call extraction is lexical and requires agent review.",
        ],
    }
    dump_yaml(run_dir / "source_report.yaml", report)
    dump_yaml(
        run_dir / "evidence.yaml",
        {
            "schema_version": "paper2skills.evidence.v1",
            "evidence": evidence,
        },
    )
    write_text(run_dir / "agent_packet.md", _agent_packet(request, report))
    return report


def _agent_packet(request: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# Paper2Skills Agent Synthesis Packet",
        "",
        f"Package: `{request.get('package_name')}`",
        f"Requested source revision: `{request.get('source_revision', 'unresolved')}`",
        "",
        "## Required Action",
        "",
        "Read `source_report.yaml`, inspect the registered official sources, and fill",
        "`skill_spec.yaml`. Treat external URL records as uninspected until their",
        "content has actually been read. Do not add claims from URL titles alone.",
        "",
        "For every task, provide selection, non-selection, inputs, metadata,",
        "preflight, workflow, grounded API sequence, outputs, refusals, technical",
        "validation, biological boundaries, reuse, troubleshooting, and evidence IDs.",
        "",
        "Do not split tasks by tutorial, notebook, demo, stage, plot, or parameter.",
        "",
        "## Grounding Summary",
        "",
        f"- Indexed files: {len(report.get('indexed_files', []))}",
        f"- Evidence records: {len(report.get('evidence', []))}",
        f"- Grounded API candidates: {len(report.get('grounded_apis', []))}",
        f"- Missing local paths: {len(report.get('missing_paths', []))}",
        "",
        "## Stop Conditions",
        "",
        "Stop and ask for evidence when a task-defining input, biological metadata",
        "semantic, or supported API cannot be established. Leave verification as",
        "`source_grounded` unless task-specific execution evidence is supplied.",
    ]
    return "\n".join(lines)
