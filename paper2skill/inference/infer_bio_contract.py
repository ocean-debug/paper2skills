from __future__ import annotations

from typing import Any


def default_bio_contract() -> dict[str, Any]:
    return {
        "bio_contract": {
            "modality": {"primary": "not_confirmed", "secondary": "not_confirmed"},
            "organism": {"species_supported": "not_confirmed", "genome_build": "not_confirmed", "gene_id_type": "not_confirmed"},
            "input_matrix_state": {
                "raw_counts_required": "not_confirmed",
                "normalized_allowed": "not_confirmed",
                "log_transformed_allowed": "not_confirmed",
                "matrix_orientation": "not_confirmed",
            },
            "metadata_requirements": {
                "celltype_key": "not_confirmed",
                "sample_key": "not_confirmed",
                "batch_key": "not_confirmed",
                "condition_key": "not_confirmed",
            },
            "minimum_data_requirements": {
                "min_cells": "not_confirmed",
                "min_genes": "not_confirmed",
                "min_cells_per_group": "not_confirmed",
            },
            "reference_resources": {
                "genome": "not_confirmed",
                "annotation": "not_confirmed",
                "database": "not_confirmed",
                "grn": "not_confirmed",
                "ligand_receptor_database": "not_confirmed",
            },
            "statistical_contract": {
                "multiple_testing": "not_confirmed",
                "fdr_threshold": "not_confirmed",
                "metric": "not_confirmed",
            },
            "interpretation_boundary": {
                "dry_run_is_not_biological_result": True,
                "demo_run_is_not_user_data_validation": True,
                "cross_species_mapping_requires_confirmation": True,
            },
        }
    }
