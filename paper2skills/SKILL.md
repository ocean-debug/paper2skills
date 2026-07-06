---
name: paper2skills
description: Build lightweight Codex child skills for scientific algorithm packages from official source repositories, tutorials, documentation, and papers. Use when an agent needs source-grounded task_type routing, input-output contracts, refusal boundaries, validation guidance, and evidence references for a package.
---

# paper2skills

paper2skills builds one lightweight child skill per scientific algorithm
package. The child skill is not a code summary. It is an agent-readable
operational guide: what the package can do, what it cannot do, which
`task_type` to choose, what inputs are required, what outputs should exist, how
to validate them, and when to refuse.

## First Principles

Agents fail on scientific packages when they guess across missing boundaries.
paper2skills reduces guessing by compiling official package evidence into a
small skill with:

- task-type routing
- input-output contracts
- limitations and refusal rules
- validation guidance
- troubleshooting notes
- evidence references
- environment boundaries

Evidence priority is:

```text
execution trace > official tutorials/docs > source code/API > paper
```

Do not mark a task as verified unless validated execution evidence exists.

## Workflow

1. Run Discovery preflight to avoid duplicating existing Codex child skills.
2. Ground sources from official repository, tutorials, docs, and papers.
3. Optionally fetch/register official sources and parse them into compact source
   index and source parse report records without executing code. Audit source
   fetch boundaries before parsing so remote fetch opt-in, run-directory
   containment, and archive extraction safety are explicit.
4. Convert parsed records into evidence cards, source manifest, tutorial steps,
   evidence coverage, tutorial steps, API-grounding candidates, and static
   interface hints. Record source parsing coverage so parser capability and
   source-kind gaps are explicit, then audit parsing strategy, provenance, and
   non-execution boundaries.
5. Build the backend contract, static environment hints, and non-downloading
   model/checkpoint/data resource inventory.
6. Partition package capabilities into `task_type` entries and attach parameter
   constraints. Attach operational recipes that turn tutorial/API/interface
   evidence into task-specific Quick Workflows, API sequences, outputs, and
   validation checks. Record a task partition decision log so accepted task_type
   candidates and rejected tutorial-shaped split candidates are explicit.
7. Run final Discovery with the inferred `task_type` set and audit both the
   reuse/update/create decision and the field-level match quality.
8. Draft a task-type router, task partition audit, task conflict matrix, and
   static routing fixture for the single child skill.
9. Run the agent-driven paper2skills review loop against evidence, tutorial,
   environment, API/interface grounding, operational recipes, parameter
   contracts, refusals, and validation. Python records `record_score`, rollout-plan, analyst,
   merge, ranking, apply, strict-gate, and slow-update state; Codex supplies
    the optimizer JSON through `agent_review_proposals`. The proposal must
    include non-empty analyst, merge, ranking, and slow-update payloads; every
    operation must include a stable `operation_id` and cite same-iteration
    `finding_codes`; ranking must select by `operation_ids` or
    `operation_indices` before apply. If the rubric does
   not pass and no complete agent proposal is supplied, stop at `needs_agent`;
   run `review-next-step --run <run_dir>`, add the bounded proposal entry to
   the request, and rerun.
   Record review evolution and a run-level SVG plot so score movement, patch
   actions, and stop reasons remain auditable. Record review prompt contracts so draft, record-score,
   rollout-plan, critic, analyst, merge, ranking, slow-update, patch-plan, revision, and gate states have required fields and allowed
   actions. Record review cursor and patch-application artifacts so iteration
   state, resumability, and agent proposals are explicit. Record optimizer
   state, score cache, rejected buffer, and patch-safety audits so strict
   improvement policy, rejected edits, state hashes, and allowed patch
   boundaries are explicit.
   Audit review discipline so stop reasons, gate states, and patch score
   movement are checked before publish. Audit rubric grounding so every awarded
   score has a recorded support signal. Audit the review trajectory so
   evolution, cursor, patches, optimizer state, prompt contracts, and rubric
   grounding agree before publish.
10. If execution grounding is requested, use only explicit execution evidence to
   mark task types as verified, validate supplied trace structure, and audit
   rendered verification claims before publish.
11. Resolve evidence precedence by task claim so execution trace, official
    tutorials/docs, source/API, and paper evidence cannot be conflated.
12. Create static eval scenarios, a plan-only execution grounding plan, a
    plan-only environment install plan, a resource boundary audit, a plan-only
    tutorial reproduction plan, and an evidence traceability ledger plus
    acceptance suite for routing, contracts, refusals, ambiguity, tutorial
    replay, and execution boundaries.
    Build a lineage graph from source evidence to task contracts and
    child-skill files. Split cases into train, selection, and test eval sets,
    and judge only explicitly supplied eval results.
13. Generate the lightweight child skill, including a task-specific Quick
    Workflow/API sequence and a first-principles workflow DAG for every
    `task_type` in the child `SKILL.md`.
14. Audit rendered verification claims, child metadata, child package purity, lint the child skill, check draft readiness, audit output/public package
    boundaries, create a plan-only skill update plan, audit update/reuse safety, create a plan-only
    forward-test plan, create a plan-only agent rollout harness, audit E2E
    acceptance scenarios and supplied E2E results, audit rendered claim consistency, audit child reference
    coverage, audit task_type routing metadata, audit source grounding traceability, audit first-principles
    workflow invariants, audit the builder runtime, module inventory, builder skill package shape, build request template, request fingerprint, and builder version surface, audit the phase ledger, audit cross-stage protocol compliance, run the API/interface grounding gate, write
    machine-readable artifact contracts, audit artifact closure, audit code
    fences, run the public safety audit, validate artifacts, pass the action-aware publish gate, record candidate
    registry, audit candidate selection and promotion, write release-package
    metadata, audit the final candidate, summarize quality, write the plan-only
    Codex publish adapter, check install readiness, audit the publish manifest,
    write the score report,
    audit architecture completeness, audit completion evidence, write the
    acceptance handoff package, audit final completion,
    record and audit the build timeline, render the run scorecard, and record
    the run manifest before publishing.
15. Run output retention: keep `child_skill/`, copy iteration/version artifacts
    into `iteration_versions/`, write `generation_process.md`, and delete
    builder-generated process files when `cleanup_process_files` is true.

## Design Principles

- Discovery checks existing Codex child skills before creating a new one and
  audits match strength before reuse or update.
- Capability partition produces `task_type` entries inside one child skill.
- Routing guidance helps the agent choose the correct `task_type`.
- One algorithm package produces one lightweight child skill.
- Generated skills stay evidence-grounded and avoid unsupported claims.

## Required Inputs

Use `templates/build_request.yaml`. Required fields are:

- `package_name`
- `repo_url`
- at least one of `tutorial_links`, `doc_links`, or `paper_links`
- optional `paper_dois` and `api_names` to strengthen Discovery
- optional `source_material_paths` for local or already downloaded evidence
- `target_agent: codex`
- `language_backend: python`
- `execution_grounded: true|false`
- `output_dir`

R is a reserved backend extension. Until the R backend is implemented, R-only
packages should produce an explicit backend refusal boundary instead of
pretending to be runnable.

## Builder Architecture

The CLI entrypoint lives at `scripts/paper2skills.py`; phase logic is split
across focused modules in `scripts/`. Standalone audit commands such as
`audit-protocol-compliance` recompute reports from saved artifacts without
executing package code.

```bash
python scripts/paper2skills.py build --request templates/build_request.yaml --out runs/method
```

Module responsibilities:

- `common.py`: shared file IO, serialization, path, slug, list, and Markdown
  table helpers.
- `constants.py`: schema version, builder version, child reference, parser, and
  heuristic constants.
- `action_policy.py`: normalizes Discovery decisions into create, update, or
  reuse release actions and defines action-specific status expectations.
- `build_pipeline.py`: orchestrates the end-to-end artifact flow.
- `builder_baseline_audit.py`: checks expected engineering baseline families
  are covered by concrete modules and public inventory docs.
- `builder_runtime_audit.py`: statically checks builder skill metadata, build
  request template fields, UI metadata, and required CLI commands without
  running the CLI.
- `agent_metadata_audit.py`: checks `SKILL.md` trigger metadata and
  `agents/openai.yaml` UI metadata stay aligned with the installable skill name,
  default prompt, and source-grounded task_type contract/refusal/evidence scope.
- `builder_version_audit.py`: checks schema and builder version consistency
  across core release-facing artifacts.
- `public_origin_audit.py`: checks README and builder skill package text for
  private origin markers, legacy labels, or machine-specific execution details.
- `request_model.py`: normalizes build requests and fills default fields before
  auditing.
- `request_audit.py`: audits normalized build request fields, source support,
  numeric bounds, and execution environment boundaries.
- `request_template_audit.py`: audits build request template consistency with
  request normalization, request-audit constants, and runtime template fields.
- `request_fingerprint.py`: records stable redacted request hashes, request key
  names, and sensitive field paths for reproducible run identity.
- `discovery.py`: scans standard child-skill files and checks existing Codex
  child skills.
- `discovery_audit.py`: audits reuse, update, or create decisions and task
  coverage for matched skills.
- `discovery_match_audit.py`: audits field-level match strength, ambiguity,
  task_type coverage, and existing child-skill shape.
- `discovery_resolution_audit.py`: audits final Discovery resolution against
  preflight matches, match audit, and update planning to block duplicate publish
  risk.
- `phase_state.py`: records auditable build phases and gates.
- `phase_state_audit.py`: audits phase ledger structure, phase gates, artifact
  contracts for YAML outputs, and output ownership.
- `source_fetch.py`: safely fetches or registers official source material when
  explicitly enabled, with run-local cache reuse for successful downloads.
- `source_fetch_boundary_audit.py`: audits fetch opt-in, run-directory
  containment, and archive extraction safety before source parsing.
- `source_grounding.py`: records official evidence sources.
- `source_grounding_audit.py`: audits evidence priority, non-execution source
  parsing boundaries, task evidence references, traceability, and rendered
  evidence sections.
- `source_index.py`: indexes source files without executing code; Python files
  include AST symbol, signature, docstring, branch-value, and call hints.
- `source_parser.py`: records source parsing strategy, parser capability
  matrix, counts, compact samples, and limitations.
- `source_parsing_coverage.py`: audits static parser coverage by source kind
  and records fetch/parser gaps.
- `source_parsing_audit.py`: audits source parsing strategy, provenance fields,
  and non-execution boundaries.
- `evidence_claim_taxonomy_audit.py`: audits task-level claim types and source
  priority so operational claims are not supported only by paper evidence.
- `source_ingestion_audit.py`: audits evidence id and count lineage across
  source grounding, fetch/register, index, parse report, manifest, and evidence
  cards.
- `evidence_cards.py`: creates concise evidence cards.
- `evidence_coverage.py`: summarizes task_type evidence priority and claim-type
  coverage.
- `evidence_precedence.py`: resolves accepted evidence per task claim using the
  source priority policy.
- `source_manifest.py`: summarizes source provenance, fetch status, indexing,
  and evidence-card coverage.
- `tutorial_miner.py`: extracts compact tutorial/example step order.
- `api_grounding.py`: derives API candidates from parsed source records.
- `interface_inspector.py`: extracts signatures, defaults, docstrings, and
  branch-parameter hints without importing package code.
- `key_api_coverage_audit.py`: audits that explicit build-request `api_names`
  are covered by parsed API or interface grounding.
- `backend_contracts.py`: records Python-first support and backend extension
  refusal boundaries.
- `backend_extension_audit.py`: audits implemented backend support, reserved R
  extension boundaries, no-execution install strategy, and required refusals.
- `environment_miner.py`: mines dependency manifests, imports, and GPU hints.
- `environment_install_plan.py`: records plan-only installation strategy,
  required approvals, dependency hints, and refusal boundaries.
- `resource_inventory.py`: mines model registry IDs, checkpoint files, external
  artifact URLs, data artifacts, and model-loading APIs without downloading
  resources.
- `resource_boundary_audit.py`: audits that resource permissions, licenses,
  tokens, missing weights, and large downloads are rendered as refusal and
  environment boundaries.
- `execution_plan.py`: records plan-only execution grounding boundaries and
  environment requirements.
- `tutorial_reproduction_plan.py`: records plan-only tutorial replay queues,
  trace requirements, success criteria, and refusal conditions for each
  `task_type`.
- `contract_traceability.py`: expands task contracts into evidence-linked
  input, output, validation, and refusal records.
- `lineage_graph.py`: builds compact source-to-task-to-child-file provenance.
- `acceptance_suite.py`: records static cases for routing, refusal, contracts,
  traceability, ambiguity, eval, tutorial replay, and execution boundaries.
- `smoke_test_plan.py`: records plan-only child-skill package-shape smoke
  scenarios and audits explicitly supplied smoke results.
- `eval_splits.py`: builds stable train, selection, and test splits from static
  eval, routing, and acceptance cases.
- `eval_result_judge.py`: judges only explicit eval outcomes supplied in the
  build request.
- `agent_rollout_harness.py`: builds a plan-only rollout queue from
  forward-test, routing, and eval artifacts while keeping judge metadata out of
  agent prompts.
- `task_partition.py`: maps package capabilities to `task_type` and attaches
  operational recipes from tutorial, API, interface, and parameter evidence.
- `task_partition_decision_log.py`: records accepted, merged/deferred, and
  rejected task_type candidates.
- `parameter_miner.py`: mines static parameter constraints from inspected
  interfaces and attaches them to input contracts.
- `task_router.py`: writes task-type routing rules.
- `task_partition_audit.py`: audits task_type granularity so capabilities are
  not split one tutorial, demo, or notebook at a time.
- `task_conflict.py`: writes ambiguity and conflict-selection rules between
  task types.
- `routing_fixture.py`: writes static task_type selection, refusal,
  unsupported, and ambiguity cases.
- `eval_plan.py`: creates static acceptance, refusal, and API-review scenarios.
- `quality_report.py`: summarizes review, lint, validation, protocol, audit,
  gate, and task-contract blockers.
- `draft_candidate.py`: summarizes the one child-skill draft candidate.
- `child_metadata_audit.py`: audits child `SKILL.md` frontmatter, Codex trigger
  description, task_type mentions, and one-child-skill shape.
- `child_package_purity_audit.py`: audits that public child skills contain only
  `SKILL.md` plus the standard `references/` files, with no build traces,
  candidates, assets, scripts, staging files, or auxiliary docs.
- `draft_readiness.py`: blocks unresolved draft markers and build-template
  values from generated child skills.
- `output_boundary_audit.py`: blocks child-skill output outside the build
  output tree, run outputs inside likely skill install roots, or public child
  packages containing build artifacts.
- `skill_update_plan.py`: turns Discovery's reuse, update, or create decision
  into a plan-only release action and manual merge guidance.
- `skill_update_audit.py`: audits that create, update, and reuse guidance stays
  plan-only, non-destructive, and limited to standard child-skill files.
- `forward_test_plan.py`: creates plan-only prompts and judging controls for
  independent child-skill forward tests without leaking expected behavior, and
  validates saved forward-test plans.
- `claim_consistency_audit.py`: checks rendered task, evidence, refusal,
  backend, and verification claims against build artifacts.
- `biological_claim_boundary_audit.py`: checks rendered child skills for
  unsupported high-risk cross-modal biological claims and required refusal
  boundaries.
- `child_reference_coverage.py`: checks that generated references consume
  source parsing coverage, environment install boundaries, tutorial replay
  plans, evidence precedence, task conflicts, operational recipes, and
  task_type entries.
- `routing_metadata_audit.py`: checks task_type router scope, rendered routing
  guidance, refusal boundaries, and ambiguity fixtures.
- `workflow_invariant_audit.py`: checks one-package-one-skill, task_type,
  Codex target, backend, candidate, child-file, and cross-artifact coverage
  invariants, including tutorial reproduction plan coverage.
- `requirement_coverage.py`: maps first-principles product requirements to
  concrete build artifacts and gates.
- `completion_evidence_audit.py`: distinguishes static build completion from
  full real-package completion supported by rollout, E2E, and execution
  evidence.
- `acceptance_handoff.py`: packages rollout, replay, and E2E result templates
  into run-local handoff YAML and Markdown for external validation.
- `protocol_compliance_audit.py`: audits cross-stage plan-only, external
  result, output-boundary, verification, and completion-evidence protocols.
- `architecture_completeness_audit.py`: checks run-level phase coverage and
  focused gate artifacts across the full builder architecture.
- `build_timeline.py`: records phase, review, and gate events.
- `build_timeline_audit.py`: checks timeline event ids, phase/review counts,
  and gate-event coverage.
- `candidate_registry.py`: records candidate version status and gate outcomes.
- `candidate_selection_audit.py`: records why the active child-skill candidate
  was selected before promotion.
- `candidate_promotion_audit.py`: checks active candidate promotion before
  release packaging.
- `final_candidate_audit.py`: checks that release package metadata points to
  the selected and promoted active candidate before publish planning.
- `candidate_evolution_audit.py`: checks candidate identity and gate status
  remain stable from draft through registry, selection, promotion, release, and
  final candidate records.
- `score_report.py`: summarizes review trajectory, rubric grounding, quality
  blockers, publish blockers, candidate gates, candidate evolution status,
  Codex publish adapter status, install readiness, and publish manifest audit
  status.
- `release_packager.py`: records release package files and install plan without
  copying files.
- `release_action_audit.py`: checks that create, update, or reuse release
  action statuses agree across final release artifacts.
- `codex_publish_adapter.py`: converts release actions into plan-only Codex
  install, update, or reuse steps without copying files.
- `install_readiness.py`: checks final public child-skill files are ready to
  copy for create/update, and marks reuse as not applicable.
- `completion_audit.py`: aggregates final semantic gates into one run-level
  completion verdict, including release action consistency.
- `publish_manifest_audit.py`: checks publish manifest consistency with
  release, install-readiness, and reuse/update/create decisions.
- `run_scorecard.py`: renders a one-page run-level Markdown scorecard from the
  final score, quality, protocol, release, completion, and timeline artifacts.
- `run_manifest.py`: records generated artifact and child-skill file hashes for
  run-level provenance.
- `output_retention.py`: retains the final child skill, iteration/version
  artifacts, and generation process document, then removes process files when
  cleanup is enabled.
- `grounding_gate.py`: checks task API/interface grounding before publish.
- `agent_rollout_audit.py`: checks plan-only rollout scenario mapping, leakage
  controls, judge-only metadata separation, and rollout count consistency.
- `agent_rollout_result_judge.py`: judges explicitly supplied agent rollout
  results against rollout expectations without launching agents.
- `e2e_acceptance.py`: builds plan-only real end-to-end acceptance scenarios,
  result templates, and audits explicitly supplied E2E results without running
  package code.
- `smoke_test_plan.py`: builds plan-only smoke scenarios for generated
  child-skill files, task routing, contracts, refusals, verification labels,
  and publish-plan shape.
- `api_surface_audit.py`: checks rendered code fences, inline API-like mentions,
  requested API names, and task API-surface gaps against parsed grounding.
- `key_api_coverage_audit.py`: enforces exact grounding coverage for explicit
  key APIs before publish.
- `eval_leakage_audit.py`: checks eval split isolation and agent prompt leakage
  for forward-test and rollout artifacts.
- `external_result_contracts.py`: audits supplied eval, rollout, replay, and
  E2E result schemas and blocks judge-only metadata or prompts in external
  evidence.
- `artifact_contracts.py`: declares minimum artifact fields and list/mapping
  types for validation.
- `artifact_closure_audit.py`: checks required artifact contracts,
  pre-publish availability, phase outputs, and run write-plan coverage.
- `artifact_validator.py`: checks pre-publish artifact contracts, schema, and
  consistency.
- `code_fence_audit.py`: checks generated Markdown for local path leaks and
  ungrounded code-fence API calls.
- `public_safety_audit.py`: checks generated public Markdown for credentials,
  private keys, contact identifiers, and long copied excerpts.
- `skill_draft.py`: renders the lightweight child skill, including one
  task-specific Quick Workflow/API sequence and one first-principles workflow
  DAG per `task_type`.
- `self_review.py`: checks overclaims, evidence gaps, operational recipes,
  contracts, refusals, and verification labels.
- `review_rubric.py`, `patch_planner.py`, and `review_loop.py`: run bounded
  agent-driven paper2skills review loop iterations with recipe scoring, record-score,
  rollout-plan, analyst, merge, ranking, apply, strict-gate, and slow-update
  states.
- `review_evolution.py`: summarizes review score trajectory, patch actions, and
  gate reasons.
- `review_evolution_plot.py`: renders a run-level SVG review trajectory from
  review evolution metadata without executing package code.
- `review_iteration_log.py`: renders a run-level Markdown summary of each
  review iteration's score, blockers, patch actions, and gate reason.
- `review_prompt_contracts.py`: records static state-role contracts for draft,
  critic, patch-plan, revision, and gate review states.
- `review_prompt_materials.py`: records static review prompt materials,
  allowed inputs, required outputs, and forbidden outputs for each role.
- `review_prompt_suite_audit.py`: audits review duty coverage for grounding,
  task split, contracts, refusals, validation, verification, patch planning,
  and gate discipline.
- `review_cursor.py`: records the current review cursor, stop reason,
  resumability, and required per-iteration states.
- `patch_application.py`: audits planned and applied agent proposal patch
  actions from the review loop.
- `review_remediation_audit.py`: accounts for every non-info review finding as
  patched, cleared, gate-accepted, or still unresolved.
- `review_optimizer_state.py`: records review iteration hashes, cache key,
  strict improvement policy, and rejected edits.
- `patch_safety_audit.py`: checks patch records stay within bounded in-memory
  artifact boundaries and contain no commands, installs, network actions, or
  file targets.
- `patch_operation_contracts.py`: checks agent proposal patch operation names,
  required action fields, plan/application alignment, and finding traceability.
- `review_discipline_audit.py`: audits review-loop state-machine consistency,
  stop reasons, patch/gate agreement, and score regressions.
- `rubric_grounding_audit.py`: audits per-item rubric results so awarded
  points have grounding signals and total scores match item-point sums.
- `review_trajectory_audit.py`: checks review evolution, cursor, patch
  application, optimizer state, prompt contracts, and rubric grounding agree on
  iteration history and final score.
- `execution_grounding.py`: ingests optional execution traces and replay
  results as execution evidence.
- `execution_trace_validation.py`: validates supplied execution trace and
  replay-result provenance fields without running package code.
- `execution_replay_orchestrator.py`: builds plan-only tutorial replay jobs,
  audits explicitly supplied replay results, and records child-skill revision
  actions for replay failures or successful traces.
- `verification_claim_audit.py`: checks task_type verification labels against
  validated execution evidence, plan-only execution artifacts, and rendered
  child-skill Markdown.
- `lint_skill.py`: checks child skill install shape, frontmatter, reference
  links, empty references, and auxiliary-document clutter.
- `skill_package_audit.py`: checks the builder skill package itself uses the
  standard Codex skill top-level shape.
- `module_inventory_audit.py`: checks builder script modules have docstrings
  and are discoverable from the module inventory docs.
- `publish_gate.py`: blocks publish when lint, review, discovery, match
  quality, evidence, resource boundaries, review cursor, patch application,
  safety, tutorial reproduction planning, or verification boundaries fail;
  reuse can pass as a no-copy `reuse_ready` action without publishing a
  duplicate.

It writes machine-readable build artifacts and a lightweight child skill under
`child_skill/<method-name>/`.

By default the post-build retained output contains only `child_skill/`,
`iteration_versions/`, and `generation_process.md`. Set
`cleanup_process_files: false` to keep the full process artifact set for
debugging.

## Child Skill Shape

Generated child skills should look like:

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

Avoid heavy default scripts in child skills. Add scripts only when future
evidence proves a stable adapter is needed.

## Safety

Do not silently install dependencies, execute tutorials, patch upstream source,
download unbounded data, fabricate APIs, or claim verified execution without
execution evidence.

When remote-only rules apply, run tests, builds, lint, benchmarks, tutorial
reproduction, and project-code validation only on the specified remote host,
folder, environment, node, and CPU allocation.
