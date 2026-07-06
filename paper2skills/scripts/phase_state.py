"""Phase-state artifact for the paper2skills build pipeline."""

from __future__ import annotations

from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


def new_phase_state(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "target_agent": request.get("target_agent"),
        "phases": [],
    }


def record_phase(
    state: dict[str, Any],
    name: str,
    status: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    gates: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    state.setdefault("phases", []).append(
        {
            "name": name,
            "status": status,
            "created_at": now_utc(),
            "inputs": inputs or [],
            "outputs": outputs or [],
            "gates": gates or [],
            "notes": notes or [],
        }
    )
    state["updated_at"] = now_utc()
    return state
