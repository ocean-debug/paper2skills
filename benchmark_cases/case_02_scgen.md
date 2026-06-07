# Benchmark Case 02 — scGen

## Basic information

```yaml
case_id: case_02_scgen
tool_name: scGen
paper_title: "scGen predicts single-cell perturbation responses"
paper_url: "https://www.nature.com/articles/s41592-019-0494-8"
repo_url: "https://github.com/theislab/scgen"
tutorial_url: "https://scgen.readthedocs.io/en/stable/"
task_category:
  - single_cell
  - perturbation_prediction
  - generative_model
  - batch_removal
primary_language: Python
expected_adapter_type: python_api
expected_initial_adapter_status: candidate
```

## Why this case is useful

scGen is a benchmark for testing whether `paper2skills` can recover a single-cell perturbation-prediction workflow with:

```text
normalized AnnData input
condition labels
cell_type labels
optional batch labels
HVG recommendation
model training
perturbation prediction
batch-removal use case
```

It is especially useful for testing whether the builder can distinguish **raw counts**, **normalized/log-transformed training input**, and **condition/cell-type metadata requirements**.

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
      - "scgen"
      - "docs"
      - "pyproject.toml"
      - "setup.py"
      - "README.md"

  tutorial:
    expected_url: "https://scgen.readthedocs.io/en/stable/"
    expected_tutorial_pages:
      - "SCGEN: Perturbation Prediction"
      - "SCGEN: Batch-Removal"
```

---

## Dependency contract gold standard

```yaml
dependency_contract_gold:
  language:
    python: true
    r: false

  python_required:
    - scgen
    - scanpy
    - anndata
    - scvi-tools

  python_optional:
    - torch

  install_evidence:
    pip:
      - "pip install scgen"
      - "pip install git+https://github.com/theislab/scgen.git"

  expected_dependency_metrics:
    required_dependency_recall_min: 0.75
    optional_dependency_recall_min: 0.50
```

---

## Tutorial selection gold standard

```yaml
tutorial_selection_gold:
  should_select:
    - title_contains: "Perturbation Prediction"
    - title_contains: "Batch-Removal"

  expected_tutorial_signals:
    - "normalized data"
    - "cell_type"
    - "condition"
    - "control"
    - "perturbed"
    - "HVG"
    - "SCGEN"
```

---

## Workflow DAG gold standard

```yaml
workflow_dag_gold:
  nodes:
    - id: load_data
      type: load_data
      output_objects:
        - adata
      expected_calls:
        - "scanpy.read"
        - "read_h5ad"

    - id: normalize_total
      type: normalization
      input_objects:
        - adata
      output_objects:
        - adata
      expected_state_after:
        matrix_state: normalized

    - id: log1p
      type: transformation
      input_objects:
        - adata
      output_objects:
        - adata
      expected_state_after:
        matrix_state: log1p

    - id: highly_variable_genes
      type: feature_selection
      input_objects:
        - adata
      expected_state_after:
        hvg_selected: true

    - id: model_initialize
      type: model_initialization
      expected_calls:
        - "SCGEN"

    - id: train_model
      type: model_training
      expected_inputs:
        - adata
        - condition_key
        - cell_type_key

    - id: predict_perturbation
      type: prediction
      expected_inputs:
        - trained_model
        - target_cell_type_or_species
        - source_condition
        - target_condition

    - id: output_prediction
      type: save_output
      expected_outputs:
        - predicted_adata_or_expression_matrix

  edges:
    - load_data -> normalize_total
    - normalize_total -> log1p
    - log1p -> highly_variable_genes
    - highly_variable_genes -> model_initialize
    - model_initialize -> train_model
    - train_model -> predict_perturbation
    - predict_perturbation -> output_prediction
```

---

## IO contract gold standard

```yaml
io_contract_gold:
  primary_input:
    object_type: AnnData
    accepted_formats:
      - h5ad
      - AnnData_object
    matrix_state_before_training:
      expected: normalized_or_log1p
      raw_counts_allowed_before_preprocessing: true

  metadata:
    condition_key:
      required: true
      semantic: control_vs_perturbed
    cell_type_key:
      required: true
      semantic: cell type or species label
    batch_key:
      required_for_batch_removal: true
      required_for_perturbation_prediction: false

  output:
    predicted_response:
      type: AnnData_or_expression_matrix
      required: true
    batch_corrected_latent_or_expression:
      required_for_batch_removal: true
```

---

## Bio contract gold standard

```yaml
bio_contract_gold:
  modality: scRNA-seq
  task: perturbation_prediction
  perturbation_type:
    value: condition_level
    examples:
      - control
      - perturbed
  species:
    value: not_confirmed
    note: method can be used across species, but specific input species is case-dependent
  gene_id_type:
    value: not_confirmed
  recommended_preprocessing:
    - normalization
    - log1p
    - highly_variable_genes
```

---

## Adapter behavior gold standard

```yaml
adapter_behavior_gold:
  expected_adapter_type: python_api
  expected_initial_status: candidate

  reason: model training and perturbation prediction require explicit review of dataset labels, condition keys, and training time

  non_demo_run:
    expected_behavior: blocked_until_reviewed

  demo_run:
    allowed: true
    expected_behavior: safe_if_uses_small_documented_tutorial_data
```

---

## Evidence expectations

```yaml
evidence_expectations:
  high_priority_sources:
    - readthedocs_tutorial
    - repo_readme
    - api_docs

  required_claims_with_evidence:
    - scGen predicts perturbation response
    - normalized data recommended
    - condition labels required
    - cell_type labels required
    - pip install scgen
```

---

## Quantitative metrics for this case

```yaml
metrics:
  dependency:
    python_required_recall: target >= 0.75
    scvi_tools_detection: binary

  workflow:
    node_recall: target >= 0.70
    edge_recall: target >= 0.60
    step_type_accuracy: target >= 0.70

  io_bio_contract:
    condition_key_accuracy: binary
    cell_type_key_accuracy: binary
    matrix_state_accuracy: target >= 0.70
    perturbation_task_accuracy: binary

  safety:
    adapter_candidate_correctness: binary
    non_demo_block_correctness: binary
```

---

## Expected failure modes

```text
1. Tool may infer raw counts as required final input despite documentation recommending normalized data.
2. Tool may miss cell_type or condition metadata keys.
3. Tool may confuse batch-removal workflow with perturbation-prediction workflow.
4. Tool may overclaim that all species transfer is supported without dataset-specific validation.
5. Tool may mark adapter ready without checking label semantics.
```
