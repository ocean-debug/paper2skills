from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_local_path


def collect_paper(path: str | None = None, url: str | None = None, title: str | None = None, base_dir: str | Path | None = None) -> dict[str, Any]:
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    paper_path = Path(path).resolve() if path else None
    text_preview = ""
    if paper_path and paper_path.exists() and paper_path.suffix.lower() in {".md", ".txt"}:
        text_preview = paper_path.read_text(encoding="utf-8", errors="replace")[:4000]
    return {
        "path": public_local_path(paper_path, base),
        "url": url,
        "title": title,
        "exists": bool(paper_path and paper_path.exists()),
        "kind": paper_path.suffix.lower().lstrip(".") if paper_path else ("url" if url else "title"),
        "text_preview": text_preview,
    }
