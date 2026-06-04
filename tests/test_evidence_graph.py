from __future__ import annotations

from paper2skill.evidence.evidence_graph import build_evidence_graph


def test_evidence_graph_adds_decision_for_conflicting_claims():
    graph = build_evidence_graph(
        tutorial_trace={
            "tutorials": [
                {
                    "path": "docs/tutorial.ipynb",
                    "steps": [
                        {
                            "step_id": "tutorial_001:cell_001",
                            "evidence_id": "tutorial.ipynb:cell:1",
                            "source": "docs/tutorial.ipynb:cell:1",
                            "command_or_code": "adata = sc.read_10x_mtx('data/')",
                            "confidence": "high",
                        }
                    ],
                }
            ]
        },
        bio_contract={"field": {"value": "raw_counts", "confidence": "high", "evidence": ["tutorial.ipynb:cell:1"]}},
        algorithm_contract={"field": {"value": "normalized", "confidence": "medium", "evidence": ["readme:input"]}},
    )
    assert graph["conflicts"]
    decision = graph["decisions"][0]
    assert decision["field"] == "field"
    assert decision["decision"]["value"] == "raw_counts"
    assert decision["decision"]["status"] == "decided"
