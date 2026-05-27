---
name: paper2skill-builder
description: Use this skill when the user wants to generate a Codex skill from an algorithm paper, official source code repository, and official tutorial or example. The generated skill must include environment preflight, dependency checks, install planning, execution planning, output validation, and evidence reports.
---

# Paper2Skill Builder

Use this repository-level skill to run Paper2Skill Builder from a paper, an
official repository, and official tutorial evidence.

## Workflow

1. Confirm the paper, repository, tutorial, skill name, and output directory.
2. Run `python -m paper2skill.cli plan` to inspect evidence without writing a child skill.
3. Run `python -m paper2skill.cli build` to generate the child Codex Skill.
4. Run `python -m paper2skill.cli validate --skill <skill-dir>`.
5. Run `python -m paper2skill.cli test --skill <skill-dir> --mode all`.

## Environment Policy

Generated child skills must run `scripts/preflight.py` before `scripts/run.py`.
Missing dependencies block execution and produce install plans. No installation
may run unless the user explicitly approves and passes `--confirm yes`.

## Boundaries

The MVP does not generate MCP servers or Codex plugin packages. It does not
download large datasets, configure GPU/CUDA automatically, or run arbitrary
repository install scripts.
