from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TutorialCandidate:
    path: str
    title: str | None
    file_type: str
    priority: int
    include_in_tools: bool
    reason: str
    signals: dict[str, bool]
    evidence_id: str


TUTORIAL_SUFFIXES = {".ipynb", ".md", ".rst", ".rmd", ".r", ".py"}
RICH_SUFFIXES = {".ipynb", ".md", ".rst", ".rmd"}
EXCLUDED_PARTS = {"tests", "test", "benchmark", "benchmarks", "perf", "profile", "legacy", "deprecated", "old", "templates"}
DEPRECATED_WORDS = {"legacy", "deprecated", "outdated", "old", "archive"}


def scan_tutorial_candidates(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TUTORIAL_SUFFIXES)
    has_rich = any(path.suffix.lower() in RICH_SUFFIXES and not is_excluded(path, root) for path in paths)
    candidates = []
    for index, path in enumerate(paths, start=1):
        rel = path.relative_to(root).as_posix()
        signals = candidate_signals(path, root)
        include = signals["not_test_or_benchmark"] and signals["not_deprecated"] and signals["has_code"]
        if path.suffix.lower() == ".py" and has_rich:
            include = False
        reason = "included" if include else "excluded_by_policy"
        candidates.append(
            TutorialCandidate(
                path=rel,
                title=extract_title(path),
                file_type=path.suffix.lower().lstrip("."),
                priority=priority_for(path, rel),
                include_in_tools=include,
                reason=reason,
                signals=signals,
                evidence_id=f"tutorial_candidate:{index:03d}",
            )
        )
    candidates.sort(key=lambda item: (not item.include_in_tools, item.priority, item.path))
    return {"candidates": candidates, "report": {"total": len(candidates), "included": sum(1 for item in candidates if item.include_in_tools)}}


def is_excluded(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    lowered = {part.lower() for part in rel_parts}
    if lowered & EXCLUDED_PARTS:
        return True
    return any(word in path.name.lower() for word in DEPRECATED_WORDS)


def candidate_signals(path: Path, root: Path) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")[:8000]
    suffix = path.suffix.lower()
    return {
        "has_code": suffix in {".ipynb", ".r", ".py", ".rmd"} or "```" in text,
        "has_narrative": suffix in {".md", ".rst", ".rmd", ".ipynb"} or "#" in text,
        "has_clear_task": any(word in (path.name.lower() + text.lower()) for word in ["tutorial", "demo", "example", "vignette", "workflow"]),
        "has_input_signal": any(word in text.lower() for word in ["read", "input", "data", "load", "import"]),
        "has_output_signal": any(word in text.lower() for word in ["write", "save", "plot", "output", "result", "print"]),
        "not_test_or_benchmark": not is_excluded(path, root),
        "not_deprecated": not any(word in path.name.lower() for word in DEPRECATED_WORDS),
    }


def extract_title(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def priority_for(path: Path, rel: str) -> int:
    lower = rel.lower()
    base = {".ipynb": 0, ".rmd": 1, ".md": 2, ".rst": 2, ".r": 4, ".py": 5}.get(path.suffix.lower(), 9)
    if lower.startswith("docs/"):
        return base
    if lower.startswith(("vignettes/", "tutorials/", "examples/", "notebooks/")):
        return base + 1
    return base + 3
