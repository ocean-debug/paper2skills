---
name: paper2skill
description: >-
  Generate a Codex/Agent-ready child skill from an algorithm paper, official
  source repository, and official tutorial or example. Use when the user wants
  to build, validate, repair, or benchmark an installable child skill for an
  algorithm workflow.
---

# Paper2Skill Router

Paper2Skill is a builder skill. It creates a separate child skill that another
Codex or agent can use to plan, preflight, run, and validate a paper-backed
algorithm workflow.

## Load Protocol

1. Read `manifest.yaml`.
2. Read every file listed under `always_load`.
3. Use `references/validation_modes.md` only when choosing or explaining
   `--validation-depth`.
4. Use `references/benchmark_levels.md` only when the user asks for independent
   benchmark evaluation.

Do not rely on hidden conversation context. The generated child skill must carry
its own `SKILL.md`, `scripts/`, `references/`, and `assets/`.

## Compiler Workflow

Paper2Skill compiles paper methods into agent-callable child skills through a
single plan-run-plan loop:

```text
thin plan -> run -> promotion plan -> child skill
```

`thin plan` catalogs official tutorials/examples first, then uses paper and
repository evidence to support contracts, adapter candidates, and applicability
boundaries. It does not execute code.

`run` executes one approved minimal or official example with a reviewed manifest
and records a run trace.

`promotion plan` decides whether the trace can promote an adapter. It must
refuse demo summaries, dry-runs, missing adapter reports, failed adapter
execution, or failed output validation.

`child skill` is the compact installable skill with preflight, plan, run,
output validation, contracts, tutorial catalog, evidence summary, and maturity.

Each phase must write machine-readable artifacts. Later phases consume those
artifacts instead of hidden chat context.

## Command Entry

From this skill directory, run the bundled entrypoint:

```bash
python scripts/paper2skill.py --help
```

Use `plan` to inspect inputs without generating a skill:

```bash
python scripts/paper2skill.py plan \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/tutorial.py \
  --out paper2skill_plan
```

Use `triage-plan` to write the thin plan artifacts used by the generalized
compiler:

```bash
python scripts/paper2skill.py triage-plan \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/tutorial.py \
  --out paper2skill_triage_plan
```

Use `build` to generate a child skill:

```bash
python scripts/paper2skill.py build \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/tutorial.py \
  --skill-name algorithm-skill \
  --out ../algorithm-skill \
  --validation-depth dry_run
```

Use `reproduce` when the user explicitly asks for reproduction, validation, or
a usable verified skill. It first builds the L1 child skill, then runs the
fixed agentic loop `catalog -> build L1 -> env_probe -> data_probe ->
adapter_materialize -> smoke_run -> error_classify -> repair -> rerun ->
promote -> emit skill`:

```bash
python scripts/paper2skill.py reproduce \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/default_validation_tutorial.ipynb \
  --skill-name algorithm-skill \
  --out ../algorithm-skill \
  --confirm-run yes \
  --install-policy never \
  --repair-budget 2 \
  --data-cache-dir path/to/data_cache
```

For `reproduce`, explicit `--tutorial` chooses the default validation target
but must not truncate `references/tutorial_catalog.yaml`; repository tutorial
indexes and candidates remain cataloged. The command writes
`agentic_run/repair_log.jsonl`, `agentic_run/env_delta.json`,
`agentic_run/run_trace.json`, and `agentic_run/promotion_report.json`.

Use build-time execution only with an explicit validation manifest and output
contract:

```bash
python scripts/paper2skill.py build \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/tutorial.py \
  --skill-name algorithm-skill \
  --out ../algorithm-skill \
  --validation-depth data_smoke \
  --validation-manifest path/to/build_validation_manifest.yaml
```

Use `validate` after build:

```bash
python scripts/paper2skill.py validate --skill ../algorithm-skill
```

Use `run-example` only after explicit execution approval. It writes a run trace
for one selected example:

```bash
python scripts/paper2skill.py run-example \
  --skill ../algorithm-skill \
  --manifest path/to/reviewed_official_example_manifest.yaml \
  --example-id default_demo \
  --out paper2skill_run \
  --confirm-run yes
```

Use `ingest-run` when an approved run already exists:

```bash
python scripts/paper2skill.py ingest-run \
  --run-dir path/to/result \
  --skill ../algorithm-skill \
  --out paper2skill_run_trace
```

Use `promote` to convert a passing non-demo run trace into verified adapter
evidence:

```bash
python scripts/paper2skill.py promote \
  --skill ../algorithm-skill \
  --run-trace paper2skill_run_trace/run_trace.json
```

## Validation Boundary

Build-time validation is a generation self-check and repair signal. It writes
`build_validation/build_validation.json`, sets
`validation_type=build_time_self_check`, sets `diagnostic_only=true`, and must
not produce benchmark scores.

Independent benchmark evaluation is separate and requires a gold-standard case:

```bash
python scripts/paper2skill.py benchmark run \
  --case path/to/gold_case.yaml \
  --level L1
```

## Safety Boundary

Never install dependencies, execute unknown repository scripts, download large
datasets, or run non-verified adapters automatically. Generated adapters start
as `dry_run_only`; only a selected example with a passing adapter report,
passing run trace, and passing output validation may become `verified`. Static
API or CLI inference can only produce `dry_run_only` adapters. Demo summaries do
not promote adapters. If bundled runtime dependencies are missing,
`scripts/paper2skill.py` prints an install plan and exits.
