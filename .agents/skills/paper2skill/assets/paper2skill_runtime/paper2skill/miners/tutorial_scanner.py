from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
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
    section_title: str | None = None
    section_anchor: str | None = None
    source_path: str | None = None
    code_block_index: int | None = None
    indexed_from: str | None = None
    missing_index_target: str | None = None


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
                source_path=rel,
            )
        )
        if path.suffix.lower() in {".md", ".rst", ".rmd"} and not is_excluded(path, root):
            for section_index, section in enumerate(extract_sections(path), start=1):
                if not section_has_tutorial_signal(section):
                    continue
                anchor = anchor_for(section["title"])
                section_rel = f"{rel}#{anchor}" if anchor else rel
                candidates.append(
                    TutorialCandidate(
                        path=section_rel,
                        title=section["title"],
                        file_type=path.suffix.lower().lstrip("."),
                        priority=priority_for(path, rel) - 1,
                        include_in_tools=signals["not_deprecated"],
                        reason="included_section",
                        signals={**signals, "heading_section": True, "has_code": bool(section["code_blocks"])},
                        evidence_id=f"tutorial_candidate:{index:03d}:section_{section_index:03d}",
                        section_title=section["title"],
                        section_anchor=anchor,
                        source_path=rel,
                        code_block_index=section["code_blocks"][0] if section["code_blocks"] else None,
                    )
                )
    candidates.sort(key=lambda item: (not item.include_in_tools, item.priority, item.path))
    missing_indexed = indexed_tutorial_gaps(root, paths)
    return {
        "candidates": candidates,
        "report": {
            "total": len(candidates),
            "included": sum(1 for item in candidates if item.include_in_tools),
            "missing_indexed_tutorials": missing_indexed,
        },
    }


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


def extract_sections(path: Path) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    code_block_index = 0
    in_fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if in_fence:
                code_block_index += 1
                if current is not None:
                    current["code_blocks"].append(code_block_index)
            if current is not None:
                current["text"].append(line)
            continue
        if not in_fence and stripped.startswith("#"):
            if current is not None:
                sections.append(current)
            current = {"title": stripped.lstrip("#").strip(), "text": [], "code_blocks": []}
            continue
        if current is not None:
            current["text"].append(line)
    if current is not None:
        sections.append(current)
    return sections


def section_has_tutorial_signal(section: dict[str, Any]) -> bool:
    title = str(section.get("title") or "").lower()
    text = "\n".join(section.get("text") or []).lower()
    words = [
        "usage",
        "demonstration",
        "demo",
        "tutorial",
        "example",
        "installation",
        "system requirements",
        "preparing input",
        "running",
        "workflow",
        "input files",
    ]
    return bool(section.get("code_blocks")) or any(word in title or word in text for word in words)


def anchor_for(title: str | None) -> str | None:
    if not title:
        return None
    anchor = "".join(char.lower() if char.isalnum() else "-" for char in title.strip())
    anchor = "-".join(part for part in anchor.split("-") if part)
    return anchor or None


def priority_for(path: Path, rel: str) -> int:
    lower = rel.lower()
    base = {".ipynb": 0, ".rmd": 1, ".md": 2, ".rst": 2, ".r": 4, ".py": 5}.get(path.suffix.lower(), 9)
    if lower.startswith("docs/"):
        return base
    if lower.startswith(("vignettes/", "tutorials/", "examples/", "notebooks/")):
        return base + 1
    return base + 3


def indexed_tutorial_gaps(root: Path, paths: list[Path]) -> list[dict[str, str]]:
    existing = {path.relative_to(root).as_posix() for path in paths}
    gaps: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        if path.suffix.lower() not in {".rst", ".md"}:
            continue
        rel = path.relative_to(root).as_posix()
        for target in indexed_tutorial_targets(path, root):
            if target in existing:
                continue
            gaps[(rel, target)] = {"index": rel, "target": target, "reason": "indexed_tutorial_missing"}
    return list(gaps.values())


def indexed_tutorial_targets(path: Path, root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    candidates: list[str] = []
    lines = text.splitlines()
    in_toctree = False
    toctree_indent: int | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(".. toctree::"):
            in_toctree = True
            toctree_indent = None
            continue
        if in_toctree:
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            if toctree_indent is None and stripped.startswith(":"):
                continue
            if toctree_indent is None:
                toctree_indent = indent
            if indent < toctree_indent:
                in_toctree = False
            elif not stripped.startswith(":"):
                candidates.append(index_target_from_line(stripped))
                continue
        for match in re.finditer(r"\(([^)]+\.(?:ipynb|md|rst|rmd|py|r))\)", line):
            candidates.append(match.group(1))
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", line):
            target = match.group(1)
            if looks_like_indexed_tutorial_ref(target):
                candidates.append(target)
    resolved = []
    for value in candidates:
        if not value:
            continue
        if "://" in value or value.startswith("#"):
            continue
        target = value.split("#", 1)[0].strip()
        if not target:
            continue
        target_path = resolve_index_target(path.parent, target)
        try:
            resolved.append(target_path.relative_to(root.resolve()).as_posix())
        except ValueError:
            continue
    return sorted(dict.fromkeys(resolved))


def index_target_from_line(stripped: str) -> str:
    match = re.search(r"<([^>]+)>", stripped)
    if match:
        return match.group(1).strip()
    return stripped.split()[0]


def resolve_index_target(base: Path, target: str) -> Path:
    candidate = base / target
    if candidate.suffix:
        return candidate.resolve()
    for suffix in [".ipynb", ".rst", ".md", ".rmd", ".py", ".r"]:
        suffixed = candidate.with_suffix(suffix)
        if suffixed.exists():
            return suffixed.resolve()
    return candidate.with_suffix(".ipynb").resolve()


def looks_like_indexed_tutorial_ref(target: str) -> bool:
    if "://" in target or target.startswith("#"):
        return False
    clean = target.split("#", 1)[0].strip().lower()
    if not clean:
        return False
    suffix = Path(clean).suffix
    if suffix in TUTORIAL_SUFFIXES:
        return True
    parts = {part for part in clean.replace("\\", "/").split("/") if part}
    return bool(parts & {"tutorial", "tutorials", "example", "examples", "notebook", "notebooks", "vignette", "vignettes"})
