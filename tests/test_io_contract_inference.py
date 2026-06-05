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


def test_io_contract_uses_bulk_modality_rules_for_count_matrix():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "counts <- read.csv('counts.csv')\ndds <- DESeqDataSetFromMatrix(countData=counts, colData=meta, design=~condition)",
                "command_or_code": "DESeq2::DESeqDataSetFromMatrix(countData=counts, colData=meta, design=~condition)",
                "function_calls": ["DESeq2::DESeqDataSetFromMatrix"],
                "read_files": ["counts.csv", "metadata.tsv"],
                "inputs": [],
            }
        ]
    }
    bio_contract = {"bio_contract": {"modality": {"primary": {"value": "bulk RNA-seq"}}}}

    contract = infer_io_contract(trace, bio_contract)

    primary_data = contract["input_contract"]["required"]["primary_data"]
    assert primary_data["format"]["value"] == "count_matrix"
    assert primary_data["metadata_keys"]["condition_key"]["value"] == "condition"


def test_io_contract_marks_conflicting_primary_formats_not_confirmed():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "adata = sc.read_10x_mtx('data/')\nobj <- readRDS('object.rds')",
                "command_or_code": "sc.read_10x_mtx('data/')\nreadRDS('object.rds')",
                "function_calls": ["sc.read_10x_mtx", "readRDS"],
                "read_files": ["object.rds"],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    fmt = contract["input_contract"]["required"]["primary_data"]["format"]
    assert fmt["value"] == "not_confirmed"
    assert fmt["confidence"] == "low"
    assert set(fmt["conflicts"]) == {"10x_mtx", "rds"}


def test_io_contract_metadata_csv_does_not_conflict_with_primary_h5ad():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "adata = sc.read_h5ad('adata.h5ad')\nmetadata = pd.read_csv('metadata.csv')",
                "command_or_code": "adata = sc.read_h5ad('adata.h5ad')\nmetadata = pd.read_csv('metadata.csv')",
                "function_calls": ["sc.read_h5ad", "pd.read_csv"],
                "read_files": ["adata.h5ad", "metadata.csv"],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    fmt = contract["input_contract"]["required"]["primary_data"]["format"]
    assert fmt["value"] == "h5ad"
    assert "conflicts" not in fmt
