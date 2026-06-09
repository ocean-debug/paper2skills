from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from benchmark_framework import load_cases, run_case


pytestmark = pytest.mark.benchmark


@pytest.mark.parametrize("case", load_cases(Path(__file__).parent / "cases"), ids=lambda case: case.case_id)
def test_omics_algorithm_benchmark_case(case, tmp_path):
    run_case(case, tmp_path)
