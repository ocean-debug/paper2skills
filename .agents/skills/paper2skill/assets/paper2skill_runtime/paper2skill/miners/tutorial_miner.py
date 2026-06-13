from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_local_path
from paper2skill.miners.notebook_miner import mine_notebook
from paper2skill.miners.script_miner import mine_script
from paper2skill.miners.tutorial_scanner import scan_tutorial_candidates


def mine_tutorials(paths: list[str | Path], base_dir: str | Path | None = None) -> dict[str, Any]:
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    traces = []
    workflow_steps = []
    for value in paths:
        path = Path(value)
        public_path = public_local_path(path, base)
        if not path.exists():
            traces.append({"path": public_path, "error": "missing"})
            continue
        if path.suffix.lower() == ".ipynb":
            trace = mine_notebook(path)
        else:
            trace = mine_script(path)
        trace = _public_tutorial_trace(trace, public_path)
        traces.append(trace)
        workflow_steps.extend(trace.get("workflow_steps", []))
    return {"tutorials": traces, "workflow_steps": workflow_steps, "steps": workflow_steps}


def mine_repo_tutorials(repo_root: str | Path, tutorial_filter: str | None = None) -> dict[str, Any]:
    scan = scan_tutorial_candidates(repo_root)
    candidates = scan["candidates"]
    if tutorial_filter:
        filtered = []
        for item in candidates:
            if tutorial_filter_matches(item, tutorial_filter):
                filtered.append(item)
            else:
                item.include_in_tools = False
                item.reason = "excluded_by_filter"
        candidates = filtered
    included = []
    seen_paths = set()
    for item in candidates:
        if not item.include_in_tools:
            continue
        source_path = item.source_path or item.path.split("#", 1)[0]
        if source_path in seen_paths:
            continue
        seen_paths.add(source_path)
        included.append(Path(repo_root) / source_path)
    trace = mine_tutorials(included, base_dir=repo_root)
    trace["tutorial_candidates"] = [item.__dict__ for item in candidates]
    report = dict(scan["report"])
    report["filter"] = tutorial_filter
    report["included_after_filter"] = sum(1 for item in candidates if item.include_in_tools)
    trace["tutorial_scanner_report"] = report
    return trace


def tutorial_filter_matches(item: Any, tutorial_filter: str) -> bool:
    needles = [part.strip().lower() for part in tutorial_filter.split("|") if part.strip()]
    if not needles:
        return True
    title = (item.title or "").lower()
    path = item.path.lower()
    source_path = (item.source_path or "").lower()
    haystack = "\n".join([path, source_path, title])
    return any(needle in haystack for needle in needles)


def _public_tutorial_trace(trace: dict[str, Any], public_path: str | None) -> dict[str, Any]:
    clean = dict(trace)
    clean["path"] = public_path
    clean_steps = []
    for step in clean.get("workflow_steps", []):
        clean_step = dict(step)
        clean_step["source"] = public_path
        clean_steps.append(clean_step)
    clean["workflow_steps"] = clean_steps
    clean["steps"] = clean_steps
    return clean
