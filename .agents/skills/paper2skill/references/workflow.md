# Paper2Skill Compiler Workflow

Paper2Skill is a generalized paper-method-to-agent-skill compiler. The core
loop is:

```text
thin plan -> run -> promotion plan -> child skill
```

The compiler must not hardcode one algorithm. CONCORD is only a Python
single-cell golden case.

## Public Phases

`paper2skill build` stops after the static L1 child skill and dry-run
self-check. `paper2skill reproduce` calls that build path and then continues
through the fixed agentic reproduction loop:

```text
catalog -> build L1 -> env_probe -> data_probe -> adapter_materialize ->
smoke_run -> error_classify -> repair -> rerun -> promote -> emit skill
```

`reproduce` succeeds only when a selected official/minimal example reaches at
least L2: smoke execution passes, `run_trace.json` is promotion-ready, and the
selected adapter is promoted to `verified`.

1. `thin_plan`
   - Catalog official tutorials/examples independently before choosing a run path.
   - Explicit tutorial paths choose the default validation target, but they must
     not limit catalog coverage. Repository tutorial indexes, README toctrees,
     docs indexes, and all official candidate tutorials remain visible in
     `tutorial_catalog.yaml` or `missing_indexed_tutorials`.
   - Use paper and repository evidence as supporting context for applicability,
     API, environment, bio input/output, and refusal boundaries.
   - Infer candidate adapters and contracts, but keep adapters `dry_run_only`
     until run evidence exists.
   - Write `algorithm_contract.applicability` and
     `algorithm_contract.recommended_execution` so the child skill can decide
     when to run, when to plan only, and when to refuse without relying on chat
     history.
   - Rank candidates by safety: official test/minimal data > package dataset >
     official script > official notebook > README quickstart > full large
     tutorial > paper narrative only.

2. `run`
   - Execute only one selected candidate, only with explicit user approval and a
     reviewed manifest.
   - In `reproduce`, execution approval is `--confirm-run yes`; installation is
     separately controlled by `--install-policy never|plan|yes`.
   - Record environment probe, install plan, command/API sequence, input
     bindings, adapter report, produced files, stdout/stderr tails, repair
     attempts, output validation, and resource usage when available.
   - Repair loops may edit only the generated child skill or adapter scripts.
     Upstream repository source must not be modified implicitly.

3. `promotion_plan`
   - Promote an adapter only when the run trace is non-demo, the adapter report
     has `status=pass`, and output validation has `status=pass`.
   - Refuse demo summaries, dry-runs, missing adapter reports, failed adapter
     execution, failed output validation, and examples not present in
     `tutorial_catalog.yaml`.
   - Keep verification per tutorial/example. One passing tutorial must not imply
     another tutorial or user-data path is executable.

4. `child_skill`
   - Emit a compact installable skill with preflight, plan, run, output
     validation, tutorial catalog, evidence summary, contracts, and maturity.
   - Preflight must refuse incompatible requests or inputs with structured
     `refusal_reasons` containing `code`, `path`, and `message`.
   - `run.py` must also enforce `applicability.real_execution_allowed` and
     `recommended_execution.can_execute_real_data` before non-demo execution.
   - Assign L1/L2/L3/L4 based only on explicit artifacts.

## Contract Rules

- Adapter, input/output, bio, and environment contracts are produced during
  `thin_plan` and updated only through `promotion_plan`.
- The algorithm contract must include machine-readable applicability and
  recommended execution fields: supported task, domain, modality, adapter
  status, maturity level, allowed execution modes, real execution gate,
  default manifest, entrypoints, core API/command, and refusal rules.
- Bio contract fields must carry evidence metadata: `evidence_id`,
  `source_type`, and `claim_type`.
- Child skills must treat IO and bio contract mismatches as blocking preflight
  failures rather than warnings.
- Static API, CLI, notebook, script, workflow, or container inference can only
  create `dry_run_only` adapters.

## Core Artifacts

- `execution_plan.yaml`: thin plan and selected candidate.
- `tutorial_catalog.yaml`: independent records for tutorials/examples.
- `run_trace.json`: controlled execution evidence for one candidate.
- `agentic_run/repair_log.jsonl`: per-attempt error, hypothesis, repair, and
  rerun records for `paper2skill reproduce`.
- `agentic_run/env_delta.json`: before/after package snapshots, import probes,
  dry-run install plan, optional approved install result, and `pip check`.
- `agentic_run/promotion_report.json`: final promotion gate result.
- `references/contracts/*.yaml`: adapter, IO, bio, environment, and algorithm contracts.
- `references/maturity.yaml`: current L1/L2/L3/L4 status.
- `references/evidence_summary.md`: compact evidence summary for agents.

Large source parses, repository indexes, full tutorial traces, and evidence
graphs belong in debug artifacts, not the default agent context.

## Child Skill Output

The child skill should include:

- `SKILL.md`
- `scripts/preflight.py`
- `scripts/plan.py`
- `scripts/run.py`
- `scripts/validate_outputs.py`
- `references/*`
- `assets/*`
- optional `agents/openai.yaml`

The agent-facing compact references are:

- `references/tutorial_catalog.yaml`
- `references/maturity.yaml`
- `references/evidence_summary.md`
- `references/contracts/algorithm_contract.yaml`
- `references/contracts/adapter_contract.yaml`
- `references/contracts/bio_contract.yaml`
- `references/contracts/environment_contract.yaml`
- `references/contracts/io_contract.yaml`
- `assets/official_attempt_manifest.yaml`
- `assets/input_manifest_template.yaml`

`assets/demo_input_manifest.yaml` may exist as a local smoke/demo asset, but it
is not an execution candidate for promotion.
