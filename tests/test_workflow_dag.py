from __future__ import annotations

from paper2skill.inference.infer_workflow import infer_workflow


def test_workflow_dag_infers_shared_object_edges_and_step_types():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "language": "python",
                "command_or_code": "adata = sc.read_h5ad('input.h5ad')",
                "function_calls": ["sc.read_h5ad"],
                "output_objects": ["adata"],
                "read_files": ["input.h5ad"],
                "bio_signals": ["single_cell"],
                "evidence_id": "tutorial.ipynb:cell:1",
                "confidence": "high",
            },
            {
                "step_id": "tutorial_001:cell_002",
                "language": "python",
                "command_or_code": "sc.pp.normalize_total(adata)",
                "function_calls": ["sc.pp.normalize_total"],
                "input_objects": ["adata"],
                "bio_signals": ["normalization"],
                "evidence_id": "tutorial.ipynb:cell:2",
                "confidence": "high",
            },
            {
                "step_id": "tutorial_001:cell_003",
                "language": "python",
                "command_or_code": "sc.pp.log1p(adata)",
                "function_calls": ["sc.pp.log1p"],
                "input_objects": ["adata"],
                "bio_signals": ["log_transform"],
                "evidence_id": "tutorial.ipynb:cell:3",
                "confidence": "high",
            },
            {
                "step_id": "tutorial_001:cell_004",
                "language": "python",
                "command_or_code": "import scanpy as sc\nsc.tl.pca(adata)",
                "function_calls": ["sc.tl.pca"],
                "input_objects": ["adata"],
                "bio_signals": [],
                "evidence_id": "tutorial.ipynb:cell:4",
                "confidence": "high",
            },
        ]
    }
    workflow = infer_workflow(trace)
    dag = workflow["workflow_dag"]
    assert [node["type"] for node in dag["nodes"]] == ["load_data", "normalization", "transformation", "dimensionality_reduction"]
    assert {"from": "tutorial_001:cell_001", "to": "tutorial_001:cell_002", "reason": "shared_object:adata"} in dag["edges"]
    assert {"from": "tutorial_001:cell_003", "to": "tutorial_001:cell_004", "reason": "shared_object:adata"} in dag["edges"]
    assert dag["nodes"][1]["object_state_after"]["adata"]["matrix_state"] == "normalized"
    assert dag["nodes"][3]["object_state_after"]["adata"]["matrix_state"] == "log1p"
