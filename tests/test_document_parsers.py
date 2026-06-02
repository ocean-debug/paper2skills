from __future__ import annotations

from pathlib import Path

from paper2skill.parsers.markitdown_parser import MarkItDownParser
from paper2skill.parsers.plain_text_parser import PlainTextParser


def test_plain_text_parser_returns_markdown_and_sections(tmp_path: Path):
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nWe used Read10X.\n", encoding="utf-8")
    parsed = PlainTextParser().parse(paper)
    assert parsed.parser_name == "plain_text"
    assert parsed.markdown.startswith("# Methods")
    assert parsed.sections[0].section_id == "paper:methods"


def test_markitdown_missing_dependency_has_clear_error(tmp_path: Path, monkeypatch):
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    parser = MarkItDownParser()
    monkeypatch.setattr(parser, "_load_markitdown", lambda: None)
    parsed = parser.parse(paper)
    assert parsed.parser_name == "markitdown"
    assert parsed.markdown == ""
    assert "MarkItDown is not installed" in parsed.warnings[0]
