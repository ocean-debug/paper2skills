# Safety Policy

Paper2Skill generates executable child skills, so execution boundaries must be
explicit.

## Installation

- Do not install packages automatically.
- Missing dependencies must produce preflight evidence and an install plan.
- Any installation must require explicit user approval.
- Non-interactive `ask` policies behave as `never`.
- `paper2skill reproduce --install-policy plan` may run dry-run dependency
  resolution only. `--install-policy yes` is required before modifying the
  active environment, and every before/after package snapshot must be written to
  `agentic_run/env_delta.json`.
- Python 3.12 plus legacy dependency pins must enter compatibility repair
  instead of silently accepting an L1-only result.

## Adapter Execution

- Adapter status has two values: `dry_run_only` and `verified`.
- Generated adapters default to `dry_run_only`.
- `dry_run_only` adapters may preflight, plan, and dry-run only.
- Only `verified` adapters may perform real execution.
- Child skills must also check
  `references/contracts/algorithm_contract.yaml:applicability.real_execution_allowed`
  and `recommended_execution.can_execute_real_data`; a syntactically valid
  manifest is not enough to run real data.
- Static API, CLI, notebook, script, workflow, or container inference can only
  create `dry_run_only` adapters.
- `paper2skill reproduce --confirm-run yes` is the only Paper2Skill command
  mode that may execute generated adapter smoke code automatically.
- A selected example can become `verified` only after a non-demo run trace
  exists, `workflow/adapter_report.json` records `status=pass`, and
  `validate_outputs.py` records `status=pass`.
- Demo summaries and dry-runs never promote adapters.
- `assets/demo_input_manifest.yaml` is smoke-only; default execution entrypoints
  must use `assets/official_attempt_manifest.yaml` or an explicit reviewed
  manifest.
- Verification is per tutorial/example. One passing tutorial must not imply that
  another tutorial or user-data path is executable.

## Promotion

- Promotion consumes `run_trace.json`, `tutorial_catalog.yaml`, adapter review,
  and contracts.
- Promotion must refuse traces without passing output validation.
- Promotion must refuse traces from demo mode, dry-runs, missing adapter
  reports, failed adapter execution, or examples missing from
  `tutorial_catalog.yaml`.
- Promotion may update the selected example, adapter contract, adapter review,
  and maturity level; it must not rewrite unrelated evidence to hide failures.

## Data

- Do not download large datasets by default.
- Use official small examples, package test data, or minimal fixtures for
  execution validation.
- Requests outside `algorithm_contract.applicability.supported_task`, domain,
  modality, or allowed execution modes must be refused before adapter
  execution.
- User-data manifests should declare `inputs.analysis.task`,
  `inputs.analysis.domain`, and `inputs.analysis.modality` when these are known;
  preflight must refuse declared values that conflict with applicability.
- Documentation pages, install pages, wildcard paths, and README URLs must not
  be classified as data sources.
- IO and bio contract mismatches must block preflight with structured
  `refusal_reasons`; they must not be downgraded to warnings.
- Refusal reasons must identify the manifest path that needs correction, such
  as `inputs.primary_data.matrix_state` or `inputs.metadata`.
- Keep benchmark cases gold-standard driven and independent from build-time validation.

## Repository Scripts

- Do not run arbitrary repository setup, install, notebook, shell, or workflow scripts unless they are selected as the validation example and covered by the output contract.
- Notebook execution policy must be recorded in the child skill references.
- Agentic repair may change only generated child skill files, adapters, repair
  configs, or contracts. Upstream repository source files must remain unchanged
  unless the user explicitly asks for an upstream patch.
