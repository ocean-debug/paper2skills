# Review and Publish

Review the rendered child as an independent Codex user, not as its builder.

## Behavioral Rubric

For every task, verify that a fresh agent can:

1. recognize a matching request;
2. avoid selecting the task for a nearby but unsupported request;
3. ask for missing task-defining metadata;
4. follow a grounded API sequence;
5. refuse invalid inputs with an actionable reason;
6. check output structure and numerical sanity;
7. distinguish technical success from biological interpretation;
8. reuse the workflow on a compatible new dataset.

## Hard Blocks

Block publication for:

- an API without source/tutorial evidence;
- a task without a selection and refusal case;
- missing input, output, validation, boundary, reuse, or evidence sections;
- unresolved routing ambiguity;
- an `execution_verified` label without successful task-specific run evidence;
- machine-specific paths, credentials, private identifiers, or copied long
  source excerpts;
- multiple user-facing skills for one package;
- builder artifacts inside the public child skill.

## Bounded Revisions

Revise `skill_spec.yaml`, not arbitrary project files. Patch proposals may
change only shared environment, package boundaries, task contracts, routing,
and shared troubleshooting. Every revision must preserve or improve evidence
traceability.

## Publish Result

A successful publish contains only:

```text
published/<package>/
  SKILL.md
  agents/openai.yaml
  references/task-routing.md
  references/task-*.md
  references/package-boundaries.md
  references/environment.md
  references/evidence.md
  references/troubleshooting.md
  scripts/                         # optional and validated
  assets/                          # optional
```

Installation remains a separate user-controlled step.

