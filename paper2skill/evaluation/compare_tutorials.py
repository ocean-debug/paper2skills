from __future__ import annotations

from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, finish_result, ratio_for_needles


def compare_tutorials(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("tutorials")
    haystack = {
        "tutorial_trace": generated.get("tutorial_trace") or {},
        "tutorial_candidates": generated.get("tutorial_candidates") or {},
        "source_manifest": generated.get("source_manifest") or {},
    }
    should_select = []
    for item in gold.get("should_select") or []:
        if isinstance(item, dict):
            should_select.extend(str(value) for value in item.values())
        else:
            should_select.append(str(item))
    selection_recall, missing_select = ratio_for_needles(should_select, haystack)
    signal_recall, missing_signals = ratio_for_needles(gold.get("expected_tutorial_signals") or [], haystack)
    result["missing_items"].extend(f"tutorial_selection:{item}" for item in missing_select)
    result["missing_items"].extend(f"tutorial_signal:{item}" for item in missing_signals)
    return finish_result(
        result,
        {
            "tutorial_selection_recall": selection_recall,
            "tutorial_signal_recall": signal_recall,
        },
    )
