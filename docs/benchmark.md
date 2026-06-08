# Benchmark-Driven Development

## Goal

The benchmark suite evaluates whether Paper2Skill can recover an auditable
Codex skill draft from an algorithm paper, official repository, and tutorial.
It does not evaluate the scientific performance of the underlying algorithms.

The real benchmark cases stress evidence collection, dependency mining,
tutorial selection, workflow DAG inference, IO/Bio contract recovery, and
adapter safety behavior.

## Case Structure

Real benchmark data lives under `benchmarks/real`:

```text
benchmarks/real/
  case_01_concord/
    case.md
    gold/
      source_collection.yaml
      dependency_contract.yaml
      tutorial_selection.yaml
      workflow_dag.yaml
      io_contract.yaml
      bio_contract.yaml
      adapter_behavior.yaml
      evidence_expectations.yaml
      metrics.yaml
```

`case.md` preserves the source case description. Files under `gold/` are test
data and expected contracts only. They must not be imported into core inference
logic, and core code must not contain case IDs, tool names, or repository URL
special cases.

## Gold Standard Format

Gold files are plain YAML:

- `source_collection.yaml`: expected paper, repository, commit, and tutorial evidence.
- `dependency_contract.yaml`: expected languages, required dependencies, optional dependencies, and system or CLI requirements.
- `tutorial_selection.yaml`: tutorial pages, files, titles, or code signals that should be selected.
- `workflow_dag.yaml`: expected workflow node types, states, calls, objects, and edges.
- `io_contract.yaml`: expected input formats, metadata keys, CLI arguments, and outputs.
- `bio_contract.yaml`: expected modality, matrix state, metadata semantics, and biological boundaries.
- `adapter_behavior.yaml`: expected adapter type, initial status, blocking behavior, and safety constraints.
- `evidence_expectations.yaml`: high-priority evidence sources and claims that need evidence.
- `metrics.yaml`: case-specific target thresholds from the case design.

## Evaluation Metrics

Evaluation is offline and compares generated outputs to gold YAML. Missing
generated files produce failing evaluator results with warnings rather than
Python tracebacks.

Supported metric groups:

- Source collection: `commit_sha_present`, `repo_index_contains`, `tutorial_candidate_recall`, `path_leakage_rate`.
- Dependency mining: `dependency_precision`, `dependency_recall`, `required_dependency_recall`, `optional_dependency_recall`, `language_detection_accuracy`.
- Tutorial and workflow: `tutorial_selection_recall`, `workflow_node_recall`, `workflow_edge_recall`, `step_type_accuracy`, `object_state_accuracy`.
- IO/Bio contract: `input_format_accuracy`, `matrix_state_accuracy`, `metadata_key_accuracy`, `modality_accuracy`, `output_contract_accuracy`, `not_confirmed_correctness`.
- Adapter safety: `adapter_type_accuracy`, `adapter_status_accuracy`, `non_demo_block_correctness`, `install_policy_compliance`, `execution_claim_safety`.

## Scoring

The case score uses the 100-point weighting from the benchmark overview:

```text
Source collection:          10
Dependency mining:          15
Tutorial/workflow DAG:      20
IO/Bio contract:            25
Evidence graph correctness: 10
Adapter/safety behavior:    15
Generated skill validation: 5
```

Interpretation:

- `>= 85`: strong
- `70-84`: usable with review
- `50-69`: partial
- `< 50`: fail

`not_confirmed` can be a correct result when evidence is absent. A benchmark
score should be read as evidence recovery and safety quality, not as proof that
the generated skill can run a real user dataset.

## Running Evaluation

Evaluate one generated skill:

```bash
python -m paper2skill.evaluation.evaluate_case \
  --case benchmarks/real/case_01_concord \
  --generated generated/case_01_concord/skill/references \
  --out generated/case_01_concord/evaluation.json
```

Summarize multiple results:

```bash
python -m paper2skill.evaluation.summarize_benchmark \
  --results generated/*/evaluation.json \
  --out generated/benchmark_summary.md
```

Build and evaluate all real cases in one pass:

```bash
python -m paper2skill.evaluation.run_real_benchmark \
  --cases benchmarks/real \
  --out-root generated/real \
  --strict-evidence
```

The evaluator does not clone repositories, download datasets, execute notebooks,
run unknown install scripts, or install dependencies.
The real benchmark runner does clone and index official repositories, but it
still leaves tutorials unexecuted and never installs dependencies.

## Adding A Case

1. Create `benchmarks/real/<case_id>/case.md`.
2. Add all required YAML files under `benchmarks/real/<case_id>/gold/`.
3. Prefer official tutorials, official docs, repository README, dependency files, and API source as gold evidence.
4. Keep paper background claims lower priority than tutorial/API evidence for IO contracts.
5. Run the gold loading tests before using the case for regression work.
6. Add or adjust generic inference rules only when failures reveal a reusable pattern.

## No Hard-Coding

Benchmark failures should lead to general Paper2Skill improvements, such as:

- broader `pyproject.toml`, `setup.py`, `requirements.txt`, `DESCRIPTION`, or `NAMESPACE` dependency mining;
- Rscript CLI detection;
- AnnData, Seurat, count matrix, or 10x input inference;
- condition, cell type, batch, perturbation, and sample metadata inference;
- adapter candidate, blocked, reviewed, ready, and verified safety policy.

Do not add checks like `case_id == "case_03_gears"`, `tool_name == "GEARS"`,
or repository URL substring rules. Those make the benchmark pass without
improving the product.

## Mini vs Real Benchmarks

Mini benchmarks under `tests/benchmarks` are small synthetic fixtures used by
CI to exercise generation behavior quickly. Real benchmarks under
`benchmarks/real` are gold standards for real-world tools. They are intended
for benchmark-driven development and offline evaluation, not for automatically
cloning or executing large upstream projects in CI.
