# Benchmark-Driven Development

## Goal

The benchmark suite evaluates the full Paper2Skill lifecycle: package safety,
static evidence extraction, controlled example execution, new-data validation,
and agentic command following. The five real cases are benchmark data only; core
builder and evaluator logic must not special-case case IDs, tool names, or repo
URLs.

## Benchmark Pyramid

```text
L0. Skill package and safety validation
L1. Static evidence and contract extraction
L2. Official example execution
L3. New-data generalization and invalid-input rejection
L4. Agentic command following and safe refusal
```

Default scoring is 100 points:

```text
L0 skill package:              10
L1 static extraction:          30
L2 official example execution: 25
L3 new-data validation:        20
L4 agentic usage:              15
```

Scores are reported overall, by level, and by component. A strong L1 score must
not hide weak L2/L3/L4 behavior.

## Case Structure

Real benchmark cases live under `benchmarks/real/<case_id>`:

```text
case.md
gold/
  case_metadata.yaml
  source_collection.yaml
  dependency_contract.yaml
  tutorial_selection.yaml
  workflow_dag.yaml
  io_contract.yaml
  bio_contract.yaml
  adapter_behavior.yaml
  evidence_expectations.yaml
  metrics.yaml
  level0_skill_package.yaml
  level2_official_examples.yaml
  level3_new_data.yaml
  level4_agentic_tasks.yaml
data/
  official_examples/
  new_data/
```

`case.md` preserves the human-readable case description. `gold/*.yaml` files are
test data and expected behavior. They must not be imported into core inference
logic.

`case_metadata.yaml` stores case identity and `tutorial_urls` as a list. The
runner reads this file first and falls back to the `case.md` basic-information
block only for backward compatibility.

## Multi-Tutorial And Workflow Support

Tutorial gold supports:

```text
single_tutorial
multi_tutorial_same_workflow
multi_tutorial_multi_workflow
multi_tutorial_pipeline_stages
```

Workflow gold supports:

```text
single_workflow
multi_workflow
pipeline_workflow
single_workflow_multiple_examples
```

Use `workflows[]` for multi-workflow cases and `workflows[].stages[]` for
pipeline-stage tools. This keeps scGen-style separate tasks and GEARS-style
data/model/inference stages distinct instead of forcing every tool into one
linear workflow.

## Level Behavior

L0 validates generated skill package structure and safety: required files,
adapter lifecycle, notebook execution policy, install policy, and local path
leakage.

L1 compares static generated references against gold YAML: source collection,
dependencies, tutorial/workflow, IO/Bio contracts, evidence, adapter behavior,
and execution safety plan. Environment repair plans are build-validation or
BioEnvRebuilder diagnostics, not L1 score items.

L2 evaluates official examples as real benchmark execution. The benchmark
default is `live_execute`, and a real L2 pass requires `live_execute_success` on
an official full example. `dry_run` and `data_smoke` remain useful build-time
validation or diagnostic modes, but they do not contribute L2 benchmark credit.
Missing dependencies produce an install approval request; the evaluator does not
silently install packages. `blocked_by_policy` is evaluated in L4 safety/refusal
contexts, not as L2 execution success. If a case lacks a live official example
gold entry, L2 reports `missing_live_official_example_gold`.

L3 evaluates valid new-data behavior and invalid-input rejection. Invalid inputs
must be blocked before execution and should mention the violated contract field.

L4 evaluates structured agent traces or deterministic mock-agent decisions. CI
does not call online LLMs. The evaluator checks expected action, reason text,
required contract references, and forbidden unsafe actions.

## Downloads And Execution

L2/L3 may explicitly download official example data, but downloads are opt-in:

```bash
--allow-download
--download-cache benchmarks/data_cache
--max-download-mb 500
```

Downloads are cached and can be size/checksum checked. Unit tests must remain
offline. Unknown notebooks and install scripts must not execute automatically.

Build-time validation uses explicit self-check depth:

```bash
python -m paper2skill.cli build \
  --paper-url ... \
  --repo ... \
  --validation-depth dry_run
```

These self-check depths are not benchmark scoring. Benchmark execution policy is
explicit and defaults to live official execution:

```bash
--l2-mode dry_run|data_smoke|live_execute
--allow-execution none|reviewed_only|all
```

Candidate, blocked, and demo-only adapters are not executable. Correct refusal
is assessed by L4 agentic safety tasks, while L2 remains focused on reviewed
official example execution.

Dependency installation is separate from downloads and execution:

```bash
--allow-install none
--allow-install ask
--install-env paper2skill-l2-case_id
```

`--allow-install ask` returns a structured install approval request with missing
packages, allowed installers, and the target environment. It does not install
into the shared environment.

BioEnvRebuilder is the preferred installer for real L2 live execution. It treats
official `environment.yml` files as upstream evidence, derives
`assets/env/paper2skill.environment.yml`, keeps lockfile scopes explicit, and
uses conda/bioconda for compiled Python, R/Bioconductor, CLI, and workflow
engine packages. `uv` is limited to the pip/PyPI segment. Repair attempts are
additive or route migrations only, default to three attempts, and only run for
known route-table or case-gold allowlisted packages.

## Commands

Validate gold:

```bash
python -m paper2skill.evaluation.validate_gold \
  --case benchmarks/real/case_01_concord
```

Evaluate one case:

```bash
python -m paper2skill.evaluation.evaluate_case \
  --case benchmarks/real/case_01_concord \
  --generated generated/real/case_01_concord/skill \
  --levels L0,L1,L2,L3,L4 \
  --out generated/real/case_01_concord/evaluation.json \
  --markdown-out generated/real/case_01_concord/evaluation.md
```

Run L2 with small declared example data:

```bash
python -m paper2skill.evaluation.evaluate_case \
  --case benchmarks/real/case_05_deltate \
  --generated generated/real/case_05_deltate/skill \
  --levels L2 \
  --l2-mode data_smoke \
  --allow-download \
  --out generated/real/case_05_deltate/l2_data_smoke.json
```

Request dependency installation approval for live execution:

```bash
python -m paper2skill.evaluation.evaluate_case \
  --case benchmarks/real/case_05_deltate \
  --generated generated/real/case_05_deltate/skill \
  --levels L2 \
  --l2-mode live_execute \
  --allow-download \
  --allow-install ask \
  --install-env paper2skill-l2-case_05_deltate \
  --out generated/real/case_05_deltate/l2_live_execute.json
```

Run reviewed live execution with BioEnvRebuilder:

```bash
python -m paper2skill.evaluation.run_real_benchmark \
  --cases benchmarks/real/case_05_deltate \
  --out-root generated/real_live_deltate \
  --levels L2 \
  --l2-mode live_execute \
  --allow-download \
  --allow-install approved \
  --env-rebuilder bio \
  --target-env-mode new \
  --repair-attempts 3 \
  --export-lock
```

Create an approved install plan from that evaluation:

```bash
python -m paper2skill.evaluation.execution.install_approved_plan \
  --evaluation generated/real/case_05_deltate/l2_live_execute.json \
  --install-env paper2skill-l2-case_05_deltate \
  --out generated/real/case_05_deltate/install_approved_plan.json
```

The command above is a dry run: it writes the exact conda-run commands but does
not install anything. To execute, both approval flags are required:

```bash
python -m paper2skill.evaluation.execution.install_approved_plan \
  --evaluation generated/real/case_05_deltate/l2_live_execute.json \
  --install-env paper2skill-l2-case_05_deltate \
  --out generated/real/case_05_deltate/install_approved_plan.executed.json \
  --execute \
  --yes
```

The install command refuses shared environments such as `base` and `skill` by
default. Use a case-specific isolated environment unless there is a reviewed
reason to override that guard.

Build and evaluate all real cases with benchmark L2 live execution:

```bash
python -m paper2skill.evaluation.run_real_benchmark \
  --cases benchmarks/real \
  --out-root generated/real \
  --strict-evidence \
  --levels L0,L1,L2,L3,L4 \
  --l2-mode live_execute \
  --allow-download
```

Summarize results:

```bash
python -m paper2skill.evaluation.summarize_benchmark \
  --results generated/real/*/evaluation.json \
  --out generated/real/benchmark_summary.md \
  --json-out generated/real/benchmark_summary.json
```

## Adding A Case

1. Add `case.md` and all required `gold/*.yaml` files.
2. Put multiple official tutorials in `case_metadata.yaml:tutorial_urls`.
3. Use `tutorial_selection.yaml` to declare selection mode, required tutorials,
   purposes, stages, and signals.
4. Use `workflow_dag.yaml` to declare single, multi, or pipeline workflows.
5. Keep L2 downloads explicit and small unless a full benchmark run opts in.
6. Add L3 valid and invalid manifests that exercise the IO/Bio contract.
7. Add L4 structured tasks that cover valid use, invalid data, wrong task, and
   unsafe commands.

## No Hard-Coding

Benchmark failures should drive generic improvements: Python/R API detection,
Rscript CLI detection, workflow-engine detection, dependency mining,
multi-tutorial handling, AnnData/Seurat/count matrix inference, metadata key
inference, adapter lifecycle validation, input validation, and safe refusal.

Do not add checks like `case_id == "case_03_gears"`, `tool_name == "GEARS"`, or
repository URL substring rules.

## Mini Vs Real Benchmarks

Mini benchmarks under `tests/benchmarks` are small offline fixtures for CI.
Real benchmarks under `benchmarks/real` are product-quality gold standards for
real tools. Full download/execution modes are opt-in and should not run in the
default unit-test path.
