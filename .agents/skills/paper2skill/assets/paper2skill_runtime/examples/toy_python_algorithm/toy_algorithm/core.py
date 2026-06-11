from __future__ import annotations

import csv
from pathlib import Path


def summarize(path: str | Path) -> dict[str, float | int | None]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    values = [float(row["value"]) for row in rows]
    return {"rows": len(rows), "value_sum": sum(values), "value_mean": sum(values) / len(values) if values else None}
