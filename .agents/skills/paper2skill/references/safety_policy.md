# Safety Policy

Paper2Skill generates executable child skills, so execution boundaries must be
explicit.

## Installation

- Do not install packages automatically.
- Missing dependencies must produce preflight evidence and an install plan.
- Any installation must require explicit user approval.
- Non-interactive `ask` policies behave as `never`.

## Adapter Execution

- Unknown adapters remain `candidate` or `blocked`.
- Only `ready`, `reviewed`, or `verified` adapters may execute.
- `reviewed` adapters require explicit human approval evidence.
- `live_execute` additionally requires an explicitly reviewed official example.

## Data

- Do not download large datasets by default.
- Use reviewed official examples or minimal fixtures for execution validation.
- Keep benchmark cases gold-standard driven and independent from build-time validation.

## Repository Scripts

- Do not run arbitrary repository setup, install, notebook, shell, or workflow scripts unless explicitly reviewed.
- Notebook execution policy must be recorded in the child skill references.
