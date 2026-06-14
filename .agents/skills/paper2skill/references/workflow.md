# Paper2Skill Compiler Workflow

Paper2Skill is a generalized paper-method-to-agent-skill compiler. The core
loop is:

```text
thin plan -> controlled run -> promotion plan -> verified reusable skill
```

The compiler must not hardcode one algorithm. CONCORD is only a Python
single-cell golden case.

## Stable Stages

1. `collect_sources`
   - Collect paper, repository, docs, tutorials, examples, tests, and optional benchmark cases.
   - Prefer explicit local paths or reviewed official URLs.

2. `normalize_evidence`
   - Convert source observations into evidence claims with source, officialness, confidence, and claim type.
   - Do not rely on hidden conversation context.

3. `build_tutorial_graph`
   - Catalog multiple tutorials/examples independently.
   - Do not collapse them into one workflow before ranking.

4. `rank_execution_candidates`
   - Select the safest official minimal/demo path first.
   - Default ranking: official test/minimal data > package dataset > official script > official notebook > README quickstart > full large tutorial > paper narrative only.

5. `run_candidate`
   - Execute only with explicit user approval and a reviewed manifest.
   - Record environment probe, install plan, command/API sequence, input bindings, produced files, stdout/stderr tails, repair attempts, output validation, and resource usage when available.

6. `synthesize_contracts`
   - Generate adapter, input/output, bio, and environment contracts.
   - Bio contract fields must carry evidence metadata: `evidence_id`, `source_type`, and `claim_type`.

7. `promote_skill`
   - Promote adapters only from a passing run trace with passing output validation.
   - Static inference can only create `dry_run_only` adapters.

8. `evaluate_maturity`
   - Assign L1/L2/L3/L4 based on explicit artifacts.
   - Do not transfer one verified example's status to other examples.

## Core Artifacts

- `execution_plan.yaml`: thin plan and selected candidate.
- `tutorial_catalog.yaml`: independent records for tutorials/examples.
- `run_trace.json`: controlled execution evidence for one candidate.
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
