from __future__ import annotations

from pathlib import Path

from paper2skill.parsers.base import DocumentParser, ParsedDocument
from paper2skill.parsers.section_segmenter import segment_markdown


class PlainTextParser(DocumentParser):
    name = "plain_text"
    supported_suffixes = {".md", ".txt", ".rst"}

    def parse(self, path: Path) -> ParsedDocument:
        markdown = path.read_text(encoding="utf-8", errors="replace")
        return ParsedDocument(
            source_path=str(path),
            source_type=path.suffix.lower().lstrip(".") or "text",
            parser_name=self.name,
            markdown=markdown,
            sections=segment_markdown(markdown, str(path), "paper"),
        )
