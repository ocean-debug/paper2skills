"""Bounded SkillIR patch application with retained candidate versions."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from common import (
    PATCH_SCHEMA,
    Paper2SkillsError,
    append_event,
    as_list,
    dump_yaml,
    load_yaml,
    require_schema,
)
from validation import validate_spec


ALLOWED_ROOTS = {
    "shared_environment",
    "package_boundaries",
    "shared_troubleshooting",
    "task_types",
    "routing",
}
ALLOWED_OPS = {"append", "insert_after", "replace", "delete"}


def _parts(path: str) -> list[str]:
    parts = [item for item in path.split(".") if item]
    if not parts or parts[0] not in ALLOWED_ROOTS:
        raise Paper2SkillsError(
            f"Patch path must start with one of {sorted(ALLOWED_ROOTS)}: {path}"
        )
    if any(item.startswith("_") for item in parts):
        raise Paper2SkillsError(f"Private patch path is not allowed: {path}")
    return parts


def _lookup(document: Any, parts: list[str]) -> Any:
    current = document
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                raise Paper2SkillsError(f"Patch path does not exist: {'.'.join(parts)}")
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise Paper2SkillsError(f"Patch list index is out of range: {part}")
            current = current[index]
        else:
            raise Paper2SkillsError(f"Patch path is not traversable: {'.'.join(parts)}")
    return current


def _parent(document: Any, parts: list[str]) -> tuple[Any, str]:
    if len(parts) == 1:
        return document, parts[0]
    return _lookup(document, parts[:-1]), parts[-1]


def _replace(document: Any, parts: list[str], value: Any) -> None:
    parent, key = _parent(document, parts)
    if isinstance(parent, dict):
        if key not in parent:
            raise Paper2SkillsError(f"Replace target does not exist: {'.'.join(parts)}")
        parent[key] = value
    elif isinstance(parent, list) and key.isdigit():
        index = int(key)
        if index >= len(parent):
            raise Paper2SkillsError(f"Replace index is out of range: {key}")
        parent[index] = value
    else:
        raise Paper2SkillsError(f"Replace target is invalid: {'.'.join(parts)}")


def _delete(document: Any, parts: list[str]) -> None:
    if len(parts) < 2:
        raise Paper2SkillsError("Deleting a whole allowed root is not permitted")
    parent, key = _parent(document, parts)
    if isinstance(parent, dict) and key in parent:
        del parent[key]
    elif isinstance(parent, list) and key.isdigit() and int(key) < len(parent):
        del parent[int(key)]
    else:
        raise Paper2SkillsError(f"Delete target does not exist: {'.'.join(parts)}")


def _append(document: Any, parts: list[str], value: Any) -> None:
    target = _lookup(document, parts)
    if not isinstance(target, list):
        raise Paper2SkillsError(f"Append target must be a list: {'.'.join(parts)}")
    target.append(value)


def _insert_after(document: Any, parts: list[str], after: Any, value: Any) -> None:
    target = _lookup(document, parts)
    if not isinstance(target, list):
        raise Paper2SkillsError(
            f"insert_after target must be a list: {'.'.join(parts)}"
        )
    try:
        index = target.index(after)
    except ValueError as exc:
        raise Paper2SkillsError(
            f"insert_after anchor was not found at {'.'.join(parts)}"
        ) from exc
    target.insert(index + 1, value)


def _next_iteration(iterations: Path) -> int:
    existing = []
    for path in iterations.glob("spec-v*.yaml"):
        try:
            existing.append(int(path.stem.split("v", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(existing, default=0) + 1


def apply_proposal(run_dir: Path, proposal_path: Path) -> dict[str, Any]:
    """Apply a bounded proposal only when the resulting SkillIR still validates."""

    proposal = load_yaml(proposal_path)
    require_schema(proposal, PATCH_SCHEMA, "patch proposal")
    operations = as_list(proposal.get("operations"))
    if not operations:
        raise Paper2SkillsError("Patch proposal contains no operations")

    current = load_yaml(run_dir / "skill_spec.yaml")
    candidate = copy.deepcopy(current)
    applied: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise Paper2SkillsError(f"Patch operation {index} must be a mapping")
        op = str(operation.get("op") or "")
        path = str(operation.get("path") or "")
        if op not in ALLOWED_OPS:
            raise Paper2SkillsError(f"Unsupported patch operation {op!r}")
        parts = _parts(path)
        if op == "replace":
            _replace(candidate, parts, operation.get("value"))
        elif op == "delete":
            _delete(candidate, parts)
        elif op == "append":
            _append(candidate, parts, operation.get("value"))
        else:
            _insert_after(
                candidate, parts, operation.get("after"), operation.get("value")
            )
        applied.append({"index": index, "op": op, "path": path})

    iterations = run_dir / "iterations"
    iterations.mkdir(parents=True, exist_ok=True)
    version = _next_iteration(iterations)
    candidate_path = iterations / f"spec-v{version:03d}.yaml"
    dump_yaml(candidate_path, candidate)

    original_path = run_dir / "skill_spec.yaml"
    dump_yaml(original_path, candidate)
    report = validate_spec(run_dir)
    if report["status"] != "pass":
        dump_yaml(original_path, current)
        rejection = {
            "status": "rejected",
            "candidate": str(candidate_path),
            "blockers": report["blockers"],
            "operations": applied,
        }
        dump_yaml(iterations / f"patch-v{version:03d}-report.yaml", rejection)
        append_event(run_dir, "patch_rejected", version=version, blockers=report["blockers"])
        return rejection

    acceptance = {
        "status": "applied",
        "candidate": str(candidate_path),
        "operations": applied,
        "rationale": str(proposal.get("rationale") or ""),
    }
    dump_yaml(iterations / f"patch-v{version:03d}-report.yaml", acceptance)
    append_event(run_dir, "patch_applied", version=version, operations=applied)
    return acceptance

