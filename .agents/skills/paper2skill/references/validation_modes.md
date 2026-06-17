# Build-Time Validation Modes

Build-time validation is used during generation to find and repair child skill
problems. It is not benchmark scoring.

## dry_run

Use `dry_run` for fast structural and safety self-checks.

It checks:

- child skill package structure
- schema and contract presence
- policy safety
- preflight plan presence
- install plan presence
- execution plan presence

It must not execute a real algorithm reproduction.

## data_smoke

Use `data_smoke` only when a small official or minimal data manifest and output
contract are available.

It runs:

- preflight
- plan
- selected adapter smoke path
- output validation

It must block when the runner, validation manifest, selected example, or
expected outputs are missing. The validation manifest is required and must use
`data_kind: minimal` or `data_kind: official_minimal`. The selected example
adapter can become `verified` only after a run trace is recorded and output
validation passes. Demo-mode summary runs are diagnostic only and cannot promote
an adapter.

## live_execute

Use `live_execute` only for official example data with a validation manifest
and output contract.

It runs the complete child skill flow and records:

- environment evidence
- input manifest
- command records
- outputs
- validation result
- failure reason if execution fails

It must block unless the validation manifest uses
`data_kind: official_example` and declares expected outputs.

## Validation Manifest Contract

`data_smoke` and `live_execute` require `--validation-manifest`. This file is an
execution gate and output contract for build-time self-check execution, not a
benchmark case.

Required fields:

```yaml
validation_type: build_time_self_check
data_kind: minimal
manifest_path: path/to/reviewed_official_minimal_manifest.yaml
expected_outputs:
  - results/summary.json
expected_output_values:
  results/summary.json:
    rows: 3
official_example:
  source: official tutorial or package test data
```

Rules:

- `data_smoke` accepts only `data_kind: minimal` or `official_minimal`.
- `live_execute` accepts only `data_kind: official_example`.
- `manifest_path` points to the child skill input manifest and is resolved
  relative to the validation manifest, then the child skill root.
- `expected_outputs` are paths relative to the result directory.
- `expected_output_values` maps JSON output paths to exact field values.
- Missing manifests or output contracts return `blocked_verification_required`.

## Report Contract

`build_validation/build_validation.json` must include:

- `validation_type: build_time_self_check`
- `diagnostic_only: true`
- `validation_depth`
- package, policy, preflight, install, and execution-plan status
- execution gate status for `data_smoke` and `live_execute`
- execution records when execution is allowed
- run trace or run-trace-compatible records when execution is allowed
- repair actions when regeneration is attempted

It must not include `benchmark_score`.

## Repair Boundary

Repair is finite and deterministic. Paper2Skill may regenerate a package when
required files or install artifacts are missing. It must not fabricate expected
outputs or alter output contracts to make a run pass.
