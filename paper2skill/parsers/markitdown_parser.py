from __future__ import annotations

from pathlib import Path

from paper2skill.parsers.base import DocumentParser, ParsedDocument
from paper2skill.parsers.section_segmenter import segment_markdown


MISSING_MARKITDOWN = "MarkItDown is not installed. Install with pip install 'markitdown[pdf,docx,pptx,xlsx]'"


class MarkItDownParser(DocumentParser):
    name = "markitdown"
    supported_suffixes = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv", ".json", ".xml", ".zip", ".epub"}

    def _load_markitdown(self):
        try:
            from markitdown import MarkItDown

            return MarkItDown()
        except ImportError:
            return None

    def parse(self, path: Path) -> ParsedDocument:
        converter = self._load_markitdown()
        if converter is None:
            return ParsedDocument(str(path), path.suffix.lower().lstrip("."), self.name, "", warnings=[MISSING_MARKITDOWN])
        try:
            result = converter.convert(str(path))
            markdown = getattr(result, "text_content", "") or str(result)
            warnings: list[str] = []
        except Exception as exc:
            markdown = ""
            warnings = [f"MarkItDown failed: {exc}"]
        return ParsedDocument(
            source_path=str(path),
            source_type=path.suffix.lower().lstrip("."),
            parser_name=self.name,
            markdown=markdown,
            sections=segment_markdown(markdown, str(path), "paper") if markdown else [],
            warnings=warnings,
        )
