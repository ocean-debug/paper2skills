from __future__ import annotations

import re
from pathlib import Path

from paper2skill.parsers.base import DocumentParser, ParsedDocument
from paper2skill.parsers.section_segmenter import segment_markdown


class HtmlParser(DocumentParser):
    name = "html"
    supported_suffixes = {".html", ".htm"}

    def parse(self, path: Path) -> ParsedDocument:
        html = path.read_text(encoding="utf-8", errors="replace")
        markdown = html_to_markdown(html)
        return ParsedDocument(
            source_path=str(path),
            source_type="html",
            parser_name=self.name,
            markdown=markdown,
            sections=segment_markdown(markdown, str(path), "paper"),
        )


def html_to_markdown(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        lines = []
        for node in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            if node.name in {"h1", "h2", "h3"}:
                lines.append(f"{'#' * int(node.name[1])} {text}")
            else:
                lines.append(text)
        return "\n\n".join(lines) + ("\n" if lines else "")
    except ImportError:
        text = re.sub(r"<h([1-3])[^>]*>(.*?)</h\1>", lambda m: f"\n{'#' * int(m.group(1))} {strip_tags(m.group(2))}\n", html, flags=re.I | re.S)
        text = strip_tags(text)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)
