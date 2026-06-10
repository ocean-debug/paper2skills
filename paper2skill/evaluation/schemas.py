from __future__ import annotations

from typing import Final


LEVEL_WEIGHTS: Final[dict[str, int]] = {
    "L0": 10,
    "L1": 30,
    "L2": 25,
    "L3": 20,
    "L4": 15,
}

STATIC_L1_WEIGHTS: Final[dict[str, int]] = {
    "source_collection": 10,
    "dependency_mining": 15,
    "tutorial_workflow_dag": 20,
    "io_bio_contract": 25,
    "evidence_graph_correctness": 10,
    "adapter_safety_behavior": 15,
    "execution_safety_plan": 5,
}

VALID_LEVELS: Final[tuple[str, ...]] = ("L0", "L1", "L2", "L3", "L4")

VALID_L2_MODES: Final[tuple[str, ...]] = ("dry_run", "data_smoke", "live_execute")
BUILD_VALIDATION_DEPTHS: Final[tuple[str, ...]] = VALID_L2_MODES
BENCHMARK_L2_MODE: Final[str] = "live_execute"

L2_MODE_RANK: Final[dict[str, int]] = {
    "blocked_expected": 0,
    "dry_run": 0,
    "smoke": 1,
    "data_smoke": 1,
    "full": 2,
    "live_execute": 2,
}

VALID_INSTALL_POLICIES: Final[tuple[str, ...]] = ("none", "ask", "approved")

VALID_ADAPTER_STATUSES: Final[set[str]] = {
    "demo_only",
    "candidate",
    "blocked",
    "ready",
    "reviewed",
    "verified",
}

EXECUTABLE_ADAPTER_STATUSES: Final[set[str]] = {"ready", "reviewed", "verified"}

VALID_TUTORIAL_SELECTION_MODES: Final[set[str]] = {
    "single_tutorial",
    "multi_tutorial_same_workflow",
    "multi_tutorial_multi_workflow",
    "multi_tutorial_pipeline_stages",
}

VALID_WORKFLOW_MODES: Final[set[str]] = {
    "single_workflow",
    "multi_workflow",
    "pipeline_workflow",
    "single_workflow_multiple_examples",
}
