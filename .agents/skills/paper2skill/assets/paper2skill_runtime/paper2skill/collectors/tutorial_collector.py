from __future__ import annotations

from pathlib import Path
from typing import Any

from paper2skill.collectors.path_sanitizer import public_local_path


def collect_tutorials(paths: list[str] | None = None, mode: str = "official_example", base_dir: str | Path | None = None) -> dict[str, Any]:
    base = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
    records = []
    for value in paths or []:
        path = Path(value).resolve()
        records.append(
            {
                "path": public_local_path(path, base),
                "exists": path.exists(),
                "suffix": path.suffix.lower(),
                "mode": mode,
            }
        )
    return {"paths": records, "mode": mode}
