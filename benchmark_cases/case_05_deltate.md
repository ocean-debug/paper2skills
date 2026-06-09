# Benchmark Case 05 — deltaTE / DTEG.R

## Basic information

```yaml
case_id: case_05_deltate
tool_name: deltaTE / DTEG.R
paper_title: "deltaTE: Detection of Translationally Regulated Genes by Integrative Analysis of Ribo-seq and RNA-seq Data"
paper_url: "https://currentprotocols.onlinelibrary.wiley.com/doi/10.1002/cpmb.108"
repo_url: "https://github.com/SGDDNB/translational_regulation"
tutorial_url: "https://github.com/SGDDNB/translational_regulation"
task_category:
  - ribo_seq
  - rna_seq
  - translational_efficiency
  - differential_translation
primary_language: R
expected_adapter_type: cli
expected_initial_adapter_status: candidate
```

## Why this case is useful

deltaTE / DTEG.R is a strong benchmark for CLI-style R workflows. It tests whether `paper2skills` can recover:

```text
Rscript entrypoint
positional CLI arguments
two raw count matrices
sample information file schema
Ribo-seq/RNA-seq paired design
batch covariate flag
DESeq2/apeglm dependency hints
raw count matrix requirement
genes-by-samples orientation
```

This case is especially useful for validating CLI adapter inference and strict IO contract extraction.

---

## Source collection gold standard

```yaml
source_collection_gold:
  paper:
    expected_status: parsed_or_metadata_recorded
    expected_sections:
      - protocol_or_methods
      - input_preparation
      - usage

  repo:
    expected_clone_or_index: true
    expected_commit_sha: true
    expected_files_or_dirs:
      - "DTEG.R"
      - "README.md"

  tutorial:
    expected_url: "https://github.com/SGDDNB/translational_regulation"
    expected_readme_sections:
      - "Preparing input files"
      - "Running script DTEG.R"
```

---

## Dependency contract gold standard

```yaml
dependency_contract_gold:
  language:
    python: false
    r: true

  r_required:
    - DESeq2
    - apeglm

  r_possible_required_or_inferred:
    - data.table
    - ggplot2
    - stats

  system_or_cli:
    - Rscript

  expected_dependency_metrics:
    r_required_recall_min: 0.60
    cli_entrypoint_detection_required: true
```

---

## Tutorial selection gold standard

```yaml
tutorial_selection_gold:
  should_select:
    - "README.md#Preparing input files"
    - "README.md#Running script DTEG.R"

  expected_tutorial_signals:
    - "Rscript --vanilla DTEG.R"
    - "Ribo-seq count matrix"
    - "RNA-seq count matrix"
    - "Sample information file"
    - "Condition"
    - "SeqType"
    - "Batch"
```

---

## Workflow DAG gold standard

```yaml
workflow_dag_gold:
  nodes:
    - id: prepare_ribo_counts
      type: load_data
      expected_input:
        name: ribo_counts
        matrix_state: raw_counts
        orientation: genes_by_samples

    - id: prepare_rna_counts
      type: load_data
      expected_input:
        name: rna_counts
        matrix_state: raw_counts
        orientation: genes_by_samples

    - id: prepare_sample_info
      type: load_metadata
      expected_columns:
        - SampleID
        - Condition
        - SeqType
        - Batch

    - id: run_dteg_r
      type: cli_execution
      expected_command:
        - "Rscript"
        - "--vanilla"
        - "DTEG.R"
      expected_arguments:
        - ribo_count_matrix
        - rna_count_matrix
        - sample_info_file
        - batch_effect_covariate_flag
        - save_rdata_flag
        - verbose_flag

    - id: classify_differential_translation
      type: statistical_analysis
      expected_outputs:
        - DTEG_results
        - DTG_classification
        - optional_RData

  edges:
    - prepare_ribo_counts -> run_dteg_r
    - prepare_rna_counts -> run_dteg_r
    - prepare_sample_info -> run_dteg_r
    - run_dteg_r -> classify_differential_translation
```

---

## IO contract gold standard

```yaml
io_contract_gold:
  primary_inputs:
    ribo_count_matrix:
      format: tabular_count_matrix
      matrix_state: raw_counts
      normalized_or_batch_corrected_allowed: false
      orientation: genes_by_samples
      first_column: Gene ID

    rna_count_matrix:
      format: tabular_count_matrix
      matrix_state: raw_counts
      normalized_or_batch_corrected_allowed: false
      orientation: genes_by_samples
      first_column: Gene ID

    sample_info_file:
      format: tabular_metadata
      required_columns:
        - SampleID
        - Condition
        - SeqType
        - Batch
      constraints:
        - same_sample_order_as_count_matrices
        - SeqType contains RIBO and RNA

  cli_arguments:
    arg1: ribo_count_matrix
    arg2: rna_count_matrix
    arg3: sample_info_file
    arg4: batch_effect_covariate_flag_yes_1_no_0
    arg5: save_RData_flag_default_1
    arg6: verbose_flag_default_0

  output:
    dteg_result_table:
      required: true
    rdata:
      required: optional
```

---

## Bio contract gold standard

```yaml
bio_contract_gold:
  modality:
    - Ribo-seq
    - RNA-seq
  task: translational_efficiency_and_differential_translation
  matrix_state:
    raw_counts_required: true
    normalized_input_disallowed: true
    batch_corrected_input_disallowed: true
  experimental_design:
    condition_required: true
    sequencing_type_required: true
    batch_optional_or_flagged: true
  gene_id_type:
    value: not_confirmed
```

---

## Adapter behavior gold standard

```yaml
adapter_behavior_gold:
  expected_adapter_type: cli
  expected_initial_status: candidate

  reason: Rscript CLI is clear, but real execution requires dependency review and validated small input files

  demo_run:
    allowed: true
    expected_behavior: run_only_if_small_synthetic_inputs_are_provided

  non_demo_run:
    expected_behavior: blocked_until_reviewed

  must_not:
    - run_without_validating_raw_counts
    - run_if_sample_info_missing_required_columns
    - auto_install_DESeq2_or_apeglm
```

---

## Evidence expectations

```yaml
evidence_expectations:
  high_priority_sources:
    - repo_readme
    - DTEG.R_script
    - paper_protocol

  required_claims_with_evidence:
    - raw Ribo-seq count matrix required
    - raw RNA-seq count matrix required
    - normalized or batch-corrected input should not be used
    - sample info required columns
    - Rscript CLI positional arguments
    - apeglm dependency note
```

---

## Quantitative metrics for this case

```yaml
metrics:
  dependency:
    cli_entrypoint_accuracy: binary
    r_dependency_recall: target >= 0.60
    bioconductor_dependency_detection: binary

  workflow:
    node_recall: target >= 0.80
    edge_recall: target >= 0.70
    cli_argument_order_accuracy: target >= 0.90

  io_bio_contract:
    raw_counts_requirement_accuracy: binary
    normalized_disallowed_accuracy: binary
    sample_metadata_schema_accuracy: target >= 0.90
    matrix_orientation_accuracy: binary

  adapter_safety:
    cli_adapter_type_accuracy: binary
    candidate_status_correctness: binary
    validation_before_execution_correctness: binary
```

---

## Expected failure modes

```text
1. Tool may treat RNA-seq and Ribo-seq matrices as one generic count matrix.
2. Tool may miss the rule that inputs must not be normalized or batch corrected.
3. Tool may miss sample information column names and case sensitivity.
4. Tool may parse only four CLI args because the example shows four visible args, despite documentation listing six arguments.
5. Tool may classify this as an R package API instead of Rscript CLI.
```
