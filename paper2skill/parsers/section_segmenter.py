from __future__ import annotations

import re
from collections import defaultdict

from paper2skill.parsers.base import ParsedSection


METHOD_ALIASES = ["methods", "method", "materials and methods", "online methods", "experimental procedures"]
DATA_ALIASES = ["data availability", "datasets", "data", "availability"]
CODE_ALIASES = ["code availability", "software availability", "implementation"]
RESULT_ALIASES = ["results", "experiments", "benchmark", "evaluation"]
LIMITATION_ALIASES = ["limitations", "discussion"]

ALIAS_GROUPS = {
    "methods": METHOD_ALIASES,
    "data": DATA_ALIASES,
    "code": CODE_ALIASES,
    "results": RESULT_ALIASES,
    "limitations": LIMITATION_ALIASES,
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def segment_markdown(markdown: str, source_path: str, prefix: str = "paper") -> list[ParsedSection]:
    lines = markdown.splitlines()
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    if not headings:
        text = markdown.strip()
        return [ParsedSection(f"{prefix}:document", "Document", 0, text, source_path, 1 if text else None, len(lines) if text else None)] if text else []
    sections = []
    slug_counts: dict[str, int] = defaultdict(int)
    stack: list[tuple[int, str]] = []
    for pos, (line_no, level, title) in enumerate(headings):
        next_line = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines) + 1
        while stack and stack[-1][0] >= level:
            stack.pop()
        slug = canonical_slug(title)
        if slug in ALIAS_GROUPS:
            stack = []
        slug_counts[":".join([part for _lvl, part in stack] + [slug])] += 1
        count = slug_counts[":".join([part for _lvl, part in stack] + [slug])]
        final_slug = f"{slug}-{count}" if count > 1 else slug
        stack.append((level, final_slug))
        section_id = ":".join([prefix, *[part for _lvl, part in stack]])
        body_lines = lines[line_no: next_line - 1]
        sections.append(ParsedSection(section_id, title, level, "\n".join(body_lines).strip(), source_path, line_no, next_line - 1))
    return sections


def canonical_slug(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    for canonical, aliases in ALIAS_GROUPS.items():
        if normalized in aliases:
            return canonical
    value = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return value or "section"
