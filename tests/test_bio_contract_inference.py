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


def test_bio_contract_adds_perturb_seq_and_ribo_rna_metadata_contracts():
    perturb_trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "evidence_id": "tutorial.ipynb:cell:1",
                "code_preview": "Perturb-seq AnnData uses adata.obs['condition'] and adata.obs['cell_type'] for gene perturbation prediction",
                "command_or_code": "adata.obs['condition']; adata.obs['cell_type']",
                "function_calls": [],
            }
        ]
    }
    ribo_trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "evidence_id": "tutorial.ipynb:cell:1",
                "code_preview": "Ribo-seq and RNA-seq raw count matrix uses SampleID, Condition, SeqType, and Batch columns",
                "command_or_code": "raw count matrix SampleID Condition SeqType Batch",
                "function_calls": [],
            }
        ]
    }

    perturb = infer_bio_contract(perturb_trace, paper_sections=[])["bio_contract"]
    ribo = infer_bio_contract(ribo_trace, paper_sections=[])["bio_contract"]

    assert perturb["modality"]["primary"]["value"] == "perturb-seq"
    assert perturb["modality_contracts"]["perturb_seq"]["metadata"]["condition_key"]["value"] == "condition"
    assert ribo["modality"]["primary"]["value"] == "Ribo-seq/RNA-seq"
    assert ribo["modality_contracts"]["ribo_rna_seq"]["metadata"]["seqtype_key"]["value"] == "SeqType"


def test_bio_contract_infers_augur_like_preprocessed_scrna_constraints():
    trace = {
        "workflow_steps": [
            {
                "step_id": "README.md:section:usage",
                "evidence_id": "README.md:section:usage",
                "code_preview": (
                    "calculate_auc takes a preprocessed features-by-cells "
                    "(genes-by-cells for scRNA-seq) matrix and metadata. "
                    "If batch effects are present, these should be accounted for. "
                    "calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")"
                ),
                "command_or_code": "augur = calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")",
                "function_calls": ["calculate_auc"],
            }
        ]
    }

    bio = infer_bio_contract(trace, paper_sections=[])["bio_contract"]

    assert bio["modality"]["primary"]["value"] == "scRNA-seq"
    assert bio["input_matrix_state"]["preprocessed_required"]["value"] is True
    assert bio["input_matrix_state"]["raw_counts_required"]["value"] is False
    assert bio["input_matrix_state"]["batch_effects_accounted_for"]["value"] is True
    assert bio["metadata_requirements"]["celltype_key"]["value"] == "cell_type"
    assert "cell.type" in bio["metadata_requirements"]["celltype_key"]["aliases"]
    assert bio["metadata_requirements"]["condition_key"]["value"] == "condition"


def test_bio_contract_prefers_paired_ribo_rna_over_bulk_and_handles_negated_normalization():
    trace = {
        "workflow_steps": [
            {
                "step_id": "README.md:section:inputs",
                "evidence_id": "README.md:section:inputs",
                "code_preview": (
                    "Calculating DTEGs requires count matrices for both Ribo-seq and RNA-seq. "
                    "These should be raw counts, not normalized or batch corrected. "
                    "Each row is a gene and each column is a sample. "
                    "SampleID Condition SeqType Batch. DESeq2 is used downstream."
                ),
                "command_or_code": "Rscript --vanilla DTEG.R ribo_counts.txt rna_counts.txt sample_info.txt 1",
                "function_calls": ["Rscript", "DESeq2::DESeqDataSetFromMatrix"],
            }
        ]
    }

    bio = infer_bio_contract(trace, paper_sections=[])["bio_contract"]

    assert bio["modality"]["primary"]["value"] == "Ribo-seq/RNA-seq"
    assert bio["input_matrix_state"]["raw_counts_required"]["value"] is True
    assert bio["input_matrix_state"]["normalized_allowed"]["value"] is False
    assert bio["input_matrix_state"]["normalized_input_disallowed"]["value"] is True
    assert bio["input_matrix_state"]["batch_corrected_input_disallowed"]["value"] is True
    ribo = bio["modality_contracts"]["ribo_rna_seq"]
    assert ribo["metadata"]["sample_key"]["value"] == "sample"
    assert "SampleID" in ribo["metadata"]["sample_key"]["aliases"]
    assert ribo["metadata"]["seqtype_key"]["value"] == "SeqType"
