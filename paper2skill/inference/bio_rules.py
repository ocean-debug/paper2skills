from __future__ import annotations

MODALITY_RULES = {
    "perturb-seq": ["perturb-seq", "perturbation", "perturbed", "gene perturbation", "single-gene", "multi-gene"],
    "scRNA-seq": ["single-cell RNA", "scRNA-seq", "single cell", "AnnData", "Seurat", "SingleCellExperiment", "scanpy", "h5ad", "10x"],
    "spatial_transcriptomics": ["spatial transcriptomics", "Visium", "Slide-seq", "MERFISH", "spatial", "Squidpy"],
    "ribo_rna_seq": ["Ribo-seq", "RNA-seq", "translational efficiency", "SeqType", "ribosome profiling", "DTEG"],
    "bulk_RNA-seq": ["bulk RNA", "bulk RNA-seq", "DESeq2", "edgeR", "limma", "counts matrix", "countData", "sample information"],
    "scATAC-seq": ["scATAC", "Signac", "ArchR", "peak matrix", "fragments.tsv"],
    "multiome": ["multiome", "RNA + ATAC", "paired RNA and ATAC"],
}

MATRIX_STATE_RULES = {
    "raw_counts_loaded": ["raw counts", "raw count matrix", "count matrix", "counts matrix", "countData", "read_10x_mtx", "Read10X", "DESeqDataSetFromMatrix", "counts slot", "layers['counts']", "genes-by-samples", "genes by samples"],
    "preprocessed": ["preprocessed", "pre-processed", "pre processed", "pre-process your data", "pre-processed your data"],
    "normalized": ["NormalizeData", "normalize_total", "CPM", "TPM", "size factor"],
    "log1p_transformed": ["log1p", "log-normalized", "LogNormalize"],
    "scaled": ["ScaleData", "scale", "z-score", "standardized"],
}

GENE_ID_RULES = {
    "gene_symbol": ["gene symbol", "HGNC", "GeneSymbol", "symbol"],
    "ensembl_id": ["Ensembl", "ENSG", "ENSMUSG"],
    "entrez_id": ["Entrez", "NCBI gene id"],
}

SPECIES_RULES = {
    "human": ["human", "Homo sapiens", "hg19", "hg38", "GRCh37", "GRCh38"],
    "mouse": ["mouse", "Mus musculus", "mm10", "mm39", "GRCm38", "GRCm39"],
    "macaque": ["macaque", "Macaca", "rheMac"],
}


def match_rules(text: str, rules: dict[str, list[str]]) -> list[str]:
    lower = text.lower()
    return [value for value, words in rules.items() if any(word.lower() in lower for word in words)]
