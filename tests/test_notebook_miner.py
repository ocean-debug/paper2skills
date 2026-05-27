from __future__ import annotations

from paper2skill.miners.notebook_miner import mine_notebook


def test_notebook_trace_includes_ordered_code_cells():
    trace = mine_notebook("tests/fixtures/toy_notebook.ipynb")
    code_cells = [cell for cell in trace["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert code_cells[0]["index"] == 1
    assert "csv" in code_cells[0]["imports"]
    assert trace["workflow_steps"][0]["evidence_id"].endswith("cell:1")
