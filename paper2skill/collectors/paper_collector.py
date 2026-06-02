from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_data, public_local_path
from paper2skill.common import write_json, write_text
from paper2skill.parsers.base import ParsedDocument
from paper2skill.parsers.html_parser import HtmlParser
from paper2skill.parsers.markitdown_parser import MarkItDownParser
from paper2skill.parsers.plain_text_parser import PlainTextParser


def collect_paper(
    path: str | None = None,
    url: str | None = None,
    title: str | None = None,
    base_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    paper_path = Path(path).resolve() if path else None
    text_preview = ""
    parsed: ParsedDocument | None = None
    warnings: list[str] = []
    if paper_path and paper_path.exists():
        parsed = parse_paper_document(paper_path)
        warnings = parsed.warnings
        text_preview = parsed.markdown[:4000]
        if out_dir:
            write_paper_outputs(parsed, Path(out_dir), base)
    result = {
        "path": public_local_path(paper_path, base),
        "source_path": public_local_path(paper_path, base),
        "url": url,
        "title": title,
        "exists": bool(paper_path and paper_path.exists()),
        "kind": paper_path.suffix.lower().lstrip(".") if paper_path else ("url" if url else "title"),
        "text_preview": text_preview,
        "source_type": parsed.source_type if parsed else (paper_path.suffix.lower().lstrip(".") if paper_path else ("url" if url else "title")),
        "parser_name": parsed.parser_name if parsed else None,
        "markdown_path": "references/paper.md" if parsed and out_dir else None,
        "section_map_path": "references/paper_sections.json" if parsed and out_dir else None,
        "parsed_document": parsed_to_dict(parsed) if parsed else None,
        "warnings": warnings,
    }
    return result


def parse_paper_document(path: Path) -> ParsedDocument:
    parsers = [PlainTextParser(), HtmlParser(), MarkItDownParser()]
    for parser in parsers:
        if parser.can_parse(path):
            return parser.parse(path)
    return PlainTextParser().parse(path)


def write_paper_outputs(parsed: ParsedDocument, out_dir: Path, base_dir: Path | None = None) -> None:
    base = base_dir or out_dir
    references = out_dir / "references"
    write_text(references / "paper.md", parsed.markdown)
    write_json(references / "paper_sections.json", public_data(section_map(parsed), base))
    write_json(
        references / "paper_parser_report.json",
        public_data(
            {
                "source_path": parsed.source_path,
                "source_type": parsed.source_type,
                "parser_name": parsed.parser_name,
                "warnings": parsed.warnings,
            },
            base,
        ),
    )


def section_map(parsed: ParsedDocument) -> dict[str, Any]:
    return {
        "source_path": parsed.source_path,
        "parser_name": parsed.parser_name,
        "sections": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "level": section.level,
                "start_line": section.start_line,
                "end_line": section.end_line,
                "char_count": len(section.text),
            }
            for section in parsed.sections
        ],
        "warnings": parsed.warnings,
    }


def parsed_to_dict(parsed: ParsedDocument | None) -> dict[str, Any] | None:
    if parsed is None:
        return None
    return {
        "source_path": parsed.source_path,
        "source_type": parsed.source_type,
        "parser_name": parsed.parser_name,
        "markdown": parsed.markdown,
        "sections": [section.__dict__ for section in parsed.sections],
        "metadata": parsed.metadata,
        "warnings": parsed.warnings,
    }
