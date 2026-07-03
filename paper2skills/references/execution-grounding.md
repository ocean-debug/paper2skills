# Execution Grounding

Execution grounding is optional and explicit.

By default, Papert2Skills creates a `source_grounded` child skill. That means
claims are based on official sources, tutorials, documentation, source code, or
papers, but no tutorial execution has been verified.

When execution grounding is enabled, a task type can be upgraded to
`execution_verified` only if a successful execution trace exists for that same
`task_type`.

Use `execution_grounded: true` only with explicit `execution_traces` entries.
The flag records or validates supplied execution evidence; it does not silently
install dependencies or reproduce tutorials by itself.

Execution grounding must record:

- `task_type`
- `status`
- `trace_ref`
- command or notebook path summary
- environment summary
- input data source
- produced outputs
- validation checks
- errors and repairs, if any

`execution_trace_validation.yaml` checks these fields before publish. A trace
with a successful status but missing provenance or validation fields must not
upgrade a `task_type` to `execution_verified`.

Full logs stay in the build run directory. The public child skill receives only
concise provenance and validation summaries.

Never install dependencies, execute tutorials, patch upstream source, or modify
an environment without explicit user approval.
