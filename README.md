# Paper2Skill Builder

Paper2Skill Builder turns an algorithm paper, an official source repository,
and an official tutorial or example into a Codex-readable skill directory. It
is not a paper summarizer and it is not an MCP server or plugin packager in the
MVP. The first release focuses on generating self-contained Codex skills with
evidence reports, environment preflight, install planning, execution planning,
and output validation.

## Install

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
```

Optional document parsing extras:

```bash
python -m pip install -e ".[paper,html]"
```

## Quick Start

```bash
python -m paper2skill.cli --help
python -m paper2skill.cli build --example toy_python
python -m paper2skill.cli validate --skill .agents/skills/toy-python-skill
python -m paper2skill.cli test --skill .agents/skills/toy-python-skill --mode all
```

Development quality gates:

```bash
python -m pytest -q -m "not benchmark"
python -m pytest -q -m benchmark tests/benchmarks
python -m pytest -q
```

Benchmark-driven development for real-world cases is documented in
[`docs/benchmark.md`](docs/benchmark.md).

Minimal end-to-end build from paper and repository inputs:

```bash
python -m paper2skill.cli build \
  --paper examples/minimal_paper.md \
  --repo examples/minimal_repo \
  --out /tmp/paper2skill_minimal_skill \
  --no-execute-tutorials

python -m paper2skill.cli validate --skill /tmp/paper2skill_minimal_skill
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
    adapters/
  references/
  assets/
  tests/
  agents/openai.yaml
```

Generated scripts are self-contained. A child skill can run outside this
builder repository as long as Python is available and the declared algorithm
runtime dependencies are installed.

Three-stage evidence builds also write the machine-readable collection and
inference bundle:

```text
references/paper.md
references/paper_sections.json
references/paper_parser_report.json
references/repo_manifest.json
references/repo_index.json
references/workflow_dag.json
references/tutorial_candidates.json
references/tutorial_scanner_report.json
references/io_contract.yaml
references/evidence_graph.json
references/adapter_spec.yaml
references/build_report.json
```

## Environment Policy

Every generated skill must run preflight before executing an algorithm. Missing
dependencies block execution, produce environment and install reports, and never
trigger installation unless the user explicitly runs install with
`--confirm yes`. In CI or non-interactive shells, `ask` behaves as `never`.

## Current Support Matrix

Supported now:

- Local repository builds and basic `file://` remote clone/index flows.
- Markdown, plain text, HTML, and optional MarkItDown document parsing.
- Python and R toy skill generation.
- Tutorial scanning, dependency mining, workflow DAG inference, and modality-aware bio IO contracts.
- Environment preflight, install planning, and gated disposable conda environment creation.
- Adapter lifecycle tracking via `references/adapter_spec.yaml` and `references/adapter_review.yaml`.
- Static notebook execution policy reports via `references/notebook_execution_policy.json`.
- Demo-only execution and blocked non-demo runs when adapters are not `ready`, `reviewed`, or `verified`.

Experimental:

- Full remote repository inference from cloned sources.
- Evidence graph conflict decisions.
- Source-aware bio contract inference.
- Adapter-based execution scaffolding.
- R/Bioconductor metadata hints from DESCRIPTION, NAMESPACE, and R source.
- IPython notebook shell/cell magic, parameter, path, and risk detection.
- Optional offline benchmark coverage for synthetic omics algorithm paper, repository, and tutorial shapes.

Not yet:

- Robust large benchmark coverage against real-world repository diversity.
- Complete online Bioconductor metadata resolution.
- CUDA/system library automatic configuration.
- Large dataset download automation.
- Arbitrary install script execution.
- Fully automatic real algorithm execution for unknown repositories. Unknown adapters stay `candidate` or `blocked`; only `ready`, `reviewed`, or `verified` adapters execute.

## Maturity Levels

The builder records maturity explicitly. The MVP targets stable L1 generation:
contracts, preflight, environment checks, and execution planning. The built-in
toy Python and toy R examples are intended as L2 demo-executable examples.

## Roadmap

- MVP: Codex Skill generation for Python and R algorithm repositories.
- Next: broader benchmark suite for omics algorithm paper, repository, and tutorial evidence shapes.
- Later: optional MCP export.
- Later: optional Codex plugin packaging.
- Out of scope for MVP: GPU/CUDA auto-configuration, large dataset download,
  arbitrary install script execution, and complex workflow engine generation.
