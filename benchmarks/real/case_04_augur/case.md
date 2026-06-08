# Benchmark Case 04 — Augur

## Basic information

```yaml
case_id: case_04_augur
tool_name: Augur
paper_title: "Cell type prioritization in single-cell data"
paper_url: "https://www.nature.com/articles/s41587-020-0605-1"
repo_url: "https://github.com/neurorestore/Augur"
tutorial_url: "https://github.com/neurorestore/Augur"
task_category:
  - single_cell
  - cell_type_prioritization
  - perturbation_response_scoring
primary_language: R
expected_adapter_type: r_script_or_r_package
expected_initial_adapter_status: verified
```

## Why this case is useful

Augur is a strong R benchmark for testing:

```text
R package dependency mining
GitHub-based R installation instructions
genes-by-cells / features-by-cells matrix contract
metadata requirement inference
Seurat / monocle3 / SingleCellExperiment object support
calculate_auc API extraction
AUC output contract
```

This case is useful because its input contract is clearly stated in the README and differs from AnnData-centric Python workflows.

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
      - "R"
      - "README.md"
      - "DESCRIPTION"
      - "NAMESPACE"

  tutorial:
    expected_url: "https://github.com/neurorestore/Augur"
    expected_readme_sections:
      - "System requirements"
      - "Installation"
      - "Usage"
      - "Demonstration"
```

---

## Dependency contract gold standard

```yaml
dependency_contract_gold:
  language:
    python: false
    r: true

  r_required:
    - dplyr
    - purrr
    - tibble
    - magrittr
    - tester
    - Matrix
    - sparseMatrixStats
    - parsnip
    - recipes
    - rsample
    - yardstick
    - pbmcapply
    - lmtest
    - rlang
    - glmnet
    - randomForest

  r_optional_or_object_support:
    - Seurat
    - monocle3
    - SingleCellExperiment

  github_install:
    - "Bioconductor/MatrixGenerics"
    - "const-ae/sparseMatrixStats"
    - "neurorestore/Augur"

  expected_dependency_metrics:
    r_required_recall_min: 0.70
    optional_object_support_recall_min: 0.60
```

---

## Tutorial selection gold standard

```yaml
tutorial_selection_gold:
  should_select:
    - "README.md#Usage"
    - "README.md#Demonstration"

  expected_tutorial_signals:
    - "calculate_auc"
    - "calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")"
    - "calculate_auc(sc)"
    - "genes-by-cells"
    - "features-by-cells"
    - "cell_type_col"
    - "label_col"
    - "sc_sim"
    - "augur$AUC"
```

---

## Workflow DAG gold standard

```yaml
workflow_dag_gold:
  nodes:
    - id: load_library
      type: load_package
      expected_calls:
        - "library(Augur)"

    - id: load_input_matrix_and_metadata
      type: load_data
      expected_inputs:
        - expr
        - meta
      expected_state:
        matrix_orientation: features_by_cells
        matrix_semantics: genes_by_cells_scRNA_seq

    - id: validate_metadata
      type: input_validation
      expected_metadata:
        - cell.type
        - cell_type
        - condition
        - label

    - id: run_calculate_auc
      type: model_training_or_scoring
      expected_calls:
        - "calculate_auc"
        - "calculate_auc(expr, meta, cell_type_col = \"cell.type\", label_col = \"condition\")"
        - "calculate_auc(sc)"
      expected_inputs:
        - expr_or_seurat_object
        - meta
        - cell_type_col
        - label_col
      output_objects:
        - augur

    - id: extract_auc
      type: output_extraction
      expected_outputs:
        - "augur$AUC"

  edges:
    - load_library -> load_input_matrix_and_metadata
    - load_input_matrix_and_metadata -> validate_metadata
    - validate_metadata -> run_calculate_auc
    - run_calculate_auc -> extract_auc
```

---

## IO contract gold standard

```yaml
io_contract_gold:
  primary_input:
    accepted_objects:
      - genes_by_cells_matrix
      - features_by_cells_matrix
      - Seurat_object
      - monocle3_object
      - SingleCellExperiment_object
    matrix_orientation:
      expected: features_by_cells
    matrix_state:
      expected: preprocessed
      raw_counts_required: false

  metadata:
    cell_type_key:
      required: true
      defaults:
        - cell.type
        - cell_type
      override_arg: cell_type_col
    label_key:
      required: true
      defaults:
        - condition
        - label
      override_arg: label_col
      semantic: sample_or_condition_label_to_predict
    seurat_meta_data:
      container: sc@meta.data
      required_columns:
        - cell_type
        - label

  output:
    auc_table:
      location: "augur$AUC"
      columns:
        - cell_type
        - auc
      required: true
```

---

## Bio contract gold standard

```yaml
bio_contract_gold:
  modality: scRNA-seq
  task: cell_type_prioritization
  input_state:
    preprocessed: true
    batch_effects_should_be_accounted_for: true
    preprocessing_required_before_augur: true
  classifier_goal:
    predict_experimental_condition_from_molecular_measurements_per_cell_type: true
  biological_constraints:
    - input_scRNA_seq_should_be_preprocessed
    - batch_effects_should_be_removed_or_accounted_for_before_input
  species:
    value: not_confirmed
  gene_id_type:
    value: not_confirmed
```

---

## Adapter behavior gold standard

```yaml
adapter_behavior_gold:
  expected_adapter_type: r_script_or_r_package
  expected_initial_status: verified

  reason: Augur is an R package with a documented calculate_auc API and a small documented example workflow suitable for reviewed package/demo execution.

  demo_run:
    allowed: true
    expected_demo_data: sc_sim
    expected_output: augur$AUC

  non_demo_run:
    expected_behavior: validate_preprocessed_single_cell_input_before_execution

  must_not:
    - auto_install_without_user_approval
    - run_without_cell_type_and_label_metadata
    - claim_batch_effect_correction_was_performed_by_augur
```

---

## Evidence expectations

```yaml
evidence_expectations:
  high_priority_sources:
    - repo_readme
    - DESCRIPTION
    - NAMESPACE
    - R_source

  required_claims_with_evidence:
    - calculate_auc main function
    - calculate_auc(expr, meta, cell_type_col = "cell.type", label_col = "condition")
    - calculate_auc(sc) for Seurat object input
    - genes-by-cells scRNA-seq input matrix
    - features-by-cells input matrix
    - metadata requires cell type annotations and sample labels to be predicted
    - Seurat sc@meta.data contains cell_type and label columns
    - output is AUC table
    - output is available at augur$AUC
    - supports Seurat / monocle3 / SingleCellExperiment objects
    - installation via devtools::install_github("neurorestore/Augur")
```

---

## Quantitative metrics for this case

```yaml
metrics:
  dependency:
    r_required_recall: target >= 0.70
    object_support_recall: target >= 0.60
    github_dependency_detection: target >= 0.60

  workflow:
    node_recall: target >= 0.70
    edge_recall: target >= 0.60
    step_type_accuracy: target >= 0.70

  io_bio_contract:
    matrix_orientation_accuracy: binary
    metadata_key_accuracy: target >= 0.90
    output_contract_accuracy: target >= 0.90

  adapter_safety:
    r_adapter_type_accuracy: binary
    verified_status_correctness: binary
```

---

## Expected failure modes

```text
1. Tool may infer cells-by-features instead of features-by-cells.
2. Tool may miss label_col/cell_type_col override arguments or the cell.type/condition alias pair.
3. Tool may miss optional Seurat/monocle3/SingleCellExperiment support.
4. Tool may treat sc_sim demonstration as required user input.
5. Tool may fail to distinguish R package API from Rscript CLI.
```
