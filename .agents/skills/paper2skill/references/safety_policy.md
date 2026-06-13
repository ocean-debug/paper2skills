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
- `data_smoke` and `live_execute` can mark one selected example as `verified`
  only after the adapter runs and `validate_outputs.py` passes.

## Data

- Do not download large datasets by default.
- Use official small examples, package test data, or minimal fixtures for
  execution validation.
- Keep benchmark cases gold-standard driven and independent from build-time validation.

## Repository Scripts

- Do not run arbitrary repository setup, install, notebook, shell, or workflow scripts unless they are selected as the validation example and covered by the output contract.
- Notebook execution policy must be recorded in the child skill references.
