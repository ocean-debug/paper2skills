# Design Principles

paper2skills builds one lightweight child skill per scientific algorithm
package. Its job is to turn official package evidence into operational guidance
that an agent can use without guessing.

## Core Rules

- Start with Discovery to avoid duplicating existing Codex child skills.
- Ground claims in official source repositories, tutorials, documentation,
  papers, and optional execution traces.
- Partition package capabilities into `task_type` entries.
- Mine environment, tutorial, API, interface, and parameter hints statically;
  do not treat them as execution verification.
- Keep all `task_type` entries inside one child skill for the package.
- Put routing guidance in `SKILL.md` and `references/task-types.md`.
- Treat refusal rules and validation rules as first-class skill content.

## Non-Goals

paper2skills must not generate:

- one child skill per tutorial
- one child skill per capability
- hidden package-specific fallback logic in the core builder
- verified execution claims without execution evidence
- heavy default runtime packages inside child skills

## Public Child Skill Goal

The generated child skill should be small enough for an agent to read quickly,
but precise enough to answer:

- which `task_type` should be used
- which inputs are required
- which outputs should exist
- how outputs can be validated
- which requests must be refused
- which evidence supports the boundary
