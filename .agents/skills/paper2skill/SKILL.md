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

## Seven-Step Workflow

1. Plan inputs and policies
2. Inspect evidence sources
3. Build child skill
4. Run build-time validation
5. Repair iteratively
6. Validate child skill package
7. Optionally run independent benchmark

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
as `dry_run_only`; only adapters that pass `data_smoke` or `live_execute`
output validation may become `verified`. If bundled runtime dependencies are
missing, `scripts/paper2skill.py` prints an install plan and exits.
