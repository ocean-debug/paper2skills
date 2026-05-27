from __future__ import annotations

from typing import Any


def summarize_evidence(context: dict[str, Any]) -> str:
    return f"{context['algorithm_name']} uses {context['language']} evidence with {len(context['tutorial_trace'].get('workflow_steps', []))} tutorial steps."
