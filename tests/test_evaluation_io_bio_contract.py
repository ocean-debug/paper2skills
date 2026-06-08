from __future__ import annotations

from paper2skill.evaluation.compare_bio_contract import compare_bio_contract
from paper2skill.evaluation.compare_io_contract import compare_io_contract


def test_io_contract_metrics_compare_format_metadata_and_output():
    gold = {
        "primary_input": {"accepted_formats": ["h5ad", "AnnData_object"]},
        "metadata": {"condition_key": {"required": True, "semantic": "condition"}},
        "output": {"latent_embedding": {"location": "adata.obsm['X_demo']", "required": True}},
    }
    generated = {
        "io_contract": {
            "input_contract": {
                "required": {
                    "primary_data": {
                        "format": {"value": "h5ad"},
                        "metadata_keys": {"condition_key": {"value": "condition"}},
                    }
                }
            },
            "output_contract": {"tutorial_outputs": ["adata.obsm['X_demo']"]},
        }
    }

    result = compare_io_contract(gold, generated)

    assert result["metrics"]["input_format_accuracy"] == 1.0
    assert result["metrics"]["metadata_key_accuracy"] == 1.0
    assert result["metrics"]["output_contract_accuracy"] > 0


def test_bio_contract_metrics_compare_modality_matrix_and_not_confirmed():
    gold = {"modality": "scRNA-seq", "matrix_state": {"raw_counts_required": True}, "species": {"value": "not_confirmed"}}
    generated = {
        "bio_contract": {
            "bio_contract": {
                "modality": {"primary": {"value": "scRNA-seq"}},
                "input_matrix_state": {"raw_counts_required": {"value": True}, "matrix_transformations": ["raw_counts_loaded"]},
                "organism": {"species_supported": {"value": "not_confirmed"}},
            }
        }
    }

    result = compare_bio_contract(gold, generated)

    assert result["metrics"]["modality_accuracy"] == 1.0
    assert result["metrics"]["matrix_state_accuracy"] == 1.0
    assert result["metrics"]["not_confirmed_correctness"] == 1.0


def test_io_and_bio_aliases_match_equivalent_contract_terms():
    io_gold = {
        "primary_inputs": {"ribo_count_matrix": {"format": "tabular_count_matrix"}},
        "metadata": {"cell_type_key": {"required": True}, "sample_info_file": {"required_columns": ["SampleID", "SeqType"]}},
    }
    io_generated = {
        "io_contract": {
            "input_contract": {
                "required": {
                    "primary_data": {
                        "format": {"value": "count_matrix"},
                        "metadata_keys": {
                            "celltype_key": {"value": "cell_type"},
                            "sample_key": {"value": "sample"},
                            "seqtype_key": {"value": "SeqType"},
                        },
                    }
                }
            }
        }
    }
    bio_gold = {"modality": ["Ribo-seq", "RNA-seq"], "matrix_state": {"raw_counts_required": True}}
    bio_generated = {
        "bio_contract": {
            "bio_contract": {
                "modality": {"primary": {"value": "Ribo-seq/RNA-seq"}},
                "input_matrix_state": {"raw_counts_required": {"value": True}, "matrix_transformations": ["raw_counts_loaded"]},
            }
        }
    }

    assert compare_io_contract(io_gold, io_generated)["metrics"]["input_format_accuracy"] == 1.0
    assert compare_io_contract(io_gold, io_generated)["metrics"]["metadata_key_accuracy"] == 1.0
    assert compare_bio_contract(bio_gold, bio_generated)["metrics"]["modality_accuracy"] == 1.0
    assert compare_bio_contract(bio_gold, bio_generated)["metrics"]["matrix_state_accuracy"] == 1.0


def test_io_aliases_match_h5ad_and_rds_single_cell_objects():
    h5ad_gold = {"primary_input": {"accepted_objects": ["AnnData_object"]}}
    h5ad_generated = {
        "io_contract": {
            "input_contract": {
                "required": {"primary_data": {"format": {"value": "h5ad"}, "metadata_keys": {}}}
            }
        }
    }
    rds_gold = {"primary_input": {"accepted_objects": ["Seurat_object", "SingleCellExperiment_object"]}}
    rds_generated = {
        "io_contract": {
            "input_contract": {
                "required": {"primary_data": {"format": {"value": "rds"}, "metadata_keys": {}}}
            }
        }
    }

    assert compare_io_contract(h5ad_gold, h5ad_generated)["metrics"]["input_format_accuracy"] == 1.0
    assert compare_io_contract(rds_gold, rds_generated)["metrics"]["input_format_accuracy"] == 1.0
