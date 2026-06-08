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


def test_io_contract_infers_ribo_rna_count_matrix_and_metadata_aliases():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "Rscript --vanilla method.R ribo.tsv rna.tsv sample_info.tsv 1 1 0\n# Ribo-seq count matrix, RNA-seq count matrix, genes-by-samples\n# SampleID Condition SeqType Batch",
                "command_or_code": "Rscript --vanilla method.R ribo.tsv rna.tsv sample_info.tsv 1 1 0",
                "function_calls": ["Rscript"],
                "read_files": ["ribo.tsv", "rna.tsv", "sample_info.tsv"],
                "inputs": [],
            }
        ]
    }
    bio_contract = {"bio_contract": {"modality": {"primary": {"value": "Ribo-seq/RNA-seq"}}}}

    contract = infer_io_contract(trace, bio_contract)

    primary_data = contract["input_contract"]["required"]["primary_data"]
    assert primary_data["format"]["value"] == "count_matrix"
    assert primary_data["matrix_orientation"]["value"] == "genes_by_samples"
    assert primary_data["metadata_keys"]["sample_key"]["value"] == "sample"
    assert primary_data["metadata_keys"]["condition_key"]["value"] == "condition"
    assert primary_data["metadata_keys"]["seqtype_key"]["value"] == "SeqType"
    assert primary_data["metadata_keys"]["batch_key"]["value"] == "Batch"


def test_io_contract_prefers_h5ad_when_prose_also_mentions_anndata():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:cell_001",
                "code_preview": "train = sc.read('.train_kang.h5ad')",
                "command_or_code": "AnnData object stored as .h5ad\ntrain = sc.read('.train_kang.h5ad')",
                "function_calls": ["sc.read"],
                "read_files": [".train_kang.h5ad"],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    fmt = contract["input_contract"]["required"]["primary_data"]["format"]
    assert fmt["value"] == "h5ad"


def test_io_contract_does_not_treat_scenario_text_as_sce_object():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:section_001",
                "command_or_code": "This scenario predicts perturbation responses from .train_kang.h5ad.",
                "function_calls": [],
                "read_files": [],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    fmt = contract["input_contract"]["required"]["primary_data"]["format"]
    assert fmt["value"] == "h5ad"


def test_io_contract_prefers_rds_for_r_single_cell_object_with_matrix_prose():
    trace = {
        "workflow_steps": [
            {
                "step_id": "tutorial_001:section_001",
                "code_preview": "Input can be a Seurat object, SingleCellExperiment object, or features-by-cells matrix.",
                "command_or_code": "Input can be a Seurat object, SingleCellExperiment object, or features-by-cells matrix.",
                "function_calls": [],
                "read_files": [],
                "inputs": [],
            }
        ]
    }

    contract = infer_io_contract(trace)

    fmt = contract["input_contract"]["required"]["primary_data"]["format"]
    assert fmt["value"] == "rds"


def test_io_contract_extracts_augur_like_auc_output_and_metadata_aliases():
    trace = {
        "workflow_steps": [
            {
                "step_id": "README.md:section:usage",
                "code_preview": (
                    "The main function calculate_auc takes a preprocessed genes-by-cells matrix. "
                    "augur = calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")\n"
                    "Cell type prioritizations are stored in the AUC data frame.\n"
                    "head(augur$AUC, 5)"
                ),
                "command_or_code": "augur = calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")\naugur$AUC",
                "function_calls": ["calculate_auc"],
                "read_files": [],
                "inputs": [],
            }
        ]
    }
    bio_contract = {
        "bio_contract": {
            "modality": {"primary": {"value": "scRNA-seq"}},
            "input_matrix_state": {
                "preprocessed_required": {"value": True, "confidence": "high", "evidence": ["README.md:section:usage"]},
                "matrix_transformations": ["preprocessed"],
            },
            "metadata_requirements": {
                "celltype_key": {"value": "cell_type", "confidence": "medium", "evidence": ["tutorial_metadata_key"], "aliases": ["cell.type"]},
                "condition_key": {"value": "condition", "confidence": "medium", "evidence": ["tutorial_metadata_key"]},
                "label_key": {"value": "label", "confidence": "medium", "evidence": ["tutorial_metadata_key"], "aliases": ["label_col"]},
            },
        }
    }

    contract = infer_io_contract(trace, bio_contract)

    primary_data = contract["input_contract"]["required"]["primary_data"]
    assert primary_data["matrix_state"]["value"] == "preprocessed"
    assert primary_data["matrix_orientation"]["value"] == "genes_by_cells"
    assert primary_data["metadata_keys"]["celltype_key"]["aliases"] == ["cell.type"]
    outputs = contract["output_contract"]
    assert "augur$AUC" in outputs["tutorial_outputs"]
    assert outputs["semantic_outputs"][0]["name"] == "auc_table"
    assert outputs["semantic_outputs"][0]["columns"] == ["cell_type", "auc"]


def test_io_contract_extracts_paired_ribo_rna_outputs_from_rscript_workflow():
    trace = {
        "workflow_steps": [
            {
                "step_id": "DTEG.R:line:1",
                "code_preview": (
                    "Rscript --vanilla DTEG.R ribo_counts.txt rna_counts.txt sample_info.txt 1\n"
                    "Ribo-seq count matrix, RNA-seq count matrix, genes-by-samples\n"
                    "SampleID Condition SeqType Batch\n"
                    "system(\"mkdir Results\")\n"
                    "write.table(res, \"fold_changes/deltaTE.txt\")\n"
                    "write.table(rownames(res), \"gene_lists/DTEGs.txt\")"
                ),
                "command_or_code": "Rscript --vanilla DTEG.R ribo_counts.txt rna_counts.txt sample_info.txt 1",
                "function_calls": ["Rscript"],
                "read_files": ["ribo_counts.txt", "rna_counts.txt", "sample_info.txt"],
                "write_files": ["fold_changes/deltaTE.txt", "gene_lists/DTEGs.txt"],
                "inputs": [],
            }
        ]
    }
    bio_contract = {
        "bio_contract": {
            "modality": {"primary": {"value": "Ribo-seq/RNA-seq"}},
            "input_matrix_state": {
                "raw_counts_required": {"value": True, "confidence": "high", "evidence": ["README.md:section:inputs"]},
                "normalized_input_disallowed": {"value": True, "confidence": "high", "evidence": ["README.md:section:inputs"]},
                "batch_corrected_input_disallowed": {"value": True, "confidence": "high", "evidence": ["README.md:section:inputs"]},
                "matrix_transformations": ["raw_counts_loaded"],
            },
            "metadata_requirements": {
                "sample_key": {"value": "sample", "confidence": "medium", "evidence": ["tutorial_metadata_key"], "aliases": ["SampleID"]},
                "condition_key": {"value": "condition", "confidence": "medium", "evidence": ["tutorial_metadata_key"], "aliases": ["Condition"]},
                "seqtype_key": {"value": "SeqType", "confidence": "medium", "evidence": ["tutorial_metadata_key"]},
                "batch_key": {"value": "Batch", "confidence": "medium", "evidence": ["tutorial_metadata_key"]},
            },
        }
    }

    contract = infer_io_contract(trace, bio_contract)

    primary_data = contract["input_contract"]["required"]["primary_data"]
    assert primary_data["format"]["value"] == "count_matrix"
    assert primary_data["matrix_state"]["value"] == "raw_counts"
    assert primary_data["matrix_orientation"]["value"] == "genes_by_samples"
    assert primary_data["metadata_keys"]["sample_key"]["aliases"] == ["SampleID"]
    outputs = contract["output_contract"]
    assert "dteg_result_table" in outputs["tutorial_outputs"]
    assert "gene_lists/DTEGs.txt" in outputs["tutorial_outputs"]
    assert any(item["name"] == "result_directory" for item in outputs["semantic_outputs"])
