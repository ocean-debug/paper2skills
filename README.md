# Papert2Skills

Papert2Skills is a Codex-oriented skill builder for scientific algorithm
packages. It turns official source repositories, tutorials, documentation, and
papers into lightweight child skills that tell an agent how to use an algorithm
package reliably.

The core problem is not paper summarization. The problem is that agents often
do not know the operational boundary of a scientific package: which task it
supports, which inputs are valid, which metadata is required, which API path is
recommended, what outputs should exist, how results can be checked, and when to
refuse bad input.

Papert2Skills compiles that operational knowledge into one child skill per
algorithm package.

## Design

Papert2Skills is built around a few simple rules:

- Run Discovery before building, so an existing Codex child skill can be reused
  or updated instead of duplicated.
- Partition package capabilities, but keep one child skill per algorithm
  package.
- Represent each capability as a `task_type` inside that child skill.
- Put task-type routing guidance in `SKILL.md` and `references/task-types.md`.
- Keep generated child skills lightweight and evidence-grounded.

Generated child skills follow the lightweight
`scientific-agent-skills` style:

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

## Workflow

```text
Request Audit
  -> Request Fingerprint
  -> Builder Runtime Audit
  -> Agent Metadata Audit
  -> Public Origin Audit
  -> Module Inventory Audit
  -> Builder Baseline Audit
  -> Skill Package Audit
  -> Request Template Audit
  -> Discovery Preflight
  -> Source Grounding
  -> Source Fetch
  -> Source Fetch Boundary Audit
  -> Source Index
  -> Evidence Cards
  -> Source Manifest
  -> Tutorial Catalog
  -> API Grounding
  -> Interface Grounding
  -> Key API Coverage Audit
  -> Source Parse Report
  -> Source Parsing Coverage
  -> Source Parsing Audit
  -> Source Ingestion Audit
  -> Backend Contract
  -> Environment Spec
  -> Resource Inventory
  -> Task Partition
  -> Task Partition Decision Log
  -> Parameter Catalog
  -> Final Discovery
  -> Discovery Audit
  -> Discovery Match Audit
  -> Task-Type Routing
  -> Task Partition Audit
  -> Task Conflict Matrix
  -> Routing Fixture
  -> SkillOpt-Style Self Review
  -> Review Evolution
  -> Review Evolution Plot
  -> Review Iteration Log
  -> Review Prompt Contracts
  -> Review Prompt Materials
  -> Review Cursor
  -> Patch Application
  -> Review Remediation Audit
  -> Review Optimizer State
  -> Review Prompt Suite Audit
  -> Patch Safety Audit
  -> Patch Operation Contracts
  -> Review Discipline Audit
  -> Rubric Grounding Audit
  -> Review Trajectory Audit
  -> Evidence Coverage
  -> Optional Execution Grounding
  -> Execution Trace Validation
  -> Evidence Precedence
  -> Eval Plan
  -> Execution Plan
  -> Environment Install Plan
  -> Resource Boundary Audit
  -> Tutorial Reproduction Plan
  -> Contract Traceability
  -> Lineage Graph
  -> Acceptance Suite
  -> Eval Splits
  -> Eval Result Judge
  -> Draft Candidate
  -> Skill Draft
  -> Verification Claim Audit
  -> Child Metadata Audit
  -> Child Package Purity Audit
  -> Lint
  -> Draft Readiness
  -> Output Boundary Audit
  -> Skill Update Plan
  -> Skill Update Audit
  -> Forward Test Plan
  -> Agent Rollout Harness
  -> Agent Rollout Audit
  -> Eval Leakage Audit
  -> Agent Rollout Result Judge
  -> E2E Acceptance
  -> Claim Consistency Audit
  -> Child Reference Coverage
  -> Routing Metadata Audit
  -> Source Grounding Audit
  -> Workflow Invariant Audit
  -> Requirement Coverage
  -> Completion Evidence Audit
  -> Acceptance Handoff
  -> Protocol Compliance Audit
  -> Grounding Gate
  -> API Surface Audit
  -> Artifact Contracts
  -> Artifact Closure Audit
  -> Code-Fence Audit
  -> Public Safety Audit
  -> Phase State Audit
  -> Artifact Validation
  -> Publish Gate
  -> Candidate Registry
  -> Candidate Selection Audit
  -> Candidate Promotion Audit
  -> Release Package
  -> Final Candidate Audit
  -> Candidate Evolution Audit
  -> Quality Report
  -> Codex Publish Adapter
  -> Install Readiness
  -> Publish Manifest
  -> Publish Manifest Audit
  -> Score Report
  -> Builder Version Audit
  -> Release Action Audit
  -> Architecture Completeness Audit
  -> Completion Audit
  -> Build Timeline
  -> Run Scorecard
  -> Run Manifest
```

Evidence priority:

```text
execution trace > official tutorials/docs > source code/API > paper
```

Execution grounding is explicit. By default, Papert2Skills creates a
`source_grounded` child skill and does not claim verified execution. When
execution evidence is supplied, only the task types with successful validated
evidence may be marked `verified`. Verification claim audit checks the rendered
child skill after drafting so `execution_verified`, `source_grounded`, and
`execution_failed` labels match validated evidence metadata and visible
Markdown.

Tutorial reproduction planning is also explicit and plan-only. It builds a
per-`task_type` replay queue from mined tutorial/example steps and records the
environment fields, trace requirements, success criteria, and refusal conditions
that must be satisfied before runtime verification can be attempted.

Resource inventory is static and non-downloading. It detects model registry
IDs, checkpoint files, external artifact URLs, data artifacts, and model-loading
APIs so generated skills can refuse or ask for confirmation when permissions,
licenses, tokens, missing weights, or large downloads are unresolved.

Artifact contracts are generated as `artifact_contracts.yaml` before
pre-publish validation. They define the minimum stable fields and list/mapping
types for each build artifact. `artifact_closure_audit.yaml` checks that
required artifacts have contracts, pre-publish artifacts are available, and the
run write plan covers the required artifact set. Semantic consistency checks
remain in `artifact_validation.yaml`, `output_boundary_audit.yaml`,
`forward_test_plan.yaml`, `code_fence_audit.yaml`, `public_safety_audit.yaml`,
`publish_gate.yaml`, `quality_report.yaml`, `completion_audit.yaml`, and
`run_scorecard.yaml`.

Module inventory audit checks that builder script modules have docstrings and
are discoverable from the public module inventories before publishing. This
keeps the engineering surface reviewable as the builder grows.
Skill package audit checks that the builder itself remains a standard Codex
skill package with required files, allowed top-level directories, and no
auxiliary docs or cache files inside the skill folder.
Request template audit checks that `templates/build_request.yaml` stays aligned
with request normalization, request audit constants, execution-environment
fields, and builder runtime required template fields.

Child reference coverage checks that source parsing coverage, environment
install boundaries, tutorial replay plans, evidence precedence, task conflicts,
parser capability matrix, and task_type entries are actually rendered into the
public child references.
Source grounding audit then checks evidence priority, static parsing
boundaries, task-level evidence references, contract traceability, and rendered
evidence sections as one publish gate.

Output boundary audit checks that build artifacts stay in the run output
directory, the public child skill stays under `child_skill/`, and the run
output is not placed inside a likely Codex skill install root.

Task partition audit checks that capability partitioning produces `task_type`
entries inside one child skill, and flags tutorial/demo/notebook-shaped splits.
Task partition decision logging records accepted task_type candidates, merged
or deferred candidates, and rejected tutorial-shaped split candidates.

API surface audit checks rendered code fences, inline API-like mentions, and
request-provided API names against parsed API/interface grounding before
publish.

Child metadata audit checks that the generated `SKILL.md` frontmatter is a
valid Codex trigger, mentions `task_type` selection, input-output contracts,
and refusal behavior, and does not drift into multiple child skills or separate
external routing-selector shapes.

Forward test planning creates independent, plan-only prompts for checking how a
fresh agent uses the generated child skill. The prompt sent to the test agent
must not include expected behavior, review findings, or build-time conclusions.
Agent rollout harness turns those scenarios into a plan-only queue with
judge-side metadata, split labels, leakage controls, and task coverage checks.
Agent rollout audit independently checks scenario-to-rollout mapping,
judge-only metadata separation, plan-only status, and rollout id uniqueness.
Routing metadata audit checks that the task_type router is scoped inside one
child skill, rendered into `SKILL.md` and `references/task-types.md`, and backed
by refusal and ambiguity fixture cases.

Discovery match audit checks field-level match evidence, task_type coverage,
existing child-skill shape, and ambiguous high-confidence matches before a
reuse or update decision can affect publishing. Skill update planning turns
Discovery's `reuse | update | create` decision into a plan-only release action.
When an existing child skill covers the same package but misses inferred
`task_type` entries, the builder records a manual merge plan instead of
silently publishing a duplicate skill.
Skill update audit checks that create, update, and reuse plans remain
non-destructive, plan-only, and limited to standard child-skill files.
`reuse` becomes `reuse_existing` and must not copy a generated duplicate;
`update` becomes `update_existing` and requires a target existing skill path;
`create` becomes `create_new` and may install the generated child skill after
publish and install-readiness gates pass.

Release gates are action-aware. `create_new` and `update_existing` require a
`publishable` generated candidate and install readiness. `reuse_existing`
requires a `reuse_ready` no-copy decision and marks generated-candidate install
readiness as `not_applicable`.

Codex publish adapter turns the release decision into a plan-only Codex skill
installation or merge action. It never copies files itself; it records what
would be copied or merged, which files are required, and when reuse must avoid
publishing a duplicate generated child skill.

Completion audit aggregates the final semantic gates into one verdict. It
requires builder runtime audit, builder version audit, request audit, phase
state audit, Discovery match audit, requirement coverage, completion evidence
audit, architecture completeness, artifact validation, artifact closure audit,
publish gate, candidate selection
audit, candidate promotion audit, final candidate audit, candidate evolution audit, quality report, release package,
release action audit, install readiness, publish manifest audit, and skill
update planning to agree before the run is considered complete.
Completion evidence audit is separate from publishability: it records whether
the run can claim only static build completion or full real-package completion
from supplied rollout, E2E, and execution evidence.
Acceptance handoff turns the generated result templates into a run-local YAML
and Markdown checklist for external validation. Filled results must still be
copied back into the build request and pass the static result audits before
they count as evidence.
Score report summarizes review trajectory, rubric grounding, quality blockers,
publish blockers, candidate gate status, candidate evolution status, Codex
publish adapter status, install readiness, and publish manifest audit status as
a run artifact after publish manifest audit.

The iterative review loop is agent-driven. Python records findings, rubric
scores, prompt contracts, cursor state, proposal templates, strict improvement
state, and bounded apply results; Codex or another agent writes
`agent_skillopt_proposals` and reruns the build. When a run stops with
`review_summary.status: needs_agent`, use `skillopt-next-step --run <run_dir>`
to retrieve the next proposal template.
`review_prompt_contracts.yaml` records required state roles, fields, allowed
actions, and forbidden actions for draft, critic, patch-plan, revision, and
gate states. `review_prompt_materials.yaml` records static prompt material,
allowed inputs, required outputs, and forbidden outputs for each role.
`review_prompt_suite_audit.yaml` records required review duty
coverage across grounding, task split, contracts, refusals, validation,
verification, patch planning, and gate discipline. `review_cursor.yaml` records the current review state and
resumability; `patch_application.yaml` records planned and applied agent
proposal actions; `review_optimizer_state.yaml` records
state hashes, cache key, strict improvement policy, and rejected edits;
`patch_safety_audit.yaml` blocks patch records that mention paths, commands,
installs, network actions, or artifacts outside the allowed agent-edit set.
`patch_operation_contracts.yaml` checks operation names, required action
fields, plan/application alignment, and same-iteration finding traceability.
`review_discipline_audit.yaml` checks state-machine consistency, stop reasons,
and score regressions so the review loop is auditable.
`rubric_grounding_audit.yaml` checks that every awarded rubric point has a
recorded grounding signal. `review_iteration_log.md` gives a concise
per-iteration audit trail for humans. `review_trajectory_audit.yaml` checks that
review evolution, cursor, patch application, optimizer state, prompt contracts,
and rubric grounding agree on iteration history and final score.

## Install As A Codex Skill

Copy the top-level skill folder into a Codex skills directory:

```bash
cp -R paper2skills ~/.codex/skills/paper2skills
```

Then invoke it with `$paper2skills`.

## Build Request

Start from `paper2skills/templates/build_request.yaml`:

```yaml
schema_version: "1.0"
package_name: "example-package"
method_name: "Example Package"
repo_url: "https://github.com/owner/example-package"
tutorial_links:
  - "https://example.org/tutorial"
doc_links:
  - "https://example.org/docs"
paper_links: []
paper_dois: []
api_names: []
source_material_paths: []
target_agent: "codex"
language_backend: "python"
execution_grounded: false
execution_traces: []
execution_replay_results: []
eval_results: []
agent_rollout_results: []
agent_skillopt_proposals: []
smoke_test_results: []
require_smoke_test: false
e2e_acceptance_results: []
require_e2e_acceptance: false
execution_environment:
  mode: "unspecified"
  host: null
  working_directory: null
  environment_name: null
  node: null
  cores: null
  remote_only: false
  notes: []
existing_skills_dirs: []
output_dir: "./runs/example-package"
requested_task_types: []
fetch_sources: false
max_fetch_bytes: 5000000
max_index_files: 500
max_index_bytes: 250000
review_iterations: 3
review_min_score_ratio: 0.875
```

`agent_rollout_results` is optional external evidence. Each item should point
to a planned rollout by `rollout_id`, `scenario_id`, or `source_case_id`, then
provide `status` or observed fields such as `observed_decision`,
`observed_task_type`, and `observed_reason_key`. Use
`satisfied_judge_checks` for checks the external run covered (`all`, `1`,
`check:1`, or `judge_check:1` are accepted), and `failed_judge_checks` when a
check failed. Empty results are recorded as
`not_run`, not as an agent validation pass. Incomplete supplied results fail
closed and must be fixed before they can count as validation evidence.

`execution_replay_results` is optional external evidence for tutorial replay
jobs. Successful entries must include `replay_id`, `task_type`, `trace_ref`,
environment, inputs, outputs, validation checks, package versions, and command,
notebook, or script provenance. Failed entries should include `failure_reason`;
they update troubleshooting guidance and do not create verified claims.
Successful replay results are treated as supplied execution evidence, so users
do not need to duplicate the same record in `execution_traces`.

`e2e_acceptance_results` is optional external evidence for real end-to-end
acceptance scenarios. The builder always emits `e2e_acceptance.yaml` as a
plan-only scenario contract with one result template per scenario. Use those
templates to record reviewed artifacts, observed outputs, completed checks,
failure reasons, and source run identifiers; only supplied results can change
the E2E verdict from `not_run` to `passed`, `partial`, or `failed`. Set
`require_e2e_acceptance: true` when publish should be blocked until all
required E2E scenarios have passing supplied results.

The CLI entrypoint is thin; engineering logic is split by build phase:

```bash
python paper2skills/scripts/papert2skills.py build \
  --request paper2skills/templates/build_request.yaml \
  --out runs/example-package
```

Additional read-only checks for generated outputs and the builder skill package:

```bash
python paper2skills/scripts/papert2skills.py validate-run --run runs/example-package
python paper2skills/scripts/papert2skills.py audit-child \
  --skill runs/example-package/child_skill/example-package \
  --api-grounding runs/example-package/api_grounding.yaml \
  --interface-grounding runs/example-package/interface_grounding.yaml
python paper2skills/scripts/papert2skills.py audit-public-child \
  --skill runs/example-package/child_skill/example-package
python paper2skills/scripts/papert2skills.py audit-child-package-purity \
  --skill runs/example-package/child_skill/example-package \
  --skill-spec runs/example-package/skill_spec.yaml
python paper2skills/scripts/papert2skills.py audit-biological-claims \
  --skill runs/example-package/child_skill/example-package \
  --task-catalog runs/example-package/task_catalog.yaml \
  --source-grounding runs/example-package/source_grounding.yaml \
  --evidence-cards runs/example-package/evidence_cards.yaml
python paper2skills/scripts/papert2skills.py validate-forward-test-plan \
  --plan runs/example-package/forward_test_plan.yaml
python paper2skills/scripts/papert2skills.py audit-discovery-resolution \
  --request runs/example-package/request.yaml \
  --discovery-preflight runs/example-package/discovery_preflight.yaml \
  --discovery-report runs/example-package/discovery_report.yaml \
  --discovery-match-audit runs/example-package/discovery_match_audit.yaml \
  --skill-update-plan runs/example-package/skill_update_plan.yaml
python paper2skills/scripts/papert2skills.py audit-eval-leakage \
  --request runs/example-package/request.yaml \
  --eval-splits runs/example-package/eval_splits.yaml \
  --forward-test-plan runs/example-package/forward_test_plan.yaml \
  --agent-rollout-harness runs/example-package/agent_rollout_harness.yaml \
  --eval-result-judge runs/example-package/eval_result_judge.yaml
python paper2skills/scripts/papert2skills.py audit-external-results \
  --request runs/example-package/request.yaml
python paper2skills/scripts/papert2skills.py audit-evidence-claim-taxonomy \
  --request runs/example-package/request.yaml \
  --task-catalog runs/example-package/task_catalog.yaml \
  --evidence-cards runs/example-package/evidence_cards.yaml \
  --source-grounding runs/example-package/source_grounding.yaml \
  --evidence-precedence runs/example-package/evidence_precedence.yaml \
  --execution-trace-validation runs/example-package/execution_trace_validation.yaml
python paper2skills/scripts/papert2skills.py audit-execution-replay \
  --request runs/example-package/request.yaml \
  --tutorial-reproduction-plan runs/example-package/tutorial_reproduction_plan.yaml \
  --execution-plan runs/example-package/execution_plan.yaml \
  --environment-install-plan runs/example-package/environment_install_plan.yaml
python paper2skills/scripts/papert2skills.py audit-e2e-acceptance \
  --request runs/example-package/request.yaml \
  --task-catalog runs/example-package/task_catalog.yaml \
  --acceptance-suite runs/example-package/acceptance_suite.yaml \
  --eval-splits runs/example-package/eval_splits.yaml \
  --forward-test-plan runs/example-package/forward_test_plan.yaml \
  --agent-rollout-harness runs/example-package/agent_rollout_harness.yaml \
  --agent-rollout-result-judge runs/example-package/agent_rollout_result_judge.yaml \
  --execution-replay-orchestrator runs/example-package/execution_replay_orchestrator.yaml \
  --verification-claim-audit runs/example-package/verification_claim_audit.yaml
python paper2skills/scripts/papert2skills.py audit-smoke-test-plan \
  --request runs/example-package/request.yaml \
  --task-catalog runs/example-package/task_catalog.yaml
python paper2skills/scripts/papert2skills.py audit-completion-evidence \
  --request runs/example-package/request.yaml \
  --requirement-coverage runs/example-package/requirement_coverage.yaml \
  --agent-rollout-result-judge runs/example-package/agent_rollout_result_judge.yaml \
  --e2e-acceptance runs/example-package/e2e_acceptance.yaml \
  --execution-trace-validation runs/example-package/execution_trace_validation.yaml \
  --execution-replay-orchestrator runs/example-package/execution_replay_orchestrator.yaml
python paper2skills/scripts/papert2skills.py build-acceptance-handoff \
  --request runs/example-package/request.yaml \
  --e2e-acceptance runs/example-package/e2e_acceptance.yaml \
  --agent-rollout-harness runs/example-package/agent_rollout_harness.yaml \
  --execution-replay-orchestrator runs/example-package/execution_replay_orchestrator.yaml \
  --completion-evidence-audit runs/example-package/completion_evidence_audit.yaml
python paper2skills/scripts/papert2skills.py judge-agent-rollout-results \
  --request runs/example-package/request.yaml \
  --agent-rollout-harness runs/example-package/agent_rollout_harness.yaml \
  --eval-leakage-audit runs/example-package/eval_leakage_audit.yaml
python paper2skills/scripts/papert2skills.py audit-protocol-compliance --run runs/example-package
python paper2skills/scripts/papert2skills.py audit-build-timeline --run runs/example-package
python paper2skills/scripts/papert2skills.py skillopt-next-step --run runs/example-package
python paper2skills/scripts/papert2skills.py verify-run-manifest --run runs/example-package
python paper2skills/scripts/papert2skills.py audit-agent-metadata --skill paper2skills
python paper2skills/scripts/papert2skills.py audit-public-origin \
  --repo-root . \
  --skill paper2skills
python paper2skills/scripts/papert2skills.py audit-skill-package --skill paper2skills
python paper2skills/scripts/papert2skills.py audit-module-inventory --skill paper2skills
python paper2skills/scripts/papert2skills.py audit-builder-baseline --skill paper2skills
```

```text
paper2skills/scripts/
  papert2skills.py          # CLI dispatcher
  action_policy.py          # normalized create/update/reuse status policy
  agent_rollout_audit.py    # rollout scenario mapping and leakage audit
  agent_rollout_harness.py  # plan-only agent rollout queue and leakage gate
  agent_rollout_result_judge.py # explicit rollout-result judge
  e2e_acceptance.py       # plan-only E2E scenarios, result templates, and result audit
  smoke_test_plan.py      # plan-only child-skill package-shape smoke scenarios
  completion_evidence_audit.py # evidence-supported completion-claim audit
  acceptance_handoff.py   # external validation handoff templates
  protocol_compliance_audit.py # cross-stage protocol boundary audit
  agent_metadata_audit.py   # builder SKILL.md and agents/openai.yaml alignment audit
  build_pipeline.py         # end-to-end orchestration
  builder_baseline_audit.py # engineering baseline family coverage audit
  builder_runtime_audit.py  # static builder skill metadata, template, and CLI audit
  builder_version_audit.py  # schema and builder version consistency audit
  public_origin_audit.py    # public file leak audit for origin and machine details
  request_model.py          # request defaults and validation
  request_audit.py          # normalized build request contract and boundary audit
  request_template_audit.py # build request template and request-contract drift audit
  request_fingerprint.py    # redacted request identity hashes for reproducible runs
  discovery.py              # existing Codex child skill discovery
  discovery_audit.py        # reuse/update/create decision audit
  discovery_match_audit.py  # field-level match strength and shape audit
  discovery_resolution_audit.py # final duplicate-risk and target consistency audit
  phase_state.py            # phase-state artifact for auditability
  phase_state_audit.py      # phase ledger structure and output ownership audit
  source_fetch.py           # safe optional fetch/register of official sources
  source_fetch_boundary_audit.py # fetch opt-in, run-directory, and archive safety audit
  source_grounding.py       # official evidence catalog
  source_grounding_audit.py # source priority and traceability gate
  source_index.py           # compact non-executing file index and AST hints
  source_parser.py          # source parsing strategy, capability matrix, and parse summary
  source_parsing_coverage.py # parser coverage and source-kind gap audit
  source_parsing_audit.py   # parser strategy, provenance, and non-execution audit
  source_ingestion_audit.py # source id and count lineage audit
  evidence_cards.py         # evidence cards and claim hints
  evidence_coverage.py      # task_type evidence priority and claim coverage
  evidence_precedence.py    # source-priority resolution for task claims
  source_manifest.py        # source provenance and coverage summary
  tutorial_miner.py         # compact tutorial/example step mining
  api_grounding.py          # parsed API candidate grounding
  interface_inspector.py    # static signatures, docstrings, and branch hints
  key_api_coverage_audit.py # explicit request API coverage audit
  backend_contracts.py      # Python-first backend and extension boundaries
  backend_extension_audit.py # backend support and reserved-extension audit
  environment_miner.py      # dependency/import/GPU environment hints
  environment_install_plan.py # plan-only environment installation boundary
  resource_inventory.py     # static model/checkpoint/data resource inventory
  resource_boundary_audit.py # resource refusal and rendering boundary audit
  execution_plan.py         # plan-only execution grounding boundary
  tutorial_reproduction_plan.py # plan-only tutorial replay queue and trace requirements
  contract_traceability.py  # evidence ledger for generated contracts
  evidence_claim_taxonomy_audit.py # claim-type evidence and priority audit
  lineage_graph.py          # source-to-task-to-child-file provenance graph
  acceptance_suite.py       # static routing/refusal/contract/traceability test cases
  smoke_test_plan.py        # static child-skill smoke scenarios and supplied-result audit
  eval_splits.py            # train/selection/test split builder for static cases
  eval_result_judge.py      # explicit eval-result judge for supplied outcomes
  eval_leakage_audit.py     # split isolation and prompt leakage hard gate
  verification_claim_audit.py # rendered verification claims vs execution evidence gate
  task_partition.py         # capability -> task_type partition
  task_partition_decision_log.py # accepted/rejected task_type decision log
  parameter_miner.py        # static parameter constraints from interfaces
  task_router.py            # task_type routing artifact
  task_partition_audit.py   # task_type granularity and tutorial-split audit
  task_conflict.py          # task_type ambiguity and selection matrix
  routing_fixture.py        # static task_type routing fixture cases
  eval_plan.py              # static acceptance/refusal/API review scenarios
  external_result_contracts.py # supplied eval/rollout/replay/E2E result schema audit
  quality_report.py         # combined quality/protocol scorecards and blockers
  draft_candidate.py        # one-skill draft candidate summary
  child_metadata_audit.py   # Codex trigger and one-child-skill metadata audit
  child_package_purity_audit.py # strict public child-skill file-set audit
  draft_readiness.py        # unresolved marker and template-value gate
  output_boundary_audit.py  # generated-output, install-root, and public child-skill boundary gate
  skill_update_plan.py      # plan-only reuse/update/create release guidance
  skill_update_audit.py     # non-destructive update/reuse safety audit
  forward_test_plan.py      # plan-only independent child-skill rehearsal cases and validation
  claim_consistency_audit.py # rendered claim-to-artifact consistency audit
  child_reference_coverage.py # required artifact-to-reference coverage audit
  routing_metadata_audit.py # task_type router rendering and refusal audit
  workflow_invariant_audit.py # product-shape invariant audit
  requirement_coverage.py  # first-principles requirement-to-artifact matrix
  architecture_completeness_audit.py # run-level architecture coverage gate
  build_timeline.py         # phase, review, and gate event timeline
  build_timeline_audit.py   # timeline event integrity audit
  candidate_registry.py     # candidate version and gate status registry
  candidate_selection_audit.py # active candidate selection rationale gate
  candidate_promotion_audit.py # active candidate promotion gate
  final_candidate_audit.py  # release-to-selected-candidate consistency gate
  candidate_evolution_audit.py # candidate identity and gate evolution audit
  score_report.py          # review, quality, publish, candidate, and evolution score summary
  release_packager.py       # release package manifest and install plan
  release_action_audit.py   # final create/update/reuse action consistency audit
  codex_publish_adapter.py  # plan-only Codex publish action adapter
  install_readiness.py      # final public child-skill copy readiness check
  completion_audit.py       # final semantic completion verdict
  run_scorecard.py          # one-page Markdown run and protocol scorecard renderer
  run_manifest.py           # final file hashes and run-level provenance
  grounding_gate.py         # task API/interface grounding gate
  artifact_contracts.py     # machine-readable artifact field contracts
  artifact_closure_audit.py # required artifact, contract, and write-plan closure audit
  artifact_validator.py     # pre-publish artifact contract and consistency checks
  api_surface_audit.py      # rendered API-surface grounding audit
  code_fence_audit.py       # machine-path and ungrounded API audit
  public_safety_audit.py    # credential and long-excerpt release safety audit
  biological_claim_boundary_audit.py # high-risk biological claim boundary audit
  skill_draft.py            # lightweight child skill rendering
  self_review.py            # checklist review checks
  review_rubric.py          # rubric scoring gate
  patch_planner.py          # deterministic artifact patch planner
  review_loop.py            # draft/critic/patch/revision/gate iteration loop
  review_evolution.py       # review score and patch trajectory summary
  review_evolution_plot.py  # run-level SVG review trajectory renderer
  review_iteration_log.py   # run-level Markdown review iteration log
  review_prompt_contracts.py # static review state-role contracts
  review_prompt_materials.py # static review prompt materials
  review_prompt_suite_audit.py # required review duty coverage audit
  review_cursor.py          # review-loop cursor and resumability artifact
  patch_application.py      # planned/applied patch-action audit
  review_remediation_audit.py # review finding remediation accounting
  review_optimizer_state.py # review state hashes, cache key, and rejected edits
  patch_safety_audit.py     # bounded agent patch action safety audit
  patch_operation_contracts.py # patch operation names, fields, and finding links
  review_discipline_audit.py # review loop state-machine discipline audit
  rubric_grounding_audit.py # per-item rubric grounding audit
  review_trajectory_audit.py # cross-artifact review trajectory integrity audit
  execution_grounding.py    # optional execution evidence ingestion and verification labels
  execution_trace_validation.py # supplied trace/replay-result provenance gate
  execution_replay_orchestrator.py # plan-only replay jobs and result audit
  lint_skill.py             # Codex child-skill install-shape lint and publish manifest
  skill_package_audit.py    # Codex builder skill package shape audit
  module_inventory_audit.py # builder script inventory documentation audit
  publish_manifest_audit.py # release/update/create manifest consistency audit
  publish_gate.py           # final publishability gate
  common.py                 # IO, YAML/JSON, path, table helpers
  constants.py              # schema and heuristic constants
```

It writes:

```text
request.yaml
phase_state.yaml
phase_state_audit.yaml
builder_runtime_audit.yaml
agent_metadata_audit.yaml
public_origin_audit.yaml
module_inventory_audit.yaml
builder_baseline_audit.yaml
skill_package_audit.yaml
request_template_audit.yaml
builder_version_audit.yaml
request_audit.yaml
request_fingerprint.yaml
discovery_preflight.yaml
discovery_report.yaml
discovery_audit.yaml
discovery_match_audit.yaml
discovery_resolution_audit.yaml
source_grounding.yaml
source_fetch_report.yaml
source_fetch_boundary_audit.yaml
source_index.yaml
source_parse_report.yaml
source_parsing_coverage.yaml
source_parsing_audit.yaml
source_ingestion_audit.yaml
evidence_cards.yaml
evidence_coverage.yaml
evidence_precedence.yaml
source_manifest.yaml
tutorial_catalog.yaml
api_grounding.yaml
interface_grounding.yaml
backend_contract.yaml
backend_extension_audit.yaml
environment_spec.yaml
resource_inventory.yaml
parameter_catalog.yaml
task_catalog.yaml
task_partition_decision_log.yaml
task_type_router.yaml
task_partition_audit.yaml
task_conflict_matrix.yaml
routing_fixture.yaml
eval_plan.yaml
execution_trace_validation.yaml
execution_replay_orchestrator.yaml
verification_claim_audit.yaml
evidence_claim_taxonomy_audit.yaml
execution_plan.yaml
environment_install_plan.yaml
resource_boundary_audit.yaml
tutorial_reproduction_plan.yaml
contract_traceability.yaml
lineage_graph.yaml
acceptance_suite.yaml
eval_splits.yaml
eval_result_judge.yaml
eval_leakage_audit.yaml
external_result_contracts.yaml
agent_rollout_result_judge.yaml
e2e_acceptance.yaml
draft_candidates.yaml
candidate_registry.yaml
candidate_selection_audit.yaml
candidate_promotion_audit.yaml
release_package.yaml
final_candidate_audit.yaml
candidate_evolution_audit.yaml
codex_publish_adapter.yaml
install_readiness.yaml
skill_spec.yaml
review_log.jsonl
review_iterations.jsonl
review_summary.yaml
review_evolution.yaml
review_evolution_plot.yaml
review_evolution_plot.svg
review_iteration_log.yaml
review_iteration_log.md
review_prompt_contracts.yaml
review_prompt_materials.yaml
review_prompt_suite_audit.yaml
review_cursor.yaml
patch_application.yaml
review_optimizer_state.yaml
patch_safety_audit.yaml
patch_operation_contracts.yaml
review_discipline_audit.yaml
rubric_grounding_audit.yaml
review_trajectory_audit.yaml
skill_lint_report.yaml
child_metadata_audit.yaml
child_package_purity_audit.yaml
draft_readiness.yaml
output_boundary_audit.yaml
skill_update_plan.yaml
skill_update_audit.yaml
forward_test_plan.yaml
agent_rollout_harness.yaml
agent_rollout_audit.yaml
claim_consistency_audit.yaml
biological_claim_boundary_audit.yaml
child_reference_coverage.yaml
routing_metadata_audit.yaml
source_grounding_audit.yaml
workflow_invariant_audit.yaml
requirement_coverage.yaml
completion_evidence_audit.yaml
acceptance_handoff.yaml
protocol_compliance_audit.yaml
acceptance_handoff.md
architecture_completeness_audit.yaml
grounding_gate.yaml
api_surface_audit.yaml
key_api_coverage_audit.yaml
artifact_contracts.yaml
artifact_closure_audit.yaml
code_fence_audit.yaml
public_safety_audit.yaml
artifact_validation.yaml
publish_gate.yaml
quality_report.yaml
score_report.yaml
publish_manifest.yaml
publish_manifest_audit.yaml
release_action_audit.yaml
completion_audit.yaml
build_timeline.yaml
build_timeline_audit.yaml
run_scorecard.yaml
run_scorecard.md
run_manifest.yaml
child_skill/<method-name>/
```

## Safety And Testing

Papert2Skills must not silently install dependencies, patch upstream source,
download unbounded data, fabricate APIs, or mark unexecuted paths as verified.

Testing and execution should follow the user's project environment and explicit
constraints. If a user requires remote-only validation, run tests, builds,
lint checks, benchmarks, tutorial reproduction, and project-code validation only
on the specified remote host, folder, environment, node, and CPU allocation. If
no such constraint exists, use the normal development environment for the
project and keep execution-grounded reproduction opt-in.
