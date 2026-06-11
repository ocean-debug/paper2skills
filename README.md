# Paper2Skill

Paper2Skill is an installable Codex standard skill that builds child skills from
algorithm papers, official source repositories, and official tutorials or
examples. The generated child skill is meant for Codex or another agent to use
for planning, preflight, execution, and output validation of a paper-backed
algorithm workflow.

This repository is intentionally lean. The product artifact is the skill bundle
under `.agents/skills/paper2skill/`; it is not a top-level Python package, MCP
server, or plugin package.

## Skill Bundle

```text
.agents/skills/paper2skill/
  SKILL.md
  manifest.yaml
  references/
  scripts/paper2skill.py
  assets/paper2skill_runtime/
  agents/openai.yaml
```

Core behavior lives in `SKILL.md`, `manifest.yaml`, and `references/`.
`agents/openai.yaml` is only UI metadata. The bundled Python runtime lives in
`assets/paper2skill_runtime/` and is invoked through `scripts/paper2skill.py`.

## Install

Copy the full skill folder into a Codex skills directory as `paper2skill/`:

```bash
cp -R .agents/skills/paper2skill ~/.codex/skills/paper2skill
```

Then run the bundled entrypoint from the installed skill directory:

```bash
cd ~/.codex/skills/paper2skill
python scripts/paper2skill.py --help
```

The wrapper does not install packages automatically. If bundled runtime
dependencies such as `Jinja2`, `PyYAML`, or `packaging` are missing, it prints an
install plan and exits so the user can explicitly approve environment changes.

## Workflow

The skill follows this fixed seven-step workflow:

1. Plan inputs and policies
2. Inspect evidence sources
3. Build child skill
4. Run build-time validation
5. Repair iteratively
6. Validate child skill package
7. Optionally run independent benchmark

## Build A Child Skill

Use `plan` to inspect inputs without generating a child skill:

```bash
python scripts/paper2skill.py plan \
  --paper path/to/paper.md \
  --repo path/to/official-repo \
  --tutorial path/to/official-tutorial.py \
  --out paper2skill_plan
```

Use `build` to generate a child skill:

```bash
python scripts/paper2skill.py build \
  --paper path/to/paper.md \
  --repo path/to/official-repo \
  --tutorial path/to/official-tutorial.py \
  --skill-name algorithm-skill \
  --out ../algorithm-skill \
  --validation-depth dry_run
```

Non-example builds must provide paper evidence, an official source repository,
and official tutorial or example evidence. Use `--example toy_python` or
`--example toy_r` only for bundled smoke fixtures.

## Build-Time Validation

`--validation-depth` is a build-time self-check depth, not benchmark scoring.
All build reports write `build_validation/build_validation.json` with:

```yaml
validation_type: build_time_self_check
diagnostic_only: true
```

The report must not include `benchmark_score`.

Supported build-time validation modes:

- `dry_run`: checks package structure, schema, policy safety, preflight, install
  plan, and execution plan. It does not run the real algorithm.
- `data_smoke`: requires an explicit reviewed validation manifest and runs the
  child skill on reviewed minimal or official-minimal data.
- `live_execute`: requires an explicit reviewed official example manifest and
  records environment, inputs, commands, outputs, and failure reasons.

Reviewed execution modes require `--validation-manifest` and reviewed adapter
evidence. Paper2Skill does not fabricate approvals or bypass review gates during
repair.

## Validate A Child Skill

```bash
python scripts/paper2skill.py validate --skill ../algorithm-skill
```

Generated child skills keep the agent-facing interface in:

```text
SKILL.md
scripts/preflight.py
scripts/plan.py
scripts/run.py
scripts/validate_outputs.py
references/
assets/
```

## Benchmark Separately

Benchmark evaluation is independent from build-time validation and requires a
gold-standard case. It is invoked through a separate command:

```bash
python scripts/paper2skill.py benchmark run \
  --case path/to/gold_case.yaml \
  --level L1
```

Benchmark levels are L0 through L4:

- `L0`: package structure, required files, policy safety, and path hygiene.
- `L1`: evidence bundle and contracts aligned with gold standard.
- `L2`: official minimal/demo data execution.
- `L3`: gold new-data adaptation and output contract validation.
- `L4`: agent use of the generated child skill for an end-to-end task.

Benchmark scores are never produced by `build --validation-depth`.

## Safety Policy

Paper2Skill does not automatically install dependencies, execute unreviewed
repository scripts, download large datasets, or run unreviewed adapters. Missing
dependencies are reported as preflight/install plans for explicit user approval.

Command adapters must be reviewed before execution. Build-time repair can
regenerate package files or improve generated context, but it must not invent
human approval, alter expected outputs to hide failures, or bypass data review.

## Repository Scope

When committing this project as a standard skill repository, include the full
`.agents/skills/paper2skill/` tree plus repository metadata such as this
`README.md` and `.gitignore`. Old top-level package, benchmark, and test harness
files are intentionally not part of the installable skill surface.
