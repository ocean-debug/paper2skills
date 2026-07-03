# Child Skill Standard

Generated child skills are lightweight agent skills, not Python packages.

## Required Layout

```text
method-name/
  SKILL.md
  references/
    task-types.md
    input-output-contracts.md
    limitations-and-refusal.md
    validation.md
    troubleshooting.md
    evidence.md
    environment.md
```

## SKILL.md

`SKILL.md` should include:

- when to use the skill
- when not to use it
- how to select `task_type`
- the minimum workflow
- when to read each reference file
- a reminder to refuse unsupported inputs

Keep it concise. Put details in `references/`.

## References

- `task-types.md`: capabilities as task types, including routing cues.
- `input-output-contracts.md`: accepted inputs, required metadata, parameters,
  static parameter constraints, outputs, and checks.
- `limitations-and-refusal.md`: unsupported cases and structured refusal
  templates.
- `validation.md`: technical output validation, environment install boundary,
  tutorial replay plan, and verification status.
- `troubleshooting.md`: common install, API, data, memory, GPU, and tutorial
  replay issues.
- `evidence.md`: concise evidence index, source parsing coverage, and evidence
  precedence, never long excerpts.
- `environment.md`: backend, dependency/import/GPU hints, and installation
  policy, including the plan-only install boundary.

## Verification Labels

Use conservative labels:

- `source_grounded`: supported by official source/tutorial/doc/paper evidence.
- `execution_verified`: supported by successful validated execution evidence.
- `unsupported`: outside available evidence or backend support.

Do not use `execution_verified` without validated execution evidence.
