# Paper2Skill Workflow

Paper2Skill always follows this seven-step workflow.

1. Plan inputs and policies
   - Confirm paper, official repository, official tutorial or example, desired skill name, output directory, execution policy, and validation depth.
   - Prefer explicit local paths or reviewed official URLs.

2. Inspect evidence sources
   - Run `plan` to collect and inspect paper, repository, tutorial, dependency, workflow, IO, Bio, adapter, and environment evidence.
   - Do not execute unknown notebooks or unreviewed install scripts while collecting evidence.

3. Build child skill
   - Run `build` to create a child skill directory with `SKILL.md`, `scripts/`, `references/`, `assets/`, and optional `agents/openai.yaml`.
   - The child skill must be usable by Codex or another agent without relying on hidden conversation context.

4. Run build-time validation
   - Use `--validation-depth dry_run`, `data_smoke`, or `live_execute`.
   - Build-time validation is diagnostic self-check, not benchmark scoring.

5. Repair iteratively
   - If validation fails, collect failures and regenerate or adjust context/templates.
   - Keep repair attempts bounded and record repair actions in `build_validation/build_validation.json`.

6. Validate child skill package
   - Run `validate --skill <child-skill-dir>`.
   - Validate required files, contracts, adapter review, environment policy, and safety boundaries.

7. Optionally run independent benchmark
   - Use `benchmark run --case <case.yaml> --level L0-L4`.
   - Benchmark requires a gold-standard case and is independent from build-time validation.

## Child Skill Output

The child skill should include:

- `SKILL.md`
- `scripts/preflight.py`
- `scripts/plan.py`
- `scripts/run.py`
- `scripts/validate_outputs.py`
- `references/*`
- `assets/*`
- optional `agents/openai.yaml`
