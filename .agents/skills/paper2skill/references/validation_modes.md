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

Use `data_smoke` only when a reviewed small official or minimal data manifest is
available.

It runs:

- preflight
- plan
- reviewed adapter smoke path
- output validation

It must block when the reviewed runner, validation manifest, adapter approval,
or expected outputs are missing. The validation manifest is required and must
use `data_kind: minimal` or `data_kind: official_minimal`.

## live_execute

Use `live_execute` only for reviewed official example data.

It runs the complete child skill flow and records:

- environment evidence
- input manifest
- command records
- outputs
- validation result
- failure reason if execution fails

It must block unless the validation manifest uses
`data_kind: official_example` and `official_example.reviewed: true`.

## Validation Manifest Contract

`data_smoke` and `live_execute` require `--validation-manifest`. This file is a
review gate and output contract for build-time self-check execution, not a
benchmark case.

Required fields:

```yaml
validation_type: build_time_self_check
data_kind: minimal
reviewed: true
manifest_path: assets/demo_input_manifest.yaml
expected_outputs:
  - results/summary.json
expected_output_values:
  results/summary.json:
    rows: 3
official_example:
  reviewed: false
```

Rules:

- `data_smoke` accepts only `data_kind: minimal` or `official_minimal`.
- `live_execute` accepts only `data_kind: official_example` and requires
  `official_example.reviewed: true`.
- `manifest_path` points to the child skill input manifest and is resolved
  relative to the validation manifest, then the child skill root.
- `expected_outputs` are paths relative to the result directory.
- `expected_output_values` maps JSON output paths to exact field values.
- Missing or unreviewed manifests return `blocked_review_required`.

## Report Contract

`build_validation/build_validation.json` must include:

- `validation_type: build_time_self_check`
- `diagnostic_only: true`
- `validation_depth`
- package, policy, preflight, install, and execution-plan status
- review gate status for `data_smoke` and `live_execute`
- execution records when execution is allowed
- repair actions when regeneration is attempted

It must not include `benchmark_score`.

## Repair Boundary

Repair is finite and deterministic. Paper2Skill may regenerate a package when
required files or install artifacts are missing. It must not invent review
approval, fabricate expected outputs, or alter output contracts to make a run
pass.
