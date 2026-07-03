"""Parameter-constraint mining from statically inspected interfaces."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


SEMANTIC_PARAMETER_HINTS = {
    "metadata_role": ["batch", "label", "condition", "group", "sample", "obs", "var", "key"],
    "file_or_path": ["path", "file", "dir", "folder", "output", "save"],
    "resource": ["device", "gpu", "cuda", "n_jobs", "num_workers", "batch_size"],
    "randomness": ["seed", "random_state"],
    "threshold": ["min", "max", "threshold", "cutoff", "n_", "num_"],
}


def semantic_roles(name: str) -> list[str]:
    lowered = name.lower()
    roles = []
    for role, needles in SEMANTIC_PARAMETER_HINTS.items():
        if any(needle in lowered for needle in needles):
            roles.append(role)
    return roles


def parameter_record(interface: dict[str, Any], parameter: dict[str, Any]) -> dict[str, Any]:
    name = str(parameter.get("name") or "")
    branch_values = interface.get("branch_parameter_values", {}).get(name, [])
    return {
        "name": name,
        "kind": parameter.get("kind"),
        "required": bool(parameter.get("required")),
        "default": parameter.get("default"),
        "annotation": parameter.get("annotation"),
        "semantic_roles": semantic_roles(name),
        "branch_values": branch_values,
        "interface_ref": interface.get("interface_id"),
        "signature": interface.get("signature"),
        "source_path": interface.get("source_path"),
        "evidence_refs": interface.get("evidence_refs", []),
    }


def build_parameter_catalog(
    request: dict[str, Any],
    interface_grounding: dict[str, Any],
) -> dict[str, Any]:
    parameters = []
    by_task_type: dict[str, dict[str, Any]] = {}
    for interface in interface_grounding.get("interfaces", []):
        for parameter in interface.get("parameters", []):
            if parameter.get("name") in {"self", "cls"}:
                continue
            item = parameter_record(interface, parameter)
            parameters.append(item)
            for task_type in interface.get("task_type_candidates", []):
                bucket = by_task_type.setdefault(task_type, {"parameters": [], "required_parameters": []})
                bucket["parameters"].append(item)
                if item["required"]:
                    bucket["required_parameters"].append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "parameter_count": len(parameters),
        "parameters": parameters,
        "by_task_type": by_task_type,
        "notes": [
            "Parameter constraints are static hints from inspected signatures and branch values.",
            "Unknown biological semantics must still be confirmed from official tutorials or docs before execution.",
        ],
    }


def attach_parameter_constraints(
    task_catalog: dict[str, Any],
    parameter_catalog: dict[str, Any],
    limit: int = 12,
) -> dict[str, Any]:
    catalog = deepcopy(task_catalog)
    for task in catalog.get("tasks", []):
        task_type = str(task.get("task_type"))
        bucket = parameter_catalog.get("by_task_type", {}).get(task_type, {})
        observed = []
        for parameter in bucket.get("parameters", [])[:limit]:
            observed.append(
                {
                    "name": parameter.get("name"),
                    "required": parameter.get("required"),
                    "default": parameter.get("default"),
                    "annotation": parameter.get("annotation"),
                    "semantic_roles": parameter.get("semantic_roles", []),
                    "branch_values": parameter.get("branch_values", []),
                    "signature": parameter.get("signature"),
                    "source_path": parameter.get("source_path"),
                    "interface_ref": parameter.get("interface_ref"),
                }
            )
        task.setdefault("input_contract", {})["parameter_constraints_observed"] = observed
    return catalog
