from __future__ import annotations

from copy import deepcopy
from typing import Any

from paper2skill.compiler.run_trace import run_trace_passed


def evaluate_maturity(
    adapter_spec: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    run_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if run_trace and run_trace_passed(run_trace):
        level = "L2"
        status = "official_or_minimal_example_verified"
    else:
        level = "L1"
        status = "contract_only"
        if adapter_spec.get("status") == "verified":
            status = "verified_adapter_requires_attached_run_trace"
    verified_examples = []
    for item in tutorial_catalog.get("examples", []) or []:
        if not isinstance(item, dict):
            continue
        verification = item.get("verification") if isinstance(item.get("verification"), dict) else {}
        adapter = item.get("adapter") if isinstance(item.get("adapter"), dict) else {}
        if verification.get("status") == "pass" and adapter.get("status") == "verified":
            verified_examples.append(item.get("example_id"))
    return {
        "level": level,
        "status": status,
        "verified_examples": sorted(item for item in verified_examples if item),
        "levels": {
            "L1": "contract/preflight only",
            "L2": "official demo or minimal data verified",
            "L3": "new user data smoke verified",
            "L4": "agentic end-to-end use verified",
        },
    }


def promote_from_run_trace(
    *,
    adapter_spec: dict[str, Any],
    adapter_review: dict[str, Any],
    tutorial_catalog: dict[str, Any],
    run_trace: dict[str, Any],
    example_id: str | None = None,
) -> dict[str, Any]:
    if not run_trace_passed(run_trace):
        return {
            "promoted": False,
            "reason": "run_trace_output_validation_not_passed",
            "adapter_spec": adapter_spec,
            "adapter_review": adapter_review,
            "tutorial_catalog": tutorial_catalog,
            "maturity": evaluate_maturity(adapter_spec, tutorial_catalog, run_trace),
        }
    next_spec = deepcopy(adapter_spec)
    next_review = deepcopy(adapter_review)
    next_catalog = deepcopy(tutorial_catalog)
    expected_outputs = expected_outputs_from_trace(run_trace)
    target_example_id = example_id or run_trace.get("example_id") or tutorial_catalog.get("default_example_id")
    if not catalog_has_example(tutorial_catalog, target_example_id):
        return {
            "promoted": False,
            "reason": "run_trace_example_not_in_catalog",
            "example_id": target_example_id,
            "adapter_spec": adapter_spec,
            "adapter_review": adapter_review,
            "tutorial_catalog": tutorial_catalog,
            "maturity": evaluate_maturity(adapter_spec, tutorial_catalog, None),
        }
    next_spec["status"] = "verified"
    next_spec["expected_outputs"] = expected_outputs
    next_spec["verification"] = {
        "status": "pass",
        "source": "run_trace",
        "example_id": target_example_id,
        "output_validation": run_trace.get("output_validation") or {"status": "pass"},
    }
    next_review.update(
        {
            "status": "verified",
            "expected_outputs": expected_outputs,
            "verification": next_spec["verification"],
            "evidence": sorted(set([*(next_review.get("evidence") or []), "run_trace"])),
        }
    )
    mark_catalog_example_verified(next_catalog, target_example_id, next_spec, expected_outputs)
    return {
        "promoted": True,
        "reason": "run_trace_output_validation_passed",
        "adapter_spec": next_spec,
        "adapter_review": next_review,
        "tutorial_catalog": next_catalog,
        "maturity": evaluate_maturity(next_spec, next_catalog, run_trace),
    }


def expected_outputs_from_trace(run_trace: dict[str, Any]) -> list[str]:
    validation = run_trace.get("output_validation") if isinstance(run_trace.get("output_validation"), dict) else {}
    expected = validation.get("expected_outputs")
    if isinstance(expected, list) and expected:
        return [str(item) for item in expected if str(item)]
    produced = run_trace.get("produced_files") if isinstance(run_trace.get("produced_files"), list) else []
    selected = []
    for item in produced:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if path and not path.startswith(("logs/", "qc/")):
            selected.append(path)
    return selected[:20] or ["result.json"]


def catalog_has_example(catalog: dict[str, Any], example_id: str | None) -> bool:
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    if not example_id:
        return False
    return any(isinstance(item, dict) and item.get("example_id") == example_id for item in examples)


def mark_catalog_example_verified(
    catalog: dict[str, Any],
    example_id: str | None,
    adapter_spec: dict[str, Any],
    expected_outputs: list[str],
) -> bool:
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    target = example_id or catalog.get("default_example_id")
    for item in examples:
        if not isinstance(item, dict):
            continue
        if item.get("example_id") != target:
            continue
        adapter = item.get("adapter") if isinstance(item.get("adapter"), dict) else {}
        adapter.update({key: value for key, value in adapter_spec.items() if key in {"adapter_type", "archetype", "status", "entrypoint", "command", "module", "function"}})
        item["adapter"] = adapter
        item["selected_adapter"] = adapter
        item["verification"] = {"status": "pass", "source": "run_trace"}
        item["outputs"] = expected_outputs
        item["expected_outputs"] = expected_outputs
        output_contract = item.get("output_contract") if isinstance(item.get("output_contract"), dict) else {}
        output_contract["required_files"] = expected_outputs
        output_contract["nonempty"] = expected_outputs
        item["output_contract"] = output_contract
        item["maturity"] = "L2"
        item["runnable_status"] = "run_pass"
        return True
    return False
