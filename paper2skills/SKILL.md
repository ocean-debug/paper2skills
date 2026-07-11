---
name: paper2skills
description: Compile one bioinformatics algorithm's official source repository and official tutorials or examples into one evidence-grounded Codex child skill with internal task_type routing, one Markdown contract per task, structured refusal, output validation, biological interpretation boundaries, and reuse guidance. Use when Codex must create or revise an agent-usable skill for a scientific Python package from repository and tutorial evidence; papers are optional supporting evidence, not the primary input.
---

# Paper2Skills

Build one child skill for one algorithm package. Keep all supported analysis
goals inside that child skill and render each accepted goal to a separate
`references/task-*.md` file.

## Required Inputs

Require an official repository URL or local checkout. Prefer at least one
official tutorial, example, demo, notebook, or repository usage guide. If no
tutorial exists, infer a workflow conservatively from source, official docs,
tests, and repository usage instructions and label every inferred step.

Treat papers as optional evidence for intent, assumptions, applicability, and
author-stated limitations. Never derive an executable API path from a paper
alone.

## Build Workflow

1. Copy [the build request template](assets/build-request.yaml) outside the
   installed skill and fill the package sources and run output directory.
2. Run `scripts/paper2skills.py init --request <request.yaml>`.
3. If the request contains only a repository URL, obtain the requested official
   revision under the run directory (prefer `sources/repository/`) and add that
   checkout to the run-local `request.yaml.source_paths`. If Git is unavailable,
   use an official archive or user-provided checkout and preserve its revision.
4. Obtain official tutorial/example content when only URLs were supplied and
   register local copies under `tutorial_paths`; do not treat an unread URL as
   inspected evidence.
5. Run `scripts/paper2skills.py ground --run <run-dir>` to build a compact
   evidence ledger and agent packet. This step performs static inspection only.
6. Read [the evidence policy](references/evidence-policy.md), the generated
   `source_report.yaml`, and `agent_packet.md`.
7. Identify analysis-goal task types. Do not split by tutorial, notebook,
   pipeline stage, plot, or parameter variant.
8. Fill the run-local `skill_spec.yaml` using
   [the SkillIR contract](references/skillir-contract.md). Give every important
   claim an evidence ID.
9. Run `render`, then read the rendered child as a fresh agent would.
10. Review it with [the review and publish rubric](references/review-and-publish.md).
   Edit the SkillIR directly or submit a bounded patch proposal with
   `apply-patch`.
11. Run `validate`. Resolve every blocker before `publish`.
12. Publish only to the run-local `published/` tree. Do not install or deploy
    without a separate user request.

See [the complete workflow](references/workflow.md) for commands, phase
artifacts, and stopping conditions.

## Evidence Order

Use evidence in this order:

1. official runnable tutorials and examples;
2. current source, public APIs, and official tests;
3. official documentation and repository usage instructions;
4. paper Methods and supplementary materials;
5. paper abstract.

When tutorial code conflicts with the requested source revision, follow the
source behavior and record the conflict.

## Fail Closed

Refuse to publish when any task lacks grounded APIs, inputs, refusal rules,
technical validation, biological interpretation boundaries, reuse guidance,
or evidence IDs. Do not mark a task `execution_verified` without a successful,
versioned execution record for that task.

Never silently invent metadata semantics, switch methods, or generalize a
package beyond its supported modality, species, resource, or task boundary.
