from __future__ import annotations

from paper2skill.evaluation.compare_workflow_dag import compare_workflow_dag


def test_workflow_node_edge_and_state_recall():
    gold = {
        "nodes": [
            {"id": "load", "type": "load_data"},
            {"id": "normalize", "type": "normalization", "expected_state_after": {"matrix_state": "normalized"}},
            {"id": "save", "type": "save_output"},
        ],
        "edges": ["load -> normalize", "normalize -> save"],
    }
    generated = {
        "workflow_dag": {
            "nodes": [
                {"step_id": "s1", "type": "load_data"},
                {"step_id": "s2", "type": "normalization", "object_state_after": {"adata": {"matrix_state": "normalized"}}},
            ],
            "edges": [{"from": "s1", "to": "s2"}],
        }
    }

    result = compare_workflow_dag(gold, generated)

    assert result["metrics"]["workflow_node_recall"] == 2 / 3
    assert result["metrics"]["workflow_edge_recall"] == 0.5
    assert result["metrics"]["object_state_accuracy"] == 1.0
    assert "workflow_node_type:output_extraction" in result["missing_items"]


def test_workflow_step_type_aliases_match_equivalent_steps():
    gold = {
        "nodes": [
            {"id": "model", "type": "model_training_or_embedding"},
            {"id": "stats", "type": "statistical_analysis"},
            {"id": "out", "type": "output_extraction"},
        ],
        "edges": ["model -> stats", "stats -> out"],
    }
    generated = {
        "workflow_dag": {
            "nodes": [
                {"step_id": "g1", "type": "model_training"},
                {"step_id": "g2", "type": "differential_expression"},
                {"step_id": "g3", "type": "save_output"},
            ],
            "edges": [{"from": "g1", "to": "g2"}, {"from": "g2", "to": "g3"}],
        }
    }

    result = compare_workflow_dag(gold, generated)

    assert result["metrics"]["workflow_node_recall"] == 1.0
    assert result["metrics"]["workflow_edge_recall"] == 1.0
