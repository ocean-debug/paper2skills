# Safety Policy

Paper2Skill generates executable child skills, so execution boundaries must be
explicit.

## Installation

- Do not install packages automatically.
- Missing dependencies must produce preflight evidence and an install plan.
- Any installation must require explicit user approval.
- Non-interactive `ask` policies behave as `never`.

## Adapter Execution

- Adapter status has two values: `dry_run_only` and `verified`.
- Generated adapters default to `dry_run_only`.
- `dry_run_only` adapters may preflight, plan, and dry-run only.
- Only `verified` adapters may perform real execution.
- Static API, CLI, notebook, script, workflow, or container inference can only
  create `dry_run_only` adapters.
- A selected example can become `verified` only after a run trace exists and
  `validate_outputs.py` records `status=pass`.
- Verification is per tutorial/example. One passing tutorial must not imply that
  another tutorial or user-data path is executable.

## Promotion

- Promotion consumes `run_trace.json`, `tutorial_catalog.yaml`, adapter review,
  and contracts.
- Promotion must refuse traces without passing output validation.
- Promotion may update the selected example, adapter contract, adapter review,
  and maturity level; it must not rewrite unrelated evidence to hide failures.

## Data

- Do not download large datasets by default.
- Use official small examples, package test data, or minimal fixtures for
  execution validation.
- Documentation pages, install pages, wildcard paths, and README URLs must not
  be classified as data sources.
- Keep benchmark cases gold-standard driven and independent from build-time validation.

## Repository Scripts

- Do not run arbitrary repository setup, install, notebook, shell, or workflow scripts unless they are selected as the validation example and covered by the output contract.
- Notebook execution policy must be recorded in the child skill references.
