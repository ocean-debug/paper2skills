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
    scrna = bio["modality_contracts"]["scrna_seq"]
    assert scrna["input_state"]["matrix_state"]["value"] == "log1p"
    assert scrna["metadata"]["celltype_key"]["value"] == "cell_type"


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


def test_bio_contract_prefers_tutorial_evidence_over_paper_background_conflict():
    trace = {
        "tutorials": [
            {
                "path": "docs/tutorial.ipynb",
                "steps": [
                    {
                        "step_id": "tutorial_001:cell_001",
                        "evidence_id": "tutorial.ipynb:cell:1",
                        "code_preview": "adata.uns['species'] = 'human'",
                        "command_or_code": "adata.uns['species'] = 'human'",
                        "function_calls": [],
                    }
                ],
            }
        ]
    }
    sections = [
        {
            "section_id": "paper:introduction",
            "title": "Introduction",
            "text": "Mouse examples are often used as background motivation.",
        }
    ]

    contract = infer_bio_contract(trace, paper_sections=sections)

    species = contract["bio_contract"]["organism"]["species_supported"]
    assert species["value"] == "human"
    assert species["confidence"] == "high"
    assert species["evidence"] == ["tutorial.ipynb:cell:1"]


def test_bio_contract_adds_bulk_rna_seq_modality_contract():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "evidence_id": "tutorial.ipynb:cell:1",
                "code_preview": "dds <- DESeqDataSetFromMatrix(countData = counts, colData = sample_table, design = ~ condition)",
                "command_or_code": "DESeq2::DESeqDataSetFromMatrix(countData = counts, colData = sample_table, design = ~ condition)",
                "function_calls": ["DESeq2::DESeqDataSetFromMatrix"],
            }
        ]
    }

    contract = infer_bio_contract(trace, paper_sections=[])

    bio = contract["bio_contract"]
    assert bio["modality"]["primary"]["value"] == "bulk RNA-seq"
    bulk = bio["modality_contracts"]["bulk_rna_seq"]
    assert bulk["input_state"]["matrix_state"]["value"] == "raw_counts"
    assert bulk["metadata"]["condition_key"]["value"] == "condition"
    assert bulk["statistical"]["design_formula"]["value"] == "~ condition"
