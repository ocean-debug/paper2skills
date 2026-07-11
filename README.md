# Paper2Skills v1.0

Paper2Skills is a Codex skill that compiles one bioinformatics algorithm's
official source repository and official tutorials or examples into one
evidence-grounded child skill.

It is not a paper summarizer. Source code and official tutorials define the
operational workflow. Papers are optional supporting evidence for method
intent, assumptions, applicability, and author-stated limitations.

## Output contract

- One algorithm package produces one child skill.
- Each supported analysis goal is routed as a `task_type`.
- Each task is rendered to its own `references/task-*.md` file.
- APIs and operational claims require inspected evidence IDs.
- Every task defines accepted inputs, refusal rules, technical validation,
  biological interpretation boundaries, troubleshooting, and reuse guidance.
- Static inspection produces `source_grounded` status. Only a successful,
  task-specific execution witness may upgrade a task to `execution_verified`.

## Install as a Codex skill

Paper2Skills requires Python 3.10 or newer and PyYAML 6 or newer.

```bash
python -m pip install "PyYAML>=6.0"
```

Copy `paper2skills/` into your Codex skills directory, for example:

```bash
cp -R paper2skills "${CODEX_HOME:-$HOME/.codex}/skills/paper2skills"
```

Then invoke `$paper2skills` with an official repository and official
tutorials, examples, demos, or notebooks.

## Build workflow

Copy the request template outside the installed skill and fill in the official
source revision, local source/tutorial paths, key APIs, and output directory.

```bash
cp paper2skills/assets/build-request.yaml request.yaml

python paper2skills/scripts/paper2skills.py init --request request.yaml
python paper2skills/scripts/paper2skills.py ground --run runs/example-package

# Codex reads agent_packet.md and fills the evidence-backed skill_spec.yaml.

python paper2skills/scripts/paper2skills.py render --run runs/example-package
python paper2skills/scripts/paper2skills.py validate --run runs/example-package
python paper2skills/scripts/paper2skills.py publish --run runs/example-package
```

Use `apply-patch` for bounded SkillIR revisions. Publishing is fail-closed and
writes only to the run-local `published/` directory; installation remains a
separate user-controlled action.

## Evidence priority

1. Official runnable tutorials and examples.
2. Current source, public APIs, and official tests.
3. Official documentation and repository usage instructions.
4. Paper Methods and supplementary materials.
5. Paper abstract.

When tutorial code conflicts with the pinned source revision, follow the
source behavior and record the conflict.

## Scope

Version 1.0 is Python-first. Unsupported language backends are refused rather
than silently replaced with a different implementation.

Paper2Skills contains the deterministic grounding, rendering, patching,
validation, and publication layer. Codex supplies the reasoning needed to
identify analysis goals and synthesize evidence-backed task contracts;
Paper2Skills does not call an LLM SDK.

## License

Paper2Skills is released under the [MIT License](LICENSE).

The bounded review and fail-closed publication design was informed by
`omicverse/omicos-portbuild` revision
`9899d091427f86f038f8e73eac025044ca68d110` (BSD-2-Clause). Paper2Skills does
not publish OmicOS schemas, deployment integrations, or multi-capability
bundle layouts.
