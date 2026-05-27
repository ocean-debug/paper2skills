# Paper2Skill Builder

Paper2Skill Builder turns an algorithm paper, an official source repository,
and an official tutorial or example into a Codex-readable skill directory. It
is not a paper summarizer and it is not an MCP server or plugin packager in the
MVP. The first release focuses on generating self-contained Codex skills with
evidence reports, environment preflight, install planning, execution planning,
and output validation.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Quick Start

```bash
python -m paper2skill.cli --help
python -m paper2skill.cli build --example toy_python
python -m paper2skill.cli validate --skill .agents/skills/toy-python-skill
python -m paper2skill.cli test --skill .agents/skills/toy-python-skill --mode all
```

## Inputs

The builder accepts paper, repository, and tutorial inputs directly from CLI
flags, or uses built-in toy examples:

```bash
python -m paper2skill.cli build \
  --paper path/to/paper.md \
  --repo path/to/repo \
  --tutorial path/to/tutorial.ipynb \
  --skill-name algorithm-task \
  --out .agents/skills/algorithm-task
```

Paper semantic interpretation is intentionally left to Codex or ClaudeCode. The
CLI records paper sources and extracts local text when available, but does not
call an online LLM or article API.

## Generated Skill Shape

```text
.agents/skills/<skill-name>/
  SKILL.md
  scripts/
    preflight.py
    env_manager.py
    plan.py
    run.py
    validate_outputs.py
  references/
  assets/
  tests/
  agents/openai.yaml
```

Generated scripts are self-contained. A child skill can run outside this
builder repository as long as Python is available and the declared algorithm
runtime dependencies are installed.

## Environment Policy

Every generated skill must run preflight before executing an algorithm. Missing
dependencies block execution, produce environment and install reports, and never
trigger installation unless the user explicitly runs install with
`--confirm yes`. In CI or non-interactive shells, `ask` behaves as `never`.

## Maturity Levels

The builder records maturity explicitly. The MVP targets stable L1 generation:
contracts, preflight, environment checks, and execution planning. The built-in
toy Python and toy R examples are intended as L2 demo-executable examples.

## Roadmap

- MVP: Codex Skill generation for Python and R algorithm repositories.
- Later: optional MCP export.
- Later: optional Codex plugin packaging.
- Out of scope for MVP: GPU/CUDA auto-configuration, large dataset download,
  arbitrary install script execution, and complex workflow engine generation.
