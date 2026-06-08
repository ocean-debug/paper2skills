# Benchmark Case 01 — CONCORD

## Basic information

```yaml
case_id: case_01_concord
tool_name: CONCORD
paper_title: "Revealing a coherent cell-state landscape across single-cell datasets with CONCORD"
paper_url: "https://www.nature.com/articles/s41587-025-02950-z"
repo_url: "https://github.com/Gartner-Lab/Concord"
tutorial_url: "https://qinzhu.github.io/Concord_documentation/"
task_category:
  - single_cell
  - representation_learning
  - batch_integration
  - denoising
  - dimensionality_reduction
primary_language: Python
expected_adapter_type: python_api
expected_initial_adapter_status: candidate
```

## Why this case is useful

CONCORD is a good benchmark for testing whether `paper2skills` can recover a modern Python single-cell workflow with:

```text
AnnData input
PyTorch dependency
feature selection
normalization/log1p preprocessing
model initialization
fit_transform
latent embedding output in adata.obsm
UMAP visualization
optional CUDA/FAISS dependencies
```

This case should stress-test both single-cell IO/Bio contract inference and Python API adapter detection.

---

## Source collection gold standard

```yaml
source_collection_gold:
  paper:
    expected_status: parsed_or_metadata_recorded
    expected_sections:
      - abstract_or_summary
      - methods
      - data_or_code_availability
    required: true

  repo:
    expected_clone_or_index: true
    expected_commit_sha: true
    expected_files_or_dirs:
      - "src/concord"
      - "pyproject.toml"
      - "setup.py"
      - "README.md"

  tutorial:
    expected_url: "https://qinzhu.github.io/Concord_documentation/"
    expected_tutorial_sections:
      - "Getting started"
      - "Tutorials"
      - "API"
    expected_candidate_keywords:
      - "PBMC3k"
      - "scRNA-seq minimal example"
      - "Concord"
```

---

## Dependency contract gold standard

```yaml
dependency_contract_gold:
  language:
    python: true
    r: false

  python_required:
    - concord-sc
    - torch
    - scanpy
    - anndata

  python_optional:
    - faiss-cpu
    - faiss-gpu
    - plotly

  install_evidence:
    pip:
      - "pip install concord-sc"
      - "pip install torch torchvision torchaudio"
    optional:
      - "pip install concord-sc[optional]"
      - "pip install faiss-cpu"
      - "pip install faiss-gpu"

  system_or_hardware:
    cuda_optional: true
    gpu_optional: true

  expected_dependency_metrics:
    required_dependency_recall_min: 0.75
    optional_dependency_recall_min: 0.50
```

---

## Tutorial selection gold standard

```yaml
tutorial_selection_gold:
  should_select:
    - title_contains: "Getting started"
    - title_contains: "PBMC3k"
    - title_contains: "scRNA-seq minimal example"

  should_exclude:
    - deprecated: true
    - no_code: true

  expected_tutorial_signals:
    - "import concord as ccd"
    - "import scanpy as sc"
    - "sc.datasets.pbmc3k_processed"
    - "sc.pp.normalize_total"
    - "sc.pp.log1p"
    - "ccd.Concord"
    - "fit_transform"
```

---

## Workflow DAG gold standard

```yaml
workflow_dag_gold:
  nodes:
    - id: load_package
      type: load_package
      expected_calls:
        - "import concord"
        - "import scanpy"
        - "import torch"

    - id: load_data
      type: load_data
      output_objects:
        - adata
      expected_calls:
        - "sc.datasets.pbmc3k_processed"

    - id: raw_counts_restore
      type: transformation
      input_objects:
        - adata
      output_objects:
        - adata
      expected_state_after:
        matrix_state: raw_counts

    - id: feature_selection
      type: feature_selection
      input_objects:
        - adata
      output_objects:
        - feature_list
      expected_calls:
        - "select_features"

    - id: normalization
      type: normalization
      input_objects:
        - adata
      output_objects:
        - adata
      expected_state_after:
        matrix_state: normalized

    - id: log_transform
      type: transformation
      input_objects:
        - adata
      output_objects:
        - adata
      expected_state_after:
        matrix_state: log1p

    - id: model_initialize
      type: model_initialization
      input_objects:
        - adata
        - feature_list
      output_objects:
        - cur_ccd
      expected_calls:
        - "ccd.Concord"

    - id: fit_transform
      type: model_training_or_embedding
      input_objects:
        - cur_ccd
      output_objects:
        - adata.obsm["Concord"]
      expected_calls:
        - "fit_transform"

    - id: visualization
      type: visualization
      input_objects:
        - adata
      expected_calls:
        - "run_umap"
        - "plot_embedding"

  edges:
    - load_data -> raw_counts_restore
    - raw_counts_restore -> feature_selection
    - raw_counts_restore -> normalization
    - feature_selection -> model_initialize
    - normalization -> log_transform
    - log_transform -> model_initialize
    - model_initialize -> fit_transform
    - fit_transform -> visualization
```

---

## IO contract gold standard

```yaml
io_contract_gold:
  primary_input:
    object_type: AnnData
    accepted_formats:
      - h5ad
      - 10x_mtx
      - AnnData_object
    matrix_state_before_model:
      expected: log1p
      raw_counts_evidence: input can start from raw counts
      preprocessing_required:
        - normalize_total
        - log1p

  metadata:
    batch_key:
      name: domain_key
      required_for_batch_integration: true
      default_if_single_batch: not_required
    cell_type_key:
      required: false
      value: not_confirmed

  output:
    latent_embedding:
      location: "adata.obsm['Concord']"
      required: true
    umap:
      location: "adata.obsm or generated plot"
      required: optional
    figures:
      - "Concord_UMAP.png"
      - "Concord_UMAP_3D.html"
```

---

## Bio contract gold standard

```yaml
bio_contract_gold:
  modality: scRNA-seq
  supported_input_object: AnnData
  species:
    value: not_confirmed
    reason: tutorial example does not make species a required input contract
  gene_id_type:
    value: not_confirmed
  minimum_data_requirements:
    cells: not_confirmed
    genes: not_confirmed
  external_resources:
    reference_genome: not_required
    pathway_database: optional_for_GO_enrichment
```

---

## Adapter behavior gold standard

```yaml
adapter_behavior_gold:
  expected_adapter_type: python_api
  expected_initial_status: candidate
  reason: real execution requires review of model training time, device, memory, and input data assumptions

  demo_run:
    allowed: true
    expected_behavior: safe_demo_or_blocked_if_no_demo

  non_demo_run:
    expected_behavior: blocked_until_reviewed
    must_not:
      - auto_install_torch
      - auto_download_large_data
      - execute_unknown_notebook
```

---

## Evidence expectations

```yaml
evidence_expectations:
  high_priority_sources:
    - official_documentation
    - repo_readme
    - tutorial_code
  required_claims_with_evidence:
    - package_installation
    - AnnData_input
    - normalization_and_log1p
    - fit_transform_output_to_adata_obsm
    - optional_gpu_or_cuda_dependency
```

---

## Quantitative metrics for this case

```yaml
metrics:
  source_collection:
    commit_sha_present: binary
    tutorial_candidate_recall: target >= 0.80

  dependency:
    python_required_recall: target >= 0.75
    optional_dependency_recall: target >= 0.50
    cuda_optional_detection: binary

  workflow:
    node_recall: target >= 0.70
    edge_recall: target >= 0.60
    step_type_accuracy: target >= 0.70
    object_state_accuracy: target >= 0.70

  io_bio_contract:
    input_object_accuracy: binary
    matrix_state_accuracy: target >= 0.70
    output_contract_accuracy: target >= 0.80

  adapter_safety:
    adapter_type_accuracy: binary
    candidate_or_blocked_correctness: binary
```

---

## Expected failure modes

```text
1. Tool may infer raw_counts as final model input instead of preprocessing to log1p.
2. Tool may miss optional FAISS/CUDA dependencies.
3. Tool may overclaim species support from paper background.
4. Tool may treat tutorial visualization as required output.
5. Tool may incorrectly mark adapter as ready without human review.
```
