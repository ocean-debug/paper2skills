from __future__ import annotations

from paper2skill.inference.infer_bio_contract import infer_bio_contract


def test_bio_contract_infers_single_cell_transform_chain_and_metadata_key():
    trace = {
        "tutorials": [
            {
                "path": "docs/tutorial.ipynb",
                "steps": [
                    {
                        "step_id": "tutorial_001:cell_001",
                        "language": "python",
                        "code_preview": "adata = sc.read_10x_mtx('data/')",
                        "function_calls": ["sc.read_10x_mtx"],
                        "output_objects": ["adata"],
                    },
                    {
                        "step_id": "tutorial_001:cell_002",
                        "language": "python",
                        "code_preview": "sc.pp.normalize_total(adata)\nsc.pp.log1p(adata)\nadata.obs['cell_type']",
                        "function_calls": ["sc.pp.normalize_total", "sc.pp.log1p"],
                        "input_objects": ["adata"],
                    },
                ],
            }
        ]
    }
    contract = infer_bio_contract(trace, paper_sections=[])
    bio = contract["bio_contract"]
    assert bio["modality"]["primary"]["value"] == "scRNA-seq"
    assert bio["input_matrix_state"]["matrix_transformations"] == ["raw_counts_loaded", "normalized", "log1p_transformed"]
    assert bio["metadata_requirements"]["celltype_key"]["value"] == "cell_type"


def test_strict_bio_contract_does_not_promote_background_species_keyword():
    sections = [
        {
            "section_id": "paper:introduction",
            "title": "Introduction",
            "text": "Human disease studies often motivate computational methods.",
        }
    ]
    contract = infer_bio_contract({"tutorials": [], "workflow_steps": []}, paper_sections=sections, strict_evidence=True)
    species = contract["bio_contract"]["organism"]["species_supported"]
    assert species["value"] == "not_confirmed"
