# Paper2Skill

Paper2Skill is an installable Codex standard skill that compiles algorithm
papers, official source repositories, and official tutorials/examples into
agent-callable child skills. The goal is not just to run a demo: the generated
skill should know when it can be used, what inputs it requires, how to preflight,
how to run, where outputs land, how success is verified, when to refuse, and its
current maturity level.

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

The compiler follows one public plan-run-plan loop:

```text
thin plan -> run -> promotion plan -> child skill
```

`thin plan` is tutorial-first: it catalogs official tutorials/examples,
collects paper and repository evidence as support, infers initial contracts,
and selects a reviewed minimal execution candidate without running code.

`run` executes only one approved candidate with a reviewed manifest and records
environment, inputs, adapter report, produced files, logs, and output
validation.

`promotion plan` decides whether the run trace is strong enough to promote an
adapter. Demo summaries, dry-runs, missing adapter reports, and failed output
validation must refuse promotion.

`child skill` is the compact installable skill surface with preflight, planning,
execution, output validation, contracts, tutorial catalog, evidence summary, and
maturity metadata.

The main compiler artifacts are `tutorial_catalog.yaml`, `run_trace.json`,
`references/contracts/*.yaml`, `references/maturity.yaml`, and
`references/evidence_summary.md`.

`references/contracts/algorithm_contract.yaml` is the child skill's routing
contract. It records `applicability` (supported task, domain, modality,
allowed execution modes, real execution gate, and refusal rules) and
`recommended_execution` (default manifest, entrypoints, inferred API/command,
and verified-run requirements).

Generated manifests include `inputs.analysis.task`, `inputs.analysis.domain`,
and `inputs.analysis.modality` so preflight can reject requests that conflict
with the routing contract before any adapter execution.

## Build A Child Skill

Use `plan` to inspect inputs without generating a child skill:

```bash
python scripts/paper2skill.py plan \
  --paper path/to/paper.md \
  --repo path/to/official-repo \
  --tutorial path/to/official-tutorial.py \
  --out paper2skill_plan
```

Use `triage-plan` to write generalized compiler artifacts without generating a
child skill:

```bash
python scripts/paper2skill.py triage-plan \
  --paper path/to/paper.md \
  --repo path/to/official-repo \
  --tutorial path/to/official-tutorial.py \
  --out paper2skill_triage_plan
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

## Run Trace And Promotion

Generated adapters start as `dry_run_only`. Static API/CLI/notebook/script
inference cannot mark an adapter as verified.

After explicit approval, run one selected example and write a run trace:

```bash
python scripts/paper2skill.py run-example \
  --skill ../algorithm-skill \
  --manifest path/to/reviewed_official_example_manifest.yaml \
  --example-id default_demo \
  --out paper2skill_run \
  --confirm-run yes
```

If a reviewed run already exists, ingest it:

```bash
python scripts/paper2skill.py ingest-run \
  --run-dir path/to/result \
  --skill ../algorithm-skill \
  --out paper2skill_run_trace
```

Promote only from a passing non-demo run trace with a passing adapter report and
passing output validation:

```bash
python scripts/paper2skill.py promote \
  --skill ../algorithm-skill \
  --run-trace paper2skill_run_trace/run_trace.json
```

Verification is per tutorial/example. A child skill may contain multiple
examples, but each keeps its own runnable status and maturity evidence.

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

The compact contract surface is:

```text
references/tutorial_catalog.yaml
references/maturity.yaml
references/evidence_summary.md
references/contracts/algorithm_contract.yaml
references/contracts/adapter_contract.yaml
references/contracts/bio_contract.yaml
references/contracts/environment_contract.yaml
references/contracts/io_contract.yaml
assets/official_attempt_manifest.yaml
assets/input_manifest_template.yaml
```

`assets/demo_input_manifest.yaml` may be present for local smoke behavior, but it
is not part of the promotion path and must not be used as verified execution
evidence.

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
- `L2`: official minimal/example adapter execution with output validation.
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
