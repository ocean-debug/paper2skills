# Builder Architecture

Papert2Skills keeps the public child skill lightweight, but the builder itself
is split into focused stage modules so each phase can evolve independently.

## CLI

`scripts/papert2skills.py` is only the command-line dispatcher. It should stay
thin and delegate work to phase modules. Standalone audit commands, including
`audit-protocol-compliance`, recompute reports from saved artifacts without
executing package code.

## Pipeline

`scripts/build_pipeline.py` owns the end-to-end build order:

```text
request -> request audit -> request fingerprint -> builder runtime audit -> agent metadata audit -> public origin audit -> module inventory audit -> skill package audit -> request template audit -> discovery preflight -> source grounding -> source fetch -> source fetch boundary audit -> source index
  -> evidence cards -> source manifest -> tutorial catalog
  -> API grounding -> interface grounding -> key API coverage audit
  -> source parse report -> source parsing coverage -> source parsing audit -> source ingestion audit -> backend contract -> environment spec -> resource inventory -> task partition -> task partition decision log -> parameter catalog
  -> final discovery -> discovery audit -> discovery match audit
  -> routing -> task partition audit -> task conflict matrix -> routing fixture -> iterative review -> review evolution -> review evolution plot -> review iteration log -> review prompt contracts -> review prompt materials -> review cursor -> patch application -> review remediation audit -> review optimizer state -> review prompt suite audit -> patch safety audit -> patch operation contracts -> review discipline audit -> rubric grounding audit -> review trajectory audit -> evidence coverage -> optional execution trace handling
  -> execution trace validation -> evidence precedence -> eval plan -> execution plan -> environment install plan -> resource boundary audit -> tutorial reproduction plan -> contract traceability -> lineage graph -> acceptance suite
  -> eval splits -> eval result judge -> draft candidate -> child skill draft -> verification claim audit -> child metadata audit -> child package purity audit -> lint -> draft readiness -> output boundary audit -> skill update plan -> skill update audit -> forward test plan -> agent rollout harness -> agent rollout audit -> eval leakage audit -> agent rollout result judge -> E2E acceptance -> claim consistency audit -> biological claim boundary audit -> child reference coverage -> routing metadata audit -> source grounding audit -> workflow invariant audit -> requirement coverage -> completion evidence audit -> acceptance handoff
  -> protocol compliance audit -> grounding gate -> API surface audit -> artifact contracts -> artifact closure audit -> code-fence audit -> public safety audit -> phase state audit -> artifact validation -> publish gate
  -> candidate registry -> candidate selection audit -> candidate promotion audit -> release package -> final candidate audit -> candidate evolution audit -> quality report -> Codex publish adapter -> install readiness -> publish manifest -> publish manifest audit -> score report -> builder version audit -> release action audit -> architecture completeness audit -> completion audit -> build timeline -> build timeline audit
  -> run scorecard -> run manifest
```

## Stage Modules

- `request_model.py`: request defaults and validation.
- `request_audit.py`: normalized request field, source-support, numeric-bound,
  and execution-environment boundary audit.
- `request_template_audit.py`: build request template drift audit against
  request normalization and request-audit contracts.
- `request_fingerprint.py`: redacted request identity hashes, request key names,
  and sensitive field-path metadata for reproducible runs.
- `builder_runtime_audit.py`: static builder skill metadata, build request
  template, UI metadata, and CLI command surface audit.
- `builder_baseline_audit.py`: static audit that expected engineering baseline
  families are covered by concrete modules and public inventory docs.
- `agent_metadata_audit.py`: static alignment audit for `SKILL.md` trigger
  metadata and `agents/openai.yaml` UI metadata.
- `public_origin_audit.py`: static audit that README and builder skill text do
  not expose private origin markers, legacy labels, or machine-specific
  execution details.
- `builder_version_audit.py`: schema and builder version consistency audit for
  core release-facing artifacts.
- `discovery.py`: existing Codex child-skill discovery across standard child
  files.
- `discovery_audit.py`: reuse, update, or create decision audit with task
  coverage for matched skills.
- `discovery_match_audit.py`: field-level match strength, ambiguity,
  task_type coverage, and child-skill shape audit.
- `discovery_resolution_audit.py`: final duplicate-risk and target consistency
  audit across preflight Discovery, final Discovery, match audit, and update
  planning.
- `phase_state.py`: audit trail for phase status, inputs, outputs, and gates.
- `phase_state_audit.py`: phase ledger structure, completed-phase gate, YAML
  artifact contract, and output ownership audit.
- `source_fetch.py`: safe optional fetch/register of official sources.
- `source_grounding.py`: official source, tutorial, documentation, paper, and
  trace source cataloging.
- `source_grounding_audit.py`: evidence-priority, non-execution, task
  traceability, and rendered-reference audit for source grounding.
- `source_index.py`: compact non-executing source file index with Python AST
  symbol, signature, docstring, branch-value, and call hints.
- `evidence_cards.py`: concise evidence cards and claim hints.
- `evidence_coverage.py`: task-level evidence priority and claim-type coverage.
- `evidence_precedence.py`: accepted evidence resolution by source priority for
  each task claim.
- `evidence_claim_taxonomy_audit.py`: task-level claim taxonomy audit that
  blocks unsupported claim types, paper-only operational claims, and verified
  claims without execution evidence.
- `source_manifest.py`: compact provenance, fetch, indexing, and evidence
  coverage manifest.
- `tutorial_miner.py`: compact tutorial/example step order and API-call hints.
- `api_grounding.py`: API candidate extraction from parsed source records.
- `interface_inspector.py`: static Python AST interface inspection for
  signatures, defaults, docstrings, and branch parameter values.
- `key_api_coverage_audit.py`: exact grounding coverage audit for explicit
  build-request key APIs.
- `source_parser.py`: explicit source parsing strategy, parser capability
  matrix, counts, compact parsed samples, and limitations for auditability.
- `source_parsing_coverage.py`: source-kind parser coverage, fetch-gap, and
  parser-gap audit.
- `source_fetch_boundary_audit.py`: fetch opt-in, run-directory containment,
  and archive extraction safety audit before source parsing.
- `source_parsing_audit.py`: source parsing strategy, provenance, and
  non-execution boundary audit.
- `source_ingestion_audit.py`: source evidence id and count lineage audit
  across grounding, fetch/register, index, parse report, manifest, and evidence
  cards.
- `backend_contracts.py`: Python-first backend support and extension refusal
  contract.
- `backend_extension_audit.py`: backend support and reserved-extension audit
  for Python-first and R extension boundaries.
- `environment_miner.py`: static dependency, import, Python-version, and GPU
  hints.
- `environment_install_plan.py`: plan-only install strategy, approval boundary,
  dependency hints, and refusal conditions for optional execution grounding.
- `resource_inventory.py`: static model registry, checkpoint, external
  artifact, data, and model-loading API inventory without downloading
  resources.
- `resource_boundary_audit.py`: audit that resource access, license, token,
  missing-weight, and large-download risks are rendered into refusal and
  environment boundaries.
- `execution_plan.py`: plan-only execution grounding boundaries for each
  task_type and environment constraints.
- `tutorial_reproduction_plan.py`: plan-only tutorial replay queues, trace
  requirements, success criteria, and refusal conditions per task_type.
- `contract_traceability.py`: evidence-linked ledger for generated input,
  output, validation, and refusal contracts.
- `lineage_graph.py`: compact source-to-task-to-child-file provenance graph.
- `acceptance_suite.py`: static routing, contract, traceability, refusal,
  ambiguity, eval, tutorial-replay, and execution-boundary cases.
- `smoke_test_plan.py`: plan-only child-skill package-shape smoke scenarios
  and explicitly supplied smoke-result audit.
- `eval_splits.py`: stable train, selection, and test split construction from
  static eval, routing, and acceptance cases.
- `eval_result_judge.py`: result judging for explicitly supplied eval outcomes.
- `agent_rollout_harness.py`: plan-only agent rollout queue and leakage gate
  assembled from forward-test, routing, and eval artifacts.
- `eval_leakage_audit.py`: static train/selection/test split isolation and
  agent prompt leakage audit for forward-test and rollout artifacts.
- `external_result_contracts.py`: static schema and leakage-boundary audit for
  supplied eval, rollout, replay, and E2E result evidence.
- `agent_rollout_result_judge.py`: static judge for explicitly supplied agent
  rollout results.
- `e2e_acceptance.py`: plan-only real end-to-end acceptance scenario contract,
  result templates, and explicit E2E result audit.
- `smoke_test_plan.py`: plan-only smoke coverage for child-skill files,
  task_type routing, contracts, refusals, verification labels, and publish-plan
  agreement.
- `task_partition.py`: capability detection and `task_type` contract drafts.
- `task_partition_decision_log.py`: accepted, merged/deferred, and rejected
  task_type candidate decision log.
- `parameter_miner.py`: signature-derived parameter constraints attached to
  task contracts.
- `task_router.py`: explicit task-type route artifact.
- `task_partition_audit.py`: task_type granularity and tutorial-split
  anti-pattern audit.
- `task_conflict.py`: pairwise task ambiguity and selection rules.
- `routing_fixture.py`: static task_type select, refuse, unsupported, and
  ambiguity fixture cases.
- `eval_plan.py`: static acceptance, refusal, and API-review scenario planning.
- `execution_trace_validation.py`: supplied trace and replay-result metadata
  validation without tutorial execution.
- `verification_claim_audit.py`: rendered task_type verification claim audit
  against validated execution evidence and plan-only execution artifacts.
- `quality_report.py`: combined review, lint, validation, protocol,
  output-boundary, tutorial-replay, code-fence, public-safety, publish-gate,
  and task-contract scorecards.
- `draft_candidate.py`: single child-skill candidate summary and task risk notes.
- `child_metadata_audit.py`: generated child-skill frontmatter, Codex trigger,
  task_type mention, and one-child-skill shape audit.
- `child_package_purity_audit.py`: strict public child-skill file-set audit for
  the lightweight `SKILL.md` plus standard `references/` contract.
- `draft_readiness.py`: unresolved placeholder and template-value checks for
  generated child-skill Markdown.
- `output_boundary_audit.py`: output-directory, install-root isolation, and
  public child-package boundary checks.
- `skill_update_plan.py`: plan-only release guidance for Discovery reuse,
  update, or create decisions.
- `skill_update_audit.py`: non-destructive update/reuse audit for plan-only
  targets, manual merge actions, and standard child-file boundaries.
- `forward_test_plan.py`: plan-only prompts, leakage controls, and judge checks
  for independent child-skill forward tests, plus saved-plan validation.
- `claim_consistency_audit.py`: rendered child-skill claim consistency checks
  against task, evidence, backend, refusal, and verification artifacts.
- `biological_claim_boundary_audit.py`: rendered high-risk biological claim
  boundary audit for unsupported cross-modal molecular, pathway, or clinical
  claims.
- `child_reference_coverage.py`: checks that source parsing coverage,
  environment install boundaries, tutorial replay plans, evidence precedence,
  task conflicts, and task_type entries are rendered into the public child
  references.
- `routing_metadata_audit.py`: checks task_type router scope, rendered routing
  docs, refusal boundaries, and ambiguity fixtures.
- `workflow_invariant_audit.py`: product-shape invariant audit for one child
  skill, task_type coverage including tutorial reproduction planning, Codex
  target, and backend boundaries.
- `requirement_coverage.py`: first-principles requirement-to-artifact coverage
  matrix for final auditability.
- `completion_evidence_audit.py`: non-executing audit that separates static
  build completion from full real-package completion evidence.
- `acceptance_handoff.py`: packages external result templates into run-local
  YAML and Markdown handoff artifacts.
- `protocol_compliance_audit.py`: cross-stage protocol audit for plan-only,
  external-result, output-boundary, verification, and completion-evidence
  separation.
- `architecture_completeness_audit.py`: run-level check that the major
  workflow phase families and focused gate artifacts are present and passing.
- `build_timeline.py`: compact phase, review, and gate event timeline.
- `build_timeline_audit.py`: timeline event-id, phase/review count, and gate
  coverage integrity audit.
- `candidate_registry.py`: candidate version registry and gate status summary.
- `candidate_selection_audit.py`: active-candidate selection rationale and
  quality-signal audit before promotion.
- `candidate_promotion_audit.py`: active-candidate promotion audit before
  release packaging.
- `final_candidate_audit.py`: final consistency audit linking release package
  metadata to the selected and promoted candidate.
- `candidate_evolution_audit.py`: cross-artifact candidate identity and gate
  evolution audit from draft through final candidate records.
- `score_report.py`: run-level review, rubric, quality, publish, candidate,
  candidate evolution, adapter, install-readiness, and manifest-audit score
  summary.
- `release_packager.py`: action-aware release manifest and install plan without
  file copying.
- `codex_publish_adapter.py`: plan-only Codex create, update, or reuse publish
  adapter for release package actions.
- `install_readiness.py`: final child-skill file and copy-readiness checks for
  create/update, with reuse marked as not applicable.
- `publish_manifest_audit.py`: final publish manifest consistency check against
  release and reuse/update/create decisions.
- `release_action_audit.py`: final create/update/reuse release-action semantic
  audit across release, install, adapter, manifest, and candidate gates.
- `completion_audit.py`: final run-level semantic completion verdict across
  request, Discovery match quality, resource boundaries, requirement,
  architecture completeness, artifact, publish, candidate selection, candidate
  finalization, quality, score, release, install, manifest, and skill-update
  gates.
- `run_scorecard.py`: final human-readable Markdown scorecard summarizing the
  run verdict, protocol status, and blockers without overriding the
  machine-readable gates.
- `run_manifest.py`: final run-level provenance for generated artifacts and
  child-skill file hashes.
- `grounding_gate.py`: pre-publish API/interface grounding status for
  `task_type` entries.
- `agent_rollout_audit.py`: plan-only rollout scenario mapping, leakage-control,
  judge metadata separation, and count-consistency audit.
- `api_surface_audit.py`: rendered API-surface grounding audit for code-fence
  calls, inline API-like mentions, requested API names, and task surface gaps.
- `key_api_coverage_audit.py`: publish-blocking coverage audit for explicit key
  APIs named in the build request.
- `artifact_contracts.py`: machine-readable minimum fields and list/mapping
  types for generated artifacts.
- `artifact_closure_audit.py`: static audit that required artifacts have
  contracts, pre-publish artifacts are available, and the run write plan covers
  required artifacts.
- `skill_draft.py`: scientific-agent-skills style child skill rendering.
- `self_review.py`: overclaim, evidence, contract, refusal, and verification
  checks.
- `review_rubric.py`: rubric scoring for source grounding, API/interface
  grounding, task partition, contracts, refusals, validation, and verification
  labels.
- `patch_planner.py`: deterministic artifact patches for fixable review
  findings.
- `review_loop.py`: bounded draft, critic, patch-plan, revision, and gate
  iteration loop.
- `review_evolution.py`: compact score, patch, and gate trajectory summary for
  the review loop.
- `review_evolution_plot.py`: run-level SVG rendering of review score movement,
  blocking state, and patch state.
- `review_iteration_log.py`: run-level Markdown summary of review iteration
  scores, blockers, patch actions, and gate reasons.
- `review_prompt_contracts.py`: static state-role contracts for draft, critic,
  patch-plan, revision, and gate review states.
- `review_prompt_materials.py`: static prompt material for each review role,
  including allowed inputs, required outputs, and forbidden outputs.
- `review_prompt_suite_audit.py`: review duty coverage audit for grounding,
  task split, contracts, refusals, validation, verification, patch planning,
  and gate discipline.
- `review_cursor.py`: review-loop cursor, stop reason, resumability, and
  per-iteration state completeness.
- `patch_application.py`: planned and applied agent proposal patch-action audit.
- `review_remediation_audit.py`: review finding remediation accounting across
  patch actions, cleared findings, gate acceptance, and final blockers.
- `review_optimizer_state.py`: review iteration hashes, cache key, strict
  improvement policy, and rejected-edit buffer.
- `patch_safety_audit.py`: bounded agent patch action safety audit for allowed
  artifacts and non-execution boundaries.
- `patch_operation_contracts.py`: static agent patch operation contract audit for
  operation names, required fields, plan/application alignment, and
  same-iteration finding links.
- `review_discipline_audit.py`: review-loop state-machine discipline,
  stop-condition consistency, patch/gate agreement, and score-regression audit.
- `rubric_grounding_audit.py`: per-item rubric result and grounding-signal
  audit for awarded review points.
- `review_trajectory_audit.py`: cross-artifact integrity audit for review
  evolution, cursor, patch application, optimizer state, prompt contracts, and
  rubric grounding.
- `execution_grounding.py`: optional execution evidence ingestion and
  verification label handling.
- `execution_replay_orchestrator.py`: plan-only tutorial replay job queue,
  replay-result audit, and troubleshooting/verification revision action record.
- `lint_skill.py`: child skill install-shape lint for frontmatter, required
  references, linked references, empty references, and auxiliary-document
  clutter.
- `skill_package_audit.py`: static audit for the builder skill package
  top-level shape and required Codex skill metadata.
- `agent_metadata_audit.py`: static audit for builder skill trigger metadata,
  UI metadata, default prompt, and required builder concepts.
- `module_inventory_audit.py`: static audit that builder script modules have
  module docstrings and are documented in inventory docs.
- `artifact_validator.py`: pre-publish artifact contract, schema, and
  consistency checks, including tutorial reproduction plan coverage.
- `code_fence_audit.py`: generated Markdown audit for local paths and
  ungrounded code-fence API calls.
- `public_safety_audit.py`: generated public Markdown audit for credentials,
  private keys, contact identifiers, and long copied excerpts.
- `publish_gate.py`: final action-aware gate that combines lint, review,
  discovery, match quality, resource boundaries, tutorial reproduction
  planning, evidence, safety, and verification boundaries.
- `action_policy.py`: normalized create/update/reuse status expectations.
- `common.py`: shared IO and formatting helpers.
- `constants.py`: schema version, reference list, status labels, and heuristics.

## Boundaries

Build stages must not install packages, execute tutorials, or mark task types
as verified without explicit execution evidence. Execution-grounded
reproduction is a separate opt-in capability.

Remote source downloads are disabled unless `fetch_sources: true` is set in the
build request. Even when enabled, fetching is size-limited and source indexing
stores compact metadata, symbols, headings, and evidence summaries rather than
long excerpts.
