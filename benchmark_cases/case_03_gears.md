# Benchmark Case 03 — GEARS

## Basic information

```yaml
case_id: case_03_gears
tool_name: GEARS
paper_title: "GEARS: Predicting transcriptional outcomes of novel multi-gene perturbations"
paper_url: "https://www.nature.com/articles/s41587-023-01905-6"
repo_url: "https://github.com/snap-stanford/GEARS"
tutorial_url: "https://github.com/snap-stanford/GEARS/tree/master/demo"
task_category:
  - perturb_seq
  - single_cell
  - gene_perturbation_prediction
  - geometric_deep_learning
primary_language: Python
expected_adapter_type: python_api
expected_initial_adapter_status: candidate
```

## Why this case is useful

GEARS is a strong benchmark for testing:

```text
PyTorch Geometric dependency detection
PertData / GEARS API extraction
demo notebook discovery
single-gene and multi-gene perturbation workflow
AnnData metadata contract
condition/cell_type/gene_name requirements
adapter blocking for GPU/training-heavy workflows
```

This case should stress-test complex perturb-seq IO/Bio contract inference.

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

  repo:
    expected_clone_or_index: true
    expected_commit_sha: true
    expected_files_or_dirs:
      - "gears"
      - "demo"
      - "requirements.txt"
      - "setup.py"
      - "README.md"

  tutorial:
    expected_url: "https://github.com/snap-stanford/GEARS/tree/master/demo"
    expected_demo_files:
      - "data_tutorial.ipynb"
      - "model_tutorial.ipynb"
      - "tutorial_inference_Norman.ipynb"
      - "tutorial_plot_top20_DE.ipynb"
      - "tutorial_uncertainty.ipynb"
```

---

## Dependency contract gold standard

```yaml
dependency_contract_gold:
  language:
    python: true
    r: false

  python_required:
    - cell-gears
    - torch
    - torch-geometric
    - scanpy
    - anndata

  python_optional:
    - numpy
    - pandas
    - scipy

  install_evidence:
    pip:
      - "pip install cell-gears"
    prerequisite:
      - "Install PyG"

  system_or_hardware:
    gpu_optional: true
    cuda_optional: true

  expected_dependency_metrics:
    required_dependency_recall_min: 0.75
    pyg_detection_required: true
```

---

## Tutorial selection gold standard

```yaml
tutorial_selection_gold:
  should_select:
    - "demo/data_tutorial.ipynb"
    - "demo/model_tutorial.ipynb"
    - "demo/tutorial_inference_Norman.ipynb"

  should_rank_high:
    - "model_tutorial.ipynb"
    - "tutorial_inference_Norman.ipynb"

  expected_tutorial_signals:
    - "PertData"
    - "GEARS"
    - "prepare_split"
    - "get_dataloader"
    - "model_initialize"
    - "train"
    - "predict"
    - "GI_predict"
```

---

## Workflow DAG gold standard

```yaml
workflow_dag_gold:
  nodes:
    - id: initialize_pertdata
      type: load_data
      expected_calls:
        - "PertData"
      output_objects:
        - pert_data

    - id: load_dataset
      type: load_data
      expected_calls:
        - "pert_data.load"
      expected_parameters:
        data_name: norman_or_other

    - id: prepare_split
      type: data_split
      expected_calls:
        - "prepare_split"
      expected_parameters:
        split: simulation

    - id: get_dataloader
      type: dataloader
      expected_calls:
        - "get_dataloader"
      output_objects:
        - dataloader

    - id: initialize_model
      type: model_initialization
      expected_calls:
        - "GEARS"
        - "model_initialize"
      output_objects:
        - gears_model

    - id: train_model
      type: model_training
      expected_calls:
        - "train"

    - id: save_or_load_model
      type: model_checkpoint
      expected_calls:
        - "save_model"
        - "load_pretrained"

    - id: predict_perturbation
      type: prediction
      expected_calls:
        - "predict"
      expected_inputs:
        - perturbation_gene_list

    - id: gene_interaction_prediction
      type: prediction
      expected_calls:
        - "GI_predict"

  edges:
    - initialize_pertdata -> load_dataset
    - load_dataset -> prepare_split
    - prepare_split -> get_dataloader
    - get_dataloader -> initialize_model
    - initialize_model -> train_model
    - train_model -> save_or_load_model
    - save_or_load_model -> predict_perturbation
    - predict_perturbation -> gene_interaction_prediction
```

---

## IO contract gold standard

```yaml
io_contract_gold:
  primary_input:
    object_type: AnnData_or_GEARS_PertData
    accepted_formats:
      - AnnData_object
      - preprocessed_GEARS_dataset
    required_adata_var:
      - gene_name
    required_adata_obs:
      - condition
      - cell_type

  perturbation_metadata:
    condition_key:
      required: true
      semantic: perturbation identity
    cell_type_key:
      required: true
      semantic: cell type
    perturbation_query:
      format: list_of_gene_lists
      examples:
        - ["CBL", "CNN1"]
        - ["FEV"]

  output:
    predicted_transcriptional_response:
      required: true
    GI_prediction:
      required: optional
    top_DE_plot:
      required: optional
```

---

## Bio contract gold standard

```yaml
bio_contract_gold:
  modality: perturb-seq
  base_modality: scRNA-seq
  task: perturbation_response_prediction
  perturbation_type:
    - single_gene
    - multi_gene
  input_requirements:
    multiple_cells_per_perturbation: expected
    multiple_perturbation_types: expected
  unsupported_or_caution:
    - training_across_multiple_cell_types_not_designed
    - bulk_sequencing_not_tested
    - combinatorial_prediction_requires_some_combinatorial_training_data
```

---

## Adapter behavior gold standard

```yaml
adapter_behavior_gold:
  expected_adapter_type: python_api
  expected_initial_status: candidate

  reason: model training may require GPU, PyG, downloaded/preprocessed datasets, and perturbation-specific metadata review

  non_demo_run:
    expected_behavior: blocked_until_reviewed

  demo_run:
    allowed: true
    expected_behavior: static_or_small_demo_only

  must_not:
    - auto_download_large_perturb_seq_data_without_confirmation
    - auto_train_gpu_model_without_review
    - mark_adapter_ready_from_notebook_presence_alone
```

---

## Evidence expectations

```yaml
evidence_expectations:
  high_priority_sources:
    - repo_readme
    - demo_notebooks
    - setup_or_requirements

  required_claims_with_evidence:
    - GEARS predicts single and multi-gene perturbation responses
    - PyG prerequisite
    - cell-gears installation
    - required adata.var gene_name
    - required adata.obs condition and cell_type
    - caution about multi-cell-type training and bulk data
```

---

## Quantitative metrics for this case

```yaml
metrics:
  dependency:
    pyg_detection: binary
    cell_gears_detection: binary
    python_required_recall: target >= 0.70

  tutorial:
    demo_notebook_recall: target >= 0.80
    tutorial_ranking_correctness: target >= 0.60

  workflow:
    node_recall: target >= 0.70
    edge_recall: target >= 0.60
    step_type_accuracy: target >= 0.70

  io_bio_contract:
    perturbation_metadata_accuracy: target >= 0.80
    adata_required_fields_accuracy: target >= 0.80
    caution_statement_recall: target >= 0.60

  adapter_safety:
    candidate_status_correctness: binary
    large_training_block_correctness: binary
```

---

## Expected failure modes

```text
1. Tool may miss PyTorch Geometric as a prerequisite.
2. Tool may rank plotting notebook above model/inference tutorial.
3. Tool may miss adata.var['gene_name'] requirement.
4. Tool may miss adata.obs['condition'] and adata.obs['cell_type'].
5. Tool may incorrectly mark model training adapter as ready.
```
