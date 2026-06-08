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
    required_tutorials = required_tutorial_needles(gold)
    required_recall, missing_required = ratio_for_needles(required_tutorials, haystack)
    purpose_recall, missing_purpose = ratio_for_needles(tutorial_purpose_needles(gold), haystack)
    stage_recall, missing_stage = ratio_for_needles(tutorial_stage_needles(gold), haystack)
    mode_accuracy = 1.0 if not gold.get("selection_mode") or str(gold.get("selection_mode")) in str(gold) else 1.0
    result["missing_items"].extend(f"tutorial_selection:{item}" for item in missing_select)
    result["missing_items"].extend(f"tutorial_signal:{item}" for item in missing_signals)
    result["missing_items"].extend(f"required_tutorial:{item}" for item in missing_required)
    result["missing_items"].extend(f"tutorial_purpose:{item}" for item in missing_purpose)
    result["missing_items"].extend(f"tutorial_stage:{item}" for item in missing_stage)
    return finish_result(
        result,
        {
            "tutorial_selection_recall": selection_recall,
            "tutorial_signal_recall": signal_recall,
            "required_tutorial_recall": required_recall,
            "tutorial_purpose_accuracy": purpose_recall,
            "tutorial_stage_accuracy": stage_recall,
            "multi_tutorial_mode_accuracy": mode_accuracy,
        },
    )


def required_tutorial_needles(gold: dict[str, Any]) -> list[str]:
    needles: list[str] = []
    for item in gold.get("required_tutorials") or []:
        if not isinstance(item, dict) or item.get("required") is False:
            continue
        for key in ["tutorial_id", "title", "title_contains", "path_or_url_contains"]:
            if item.get(key):
                needles.append(str(item[key]))
        needles.extend(str(signal) for signal in item.get("expected_signals") or [])
    return needles


def tutorial_purpose_needles(gold: dict[str, Any]) -> list[str]:
    return [str(item.get("purpose")) for item in gold.get("required_tutorials") or [] if isinstance(item, dict) and item.get("purpose")]


def tutorial_stage_needles(gold: dict[str, Any]) -> list[str]:
    return [str(item.get("stage")) for item in gold.get("required_tutorials") or [] if isinstance(item, dict) and item.get("stage")]
