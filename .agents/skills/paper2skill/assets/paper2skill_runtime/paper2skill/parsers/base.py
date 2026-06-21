from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedSection:
    section_id: str
    title: str
    level: int
    text: str
    source_path: str
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class ParsedDocument:
    source_path: str
    source_type: str
    parser_name: str
    markdown: str
    sections: list[ParsedSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DocumentParser:
    name: str = "base"
    supported_suffixes: set[str] = set()

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def parse(self, path: Path) -> ParsedDocument:
        raise NotImplementedError
