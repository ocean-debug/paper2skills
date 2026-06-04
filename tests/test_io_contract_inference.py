from __future__ import annotations

from paper2skill.inference.infer_io_contract import infer_io_contract


def test_io_contract_infers_10x_format_from_scanpy_reader_call():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "adata = sc.read_10x_mtx('data/')",
                "command_or_code": "import scanpy as sc\nadata = sc.read_10x_mtx('data/')",
                "function_calls": ["sc.read_10x_mtx"],
                "read_files": [],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    primary_data = contract["input_contract"]["required"]["primary_data"]
    assert primary_data["format"]["value"] == "10x_mtx"
    assert primary_data["format"]["confidence"] == "high"
    assert "sc.read_10x_mtx" in primary_data["format"]["evidence"]
