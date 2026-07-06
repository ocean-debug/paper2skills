# Workflow

paper2skills compiles official evidence into one lightweight child skill per
scientific algorithm package.

## Phases

```text
Request Audit
Request Fingerprint
Builder Runtime Audit
Agent Metadata Audit
Public Origin Audit
Module Inventory Audit
Builder Baseline Audit
Skill Package Audit
Request Template Audit
Discovery Preflight
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
  -> Operational Recipes
  -> Final Discovery
  -> Discovery Audit
  -> Discovery Match Audit
  -> Task-Type Routing
  -> Task Partition Audit
  -> Task Conflict Matrix
  -> Routing Fixture
  -> Iterative Self Review
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
  -> Claim Consistency Audit
  -> Biological Claim Boundary Audit
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

## Discovery

Builder runtime audit is a static preflight over the paper2skills skill
package itself. It checks the required skill files, UI metadata, build request
template fields, execution-environment placeholders, and CLI command surface
without importing modules or running commands.

Agent metadata audit checks that `SKILL.md` trigger metadata and
`agents/openai.yaml` UI metadata agree on the installable skill name, display
name, default prompt, and source-grounded task_type contract/refusal/evidence
scope.

Public origin audit checks README and builder skill package text for private
origin markers, legacy labels, and machine-specific execution details so public
project files remain generic and product-facing.

Module inventory audit checks that every builder script module has a module
docstring and is discoverable from the public module inventory docs. It is a
static maintainability gate for the builder itself.

Builder baseline audit groups the builder into expected engineering families:
request/CLI, Discovery/update, source ingestion, interface/environment,
task routing, child drafting, paper2skills review-loop patching, candidate release,
execution boundaries, rollout/evaluation, publish/manifest, and
timeline/protocol. Each family must map to concrete documented modules.

Skill package audit checks the builder's Codex skill package shape: required
files, allowed top-level directories, frontmatter fields, and absence of
auxiliary docs or cache files inside the skill folder.

Request template audit checks that `templates/build_request.yaml` stays aligned
with request normalization defaults, request-audit field constants, remote
execution environment fields, and builder runtime required template fields.

Discovery avoids duplicate work. Preflight Discovery runs before source parsing
with requested task types or a generic package-use task. Final Discovery runs
after task partition with the inferred `task_type` set. Both checks compare
existing Codex child skills against repository URL, package name, method name,
paper DOI, API names, and covered `task_type` entries.

Discovery output is one of:

- `reuse`: an existing skill already covers the package and requested tasks
- `update`: an existing skill covers the package but misses task types or newer
  evidence
- `create`: no matching Codex child skill was found

Discovery audit explains the final decision, best match score components,
covered and missing task types, and whether reuse is valid. A reuse decision
must cover every inferred `task_type`; otherwise the build should update or
create instead of publishing a duplicate.

Discovery match audit checks field-level identifier evidence, task_type
coverage ratio, existing child-skill shape, and ambiguous high-confidence
matches. Reuse requires full task_type coverage and a standard lightweight
child-skill shape; update requires a strong enough match to avoid modifying an
unrelated skill.

Discovery resolution audit then checks preflight and final Discovery against
the update plan. It blocks create decisions that would duplicate strong matches,
requires update/reuse targets to match the final best match, and fails closed
when high-confidence matches are ambiguous.

## Source Grounding

Source grounding records official sources without storing long excerpts:

- repository URL
- tutorial links
- documentation links
- paper links
- local or already downloaded source material paths
- optional execution traces

Remote source fetching is disabled unless explicitly requested. When enabled,
downloads are bounded by size limits and indexed without executing code.

Source fetch boundary audit checks that remote fetch remains explicit opt-in,
all fetched or registered source material stays under the run sources
directory, and unsafe archive extraction blocks publish before parsing starts.

Source indexing records compact metadata such as file kind, headings, imported
modules, function/class names, notebook cell counts, and API-call hints.
Source parse reporting also records a parser capability matrix by source kind,
including extracted fields, grounding roles, backend support, limitations, and
the rule that static parsers cannot verify execution.

Evidence cards convert indexed source records into concise claim hints for task
support, input contracts, output contracts, API entrypoints, environment
requirements, validation rules, and refusal boundaries.

The source manifest summarizes source provenance, fetch status, hashes, indexed
file counts, and evidence-card coverage. It is the build's compact audit index.

Tutorial catalog mining records compact tutorial/example step order, headings,
imports, and API-call hints without executing notebooks or scripts.

API grounding converts parsed Python files and notebooks into compact API
candidates, grouped by candidate `task_type`. These candidates are review hints,
not proof that an API call was executed.

Source indexing records Python AST symbols, signatures, return annotations,
docstring summaries, simple branch parameter values, and call hints as compact
metadata. It does not store long source excerpts and never imports the package.

Interface grounding statically inspects Python AST for signatures, defaults,
annotations, docstrings, and simple branch parameter values. It never imports
the package.

Key API coverage audit checks explicit build-request `api_names` against parsed
API and interface grounding with normalized exact symbol variants. Missing key
APIs block publish, but passing this audit still does not imply execution
verification.

Source parse reporting summarizes the parsing strategy, parsed file counts,
skipped records, compact parsed samples, interface samples, and static parsing
limitations. It exists so source parsing is auditable instead of hidden across
separate artifacts.

Source parsing coverage audits parser capability by source kind and records
fetch, indexing, API-candidate, interface, and tutorial-step coverage gaps. It
does not execute source code and does not turn static parsing into verification.

Source grounding audit checks the complete evidence path after drafting: source
priority, static parsing boundaries, task-level evidence references, contract
traceability, and rendered `references/evidence.md` sections must agree before
publish.

## Backend Contract

paper2skills is Python-first. The backend contract records which backend was
requested, which backends are implemented, and which backend requests must
produce structured refusal boundaries. R is reserved as an extension point until
implemented.

Backend extension audit checks that Python remains the only implemented
backend, R remains an explicit reserved extension, non-Python install planning
stays plan-only, and non-Python task types carry `backend_not_implemented`
refusal boundaries.

Environment spec mining records dependency manifests, imports, Python version
hints, and GPU-related terms. These are install-planning hints only; they never
authorize environment mutation.

Evidence priority:

```text
execution trace > official tutorials/docs > source code/API > paper
```

Evidence claim taxonomy audit checks each task_type for required claim classes
such as task support, input/output contract, API entrypoint, validation, and
refusal boundary. Operational claims cannot be supported only by paper evidence,
and execution-verified claims require execution evidence.

## Task Partition

Task partition separates package capabilities without splitting one package
into many skills. Each capability becomes one `task_type` inside the same child
skill.

Task partition decision logging records candidate task_type signals from the
build request, package/source heuristics, evidence cards, and tutorial shapes.
It accepts task_type entries that remain inside the single child skill, and
rejects tutorial/demo/notebook-shaped candidates as evidence-only rather than
split boundaries.

Task partition audit checks that `task_type` entries stay at capability
granularity instead of tutorial, demo, notebook, or walkthrough granularity. It
also verifies routing cues, input/output contracts, refusal boundaries, and
router coverage before downstream artifacts depend on the split.

Parameter catalog mining attaches signature-derived parameter constraints to
each `task_type` input contract. Biological meaning still has to be confirmed
from official evidence before execution.

Operational recipe attachment then combines task routing cues, mined tutorial
steps, inspected interfaces, and parameter constraints into a Quick Workflow,
API sequence, expected outputs, validation checks, clarification questions, and
troubleshooting notes for each `task_type`. Recipes are still source-grounded:
missing primary APIs or missing tutorial steps are rendered as agent-review
warnings instead of hidden assumptions.

## Task-Type Routing

The child skill teaches the agent how to choose `task_type` from user intent,
input modality, data structure, metadata, and evidence boundaries.

When task selection is ambiguous, the agent should ask for the missing
distinguishing field instead of guessing.

The task conflict matrix records pairwise ambiguity and explicit selection
rules between `task_type` entries. It is rendered into `references/task-types.md`
for generated child skills.

The routing fixture converts routes, refusal boundaries, unsupported-task
behavior, and conflict pairs into static cases. It is a pre-publish check surface
for the child skill's `task_type` router, not a package execution test.

## Agent-Driven Review Loop

The review loop is an agent-driven paper2skills review loop. Python computes the
current selection score, findings, cursor, rollout-plan state, score cache, and
safe operation contract; Codex or another agent authors the analyst,
merge, ranking, slow-update, and bounded edit proposal in
`agent_review_proposals`;
Python then validates and applies only allowed in-memory edits before
rescoring. This mirrors the record-score, rollout, analyst, merge, ranking,
apply, strict-gate, slow-update shape of a full agent-driven paper2skills review loop while
keeping the generated child skill as a Codex skill.

Every proposal operation must include a stable `operation_id` and cite
non-empty same-iteration `finding_codes`. Ranking must identify selected
operations with `operation_ids` or zero-based `operation_indices`; if
`selected_operations`, `ranked_operations`, or `chosen_operations` are used,
their entries must still carry `operation_id`.
Python rejects empty role payloads, missing `slow_update`, unlinked findings,
and operation/finding-code mismatches before applying edits.

The loop checks and scores draft artifacts for:

- overclaimed support
- missing evidence references
- missing API grounding when parseable evidence exists
- missing interface grounding when API candidates exist
- missing environment, tutorial, or parameter hints
- wrong or duplicated task splits
- missing input-output contracts
- missing refusal cases
- missing validation rules
- accidental verified claims without execution trace

The loop is bounded by `review_iterations` and stops when the selection-score
gate passes, the iteration budget is exhausted, or the run is awaiting a
complete agent review-loop proposal. When `review_summary.status` is
`needs_agent`, run `python scripts/paper2skills.py review-next-step --run
<run_dir>`, copy the returned proposal template into
`agent_review_proposals`, and rerun the build.

Review evolution summarizes each iteration's score ratio, blocking status,
focus areas, patch changes, and gate reason into `review_evolution.yaml`. The
full finding-level trace remains in `review_iterations.jsonl`.

Review evolution plot renders `review_evolution_plot.svg` as a run-level human
review artifact. It visualizes score ratio by iteration, blocking state, patch
state, and pass state without executing package code or entering the public
child skill.

Review iteration log renders `review_iteration_log.md` as a run-level human
review artifact. It summarizes each iteration's score, blockers, top findings,
patch actions, and gate reason without introducing new claims or decisions.

Review prompt contracts record the required fields, allowed actions, and
forbidden actions for `draft_snapshot`, `record_score`, `rollout_plan`,
`critic`, analyst, merge, `ranking`, `slow_update`, `patch_plan`, `revision`,
and `gate` states. They prevent the review loop from becoming an informal
free-text critique without a stable state contract.

Review prompt materials record the static prompt skeleton for each review role:
allowed inputs, required outputs, forbidden outputs, and the role purpose. This
keeps the loop auditable without storing model responses as hidden behavior.

Review prompt suite audit records whether each iteration covers the required
review duties: grounding, record scoring, rollout planning, task split and
route selection, input-output contracts, operational recipes, refusals, validation, verification
boundaries, optimizer reflection, ranking, patch planning, and gate discipline.
It prevents a structurally valid review loop from silently skipping one of the
required scientific-skill checks.

Review cursor records the current review phase, stop reason, resumability, and
required per-iteration states. Patch application records planned and applied
agent proposal actions. Together they make the paper2skills review loop resumable and
auditable without executing package code.

Review remediation audit accounts for every non-info review finding as patched,
cleared, accepted by a passing gate, or still unresolved. It blocks publish
when final blocking review findings remain or when patch actions lack
same-iteration finding traceability.

Review optimizer state records stable iteration hashes, score cache, a cache
key, strict improvement policy, and rejected buffer. Patch safety audit checks that patch
actions stay inside deterministic in-memory artifacts and do not carry
commands, file paths, installs, network actions, or file mutation instructions.
Patch operation contracts check that planned and applied patch actions use
declared operation names, contain required fields, and cite review finding
codes from the same iteration.

Review discipline audit checks the loop-level invariants: consecutive
iterations, required draft/critic/patch/gate states, consistent stop reasons,
patch/gate agreement, score ranges, and score movement after patches. It blocks
publish if the review loop appears internally inconsistent.

Rubric grounding audit checks that every scored rubric item has a machine-
readable item result, every awarded point has a grounding signal, and total
scores match the sum of per-item points. It prevents a high review score from
being accepted as an opaque number.

Evidence coverage summarizes each reviewed `task_type` by evidence priority and
claim type coverage. It warns when a task has weak claim coverage and blocks
missing evidence or execution-verified claims without execution-trace coverage.

Evidence precedence resolves which evidence can support each task claim using
the project priority order: execution trace, official tutorials/docs,
source/API, then paper. It keeps lower-priority evidence as background and
blocks verified task types whose highest evidence is not a successful trace.

## Eval Plan

The eval plan is static by default. For each `task_type`, it records acceptance,
structured-refusal, and API-review scenarios that a later validation run can use
without confusing source-grounded support with execution verification.

Execution trace validation checks supplied trace and replay-result metadata
without running code. A successful execution evidence record must include
`task_type`, `status`, `trace_ref`, environment, inputs, outputs, validation
checks, and command/notebook/script provenance before it can support
`execution_verified`.

Verification claim audit runs after child skill rendering. It checks each
`task_type` verification status against validated execution evidence, blocks
`execution_verified` without a matching successful trace and `trace_ref`, keeps
execution and tutorial replay plans plan-only, and confirms the verification
status is visible in the generated Markdown.

The execution plan is also static. It records the per-`task_type` execution
grounding boundary, required approvals, environment fields, trace capture
requirements, and success criteria. It must never run package code by itself.

The environment install plan is static and plan-only. It records detected
dependency sources, install strategy, missing remote execution fields, required
approval, and refusal conditions. It must never create, mutate, or activate an
environment by itself.

The resource inventory is static and non-downloading. It records model registry
IDs, checkpoint or weight files, external artifact URLs, data artifacts, and
model-loading APIs. Resource boundary audit checks that unresolved permissions,
licenses, logins, tokens, missing weights, and large-download approvals are
rendered as environment and refusal boundaries before execution is allowed.

The tutorial reproduction plan is static and plan-only. It maps each
`task_type` to mined tutorial/example steps, environment hints, trace
requirements, success criteria, and refusal conditions. When
`execution_grounded` is requested, missing tutorial steps or incomplete
environment fields block replay planning instead of allowing a verified claim.

Execution replay orchestration turns replay plans into plan-only replay jobs
with environment, preflight, success criteria, and trace capture contracts. It
also audits explicitly supplied replay results: complete successful results can
feed trace validation without requiring duplicate `execution_traces`, while
failed results must update troubleshooting or refusal guidance and must not be
marked verified.

The contract traceability ledger expands each `task_type` contract into
evidence-linked records for required inputs, confirmation checks, expected
outputs, validation checks, and refusal boundaries. Task-level evidence is
allowed for source-grounded drafts, but direct parsed contract evidence is
stronger.

The lineage graph links sources, evidence cards, task types, contract records,
and public child-skill files. It is a compact provenance graph for auditing
whether generated skill guidance can be traced back to official evidence and
where that guidance is rendered.

Each rendered child `SKILL.md` includes a task-specific Quick Workflow/API
sequence and a first-principles workflow DAG for every `task_type`: goal
selection, input checks, refusal boundaries, environment/resource approval,
documented workflow execution or planning, output validation, troubleshooting,
and evidence citation.

The acceptance suite turns routing, contract, traceability, refusal, ambiguity,
eval, tutorial-replay, and execution-boundary requirements into static cases.
These cases can be consumed by later validation or forward-testing without
pretending that static checks are runtime verification.

Eval splits merge static eval, routing, and acceptance cases into stable train,
selection, and test sets. Train cases support draft/debug review. Selection and
test cases support later holdout validation without leaking expected fixes into
the build loop.

Eval result judging is optional and input-driven. It only judges results
explicitly supplied in `eval_results`; an empty result list records `not_run`
instead of passing or failing the generated skill. Passing static eval results
still does not imply runtime package verification.

Agent rollout harness assembles forward-test scenarios, routing fixtures, and
eval splits into a plan-only queue. It checks task_type coverage, required
rollout kinds, split labels, judge metadata separation, and leakage controls
without launching agents or executing package code.

Agent rollout audit independently checks that every forward-test scenario maps
to a rollout case, rollout ids are unique, judge-only metadata stays out of the
agent-visible prompt, and every rollout remains planned and plan-only.

Eval leakage audit checks train, selection, and test split identity isolation,
requires holdout forward-test scenarios, and verifies that agent-visible prompts
do not contain judge-only metadata keys, expected values, or review context.

External result contract audit checks supplied `eval_results` and
`agent_rollout_results` before judging. It requires case identity fields,
judgable observed fields or status, list-shaped judge-check fields, and blocks
expected values, judge metadata, and prompts from being used as external result
evidence.

Agent rollout result judging is optional and input-driven. It only judges
results explicitly supplied in `agent_rollout_results`; an empty result list
records `not_run` instead of claiming an agent validation pass.
Each supplied result must reference `rollout_id`, `scenario_id`, or
`source_case_id`; it may report `status`, observed decision fields, and
`satisfied_judge_checks` or `failed_judge_checks`. Satisfied checks may be
reported as `all`, 1-based indexes, `check:<index>`, or
`judge_check:<index>`. These results are static evidence about an external
agent run and never imply package execution verification. Incomplete supplied
results fail closed.

## Artifact Contracts, Validation, And Audits

Lint checks the generated child skill's Codex install shape: required
frontmatter, required references, reference links from `SKILL.md`, non-empty
reference files, and absence of auxiliary docs inside the child skill.

Draft readiness checks the public child-skill Markdown for unresolved fill
markers, template braces, TODO/TBD text, lorem text, and default build-request
URLs. It blocks publishing when the generated child skill still looks like a
draft.

Child package purity audit checks the public child-skill directory against the
lightweight file contract. It allows only `SKILL.md` plus the standard
`references/` files and blocks build traces, candidates, assets, scripts,
staging files, and auxiliary docs.

Claim consistency audit checks that rendered task types, verification statuses,
evidence references, refusal reasons, and backend refusal claims match the
build artifacts. It catches overclaims introduced by rendering after review.

Biological claim boundary audit checks rendered child-skill text for high-risk
cross-modal biological claims, such as inferring molecular, pathway, or clinical
targets from an unsupported source modality. Such claims require matching task
and evidence support; otherwise the skill must refuse instead of guessing.

Child reference coverage checks that source parsing coverage, environment
install boundaries, tutorial replay plans, evidence precedence, task conflicts,
operational recipes, and task_type entries are rendered into the public child
references. It catches the failure mode where an internal artifact exists but
the generated skill never exposes the operational boundary to the agent.

Source grounding audit then verifies that rendered references preserve evidence
priority and task-level traceability.

Workflow invariant audit checks the product-level shape: one package creates
one child skill, package capabilities remain `task_type` entries inside that
skill, the target agent is Codex, Python is the implemented backend, R remains
an extension boundary, and every task is covered by routing, eval, execution,
contract, tutorial reproduction planning, lineage, and rendered-claim
artifacts.

Completion evidence audit separates static build completion from full
real-package completion. Acceptance handoff packages the external rollout,
replay, and E2E result templates without treating those templates as evidence.
Protocol compliance audit then checks that plan-only artifacts stayed
plan-only, external result evidence came through audited request fields, output
directories stayed outside likely install roots, and completion claims are not
stronger than supplied evidence.

The grounding gate checks whether each `task_type` has linked API or interface
grounding when parseable source material exists. It warns on source-grounded
tasks that lack API/interface links and blocks verified task types that lack
grounded API/interface evidence.

API surface audit checks the generated public Markdown after rendering. It
blocks ungrounded code-fence API calls, warns on ungrounded inline API-like
mentions, checks request-provided API names against parsed surfaces, and records
task types without linked API or inspected interface evidence.

Artifact contracts define the minimum stable shape of every generated YAML
artifact: required top-level fields plus list and mapping field types.

Phase state audit checks the run ledger before publish gating. It verifies
unique phase names, completed-phase gates, contracts for YAML outputs, and
single ownership for phase outputs.

Artifact closure audit checks that every required top-level artifact has a
contract, every pre-publish artifact is available before publish gating, and
the run write plan covers the required artifact set. It is static and never
executes package code.

Output boundary audit checks that generated child skills stay under the build
output's `child_skill/` root, run output directories are not placed inside
likely skill install roots, and public child skills do not contain build
artifacts or auxiliary docs. Discovery match audit checks that reuse/update decisions have strong
field-level evidence and that reused skills satisfy the lightweight child-skill
shape. Skill update planning converts the final Discovery decision into a
plan-only release action, including a manual merge plan when an existing child
skill should be updated instead of duplicated. Skill update audit checks that
create, update, and reuse plans are plan-only, non-destructive, and limited to
standard child-skill files. Forward test planning creates
independent test-agent prompts from acceptance and eval-split cases, with
expected behavior kept outside the prompt so the test can reveal whether the
child skill is usable without leaked answers. Code-fence audit checks generated
Markdown for machine-local path leaks and ungrounded API calls inside code
fences. Public safety audit checks generated public Markdown for credentials,
private keys, contact identifiers, and long copied excerpts before release.
Routing metadata audit checks that task_type selection stays inside one child
skill and that rendered routing docs include selection, ambiguity, and refusal
boundaries.

Artifact validation checks those contracts, pre-publish schema versions,
required artifacts, discovery audit status, discovery match audit status, resource boundary audit status, task-to-route coverage, routing fixture coverage,
task-to-eval coverage, tutorial reproduction plan coverage, acceptance case
coverage, evidence precedence, lineage graph coverage, eval split coverage,
supplied eval-result status, source fetch boundary audit, source parsing coverage, source parsing audit,
source grounding audit, resource boundary audit, review prompt contracts, review prompt suite audit, review iteration log,
review cursor status, patch application status, review optimizer state, patch
safety, patch operation contracts, review discipline, rubric grounding, review trajectory, grounding-gate
status, output boundary status, skill update plan status, skill update audit status, forward-test plan
status, agent rollout harness status, API surface audit, key API coverage audit, verification claim audit, execution-plan boundaries, backend support, child
reference coverage, routing metadata audit, requirement coverage, and audit status.

## Publish Gate

The publish gate blocks generated output when lint fails, review does not pass,
task evidence is missing, or a task claims `execution_verified` without trace
evidence. It also consumes verification claim audit so rendered Markdown cannot
silently overstate verification status. When Discovery recommends reuse, it returns a `reuse_ready` no-copy
status instead of making the generated candidate publishable. It also consumes
artifact validation, eval split, supplied eval-result, code-fence audit, and
public safety audit results, blocks failed discovery audit, discovery match audit, output boundary,
skill update planning, skill update audit, forward test planning, agent rollout harness, key API coverage audit, source fetch boundary audit, source parsing coverage,
source parsing audit, routing metadata audit, source grounding audit, environment install planning, resource boundary audit, review prompt contracts, review prompt suite audit, review iteration log, review cursor, patch
application, review optimizer state, patch safety, patch operation contracts, review trajectory, requirement coverage, and
tutorial reproduction planning, and warns when API candidates lack inspected
interface grounding.

The quality report summarizes review, lint, artifact validation, evidence
precedence, verification claim audit, claim consistency, child reference coverage, routing metadata, workflow invariants,
lineage graph, eval splits, supplied eval results, discovery match audit, resource boundary audit, review prompt contracts, review prompt suite audit, review iteration log, review cursor, patch
application, review optimizer state, patch safety, patch operation contracts, review discipline, rubric
grounding, review trajectory, code-fence audit, public safety audit, output boundary audit, skill
update planning, skill update audit, forward test planning, agent rollout harness, API surface audit, publish gate,
candidate selection, candidate promotion, final candidate audit, source parsing, source parsing coverage, source parsing
audit, routing metadata audit, source grounding audit, execution planning, environment install planning, resource boundary audit, tutorial reproduction
planning, requirement coverage, and per-task contract coverage into a single report. The build
timeline records phase, review, and gate events for debugging and auditability.
The score report summarizes review trajectory, rubric grounding, quality
blockers, publish blockers, candidate gates, candidate evolution status, Codex
publish adapter status, install readiness, and publish manifest audit status
after publish manifest audit.
The run scorecard renders the final completion, release action, quality,
blocking findings, and recent timeline into `run_scorecard.md` for human review
without changing the machine-readable publish decision.

## Publish

The public child skill is lightweight and human-readable. Build artifacts,
full traces, and long source excerpts stay outside the public skill package.
Child metadata audit checks that `SKILL.md` has valid Codex trigger
frontmatter, mentions every task_type, and does not introduce nested child
skills, default scripts, or separate routing-selector shapes.
The release package manifest records which files are ready to copy into a Codex
skills directory, but does not copy or install anything by itself.
Codex publish adapter converts the release decision into plan-only create,
update, or reuse steps for Codex skills. It records required files and manual
copy or merge steps, but never mutates the user's Codex skills directory.
Candidate selection audit records why the registry active version was selected,
including quality signals, single-child-skill invariants, and reuse/update/create
release-action boundaries.
Candidate promotion audit checks that the active candidate exists, mirrors the
publish gate, includes the required public files, and is not promoted as a
duplicate when reuse is recommended.
For `reuse_existing`, the install plan must not copy the generated candidate as
a duplicate child skill. For `update_existing`, it must preserve the target
existing skill path and require manual merge review. For `create_new`, it may
describe copying the generated child skill after publish and install-readiness
gates pass.

Install readiness checks the generated public child-skill directory against the
release manifest for `create_new` and `update_existing`. For `reuse_existing`,
it returns `not_applicable` because no generated duplicate should be copied.
For copyable actions, it blocks missing required files, empty required files,
build artifacts inside the public child skill, auxiliary docs, and cache files.

Publish manifest audit checks that the manifest, release package, install
readiness, and reuse/update/create recommendation agree before run-level
provenance is recorded.

Builder version audit checks that core artifacts use the active schema version
and that release-facing metadata records the active builder version. It runs
after publish manifest audit because it needs release-facing metadata, and it is
a static consistency gate rather than a runtime smoke test. `smoke_test_plan.py`
is a separate plan-only package-shape checklist and supplied-result audit.

Release action audit checks the selected create/update/reuse action across
skill update planning, skill update audit, publish gate, release package, candidate promotion,
final candidate audit, install readiness, Codex publish adapter, publish
manifest, and publish manifest audit. It is the final no-copy/no-duplicate
guard for reuse and the final promoted/finalized guard for create or update.

Architecture completeness audit checks that major phase families and their
focused gate artifacts, including artifact closure, are present before final
completion.

Completion audit aggregates the final semantic gates into one verdict. It
checks builder runtime audit, module inventory audit, skill package audit, request template audit, builder version audit, request audit, Discovery match audit, resource boundary audit, child metadata audit, child package purity audit, requirement coverage, architecture completeness,
artifact validation, artifact closure, skill update audit, publish gate, candidate selection, candidate promotion,
final candidate audit, candidate evolution audit, quality report, release package, Codex publish adapter,
install readiness, publish manifest audit, score report, release action audit,
skill update planning, review prompt suite audit, review iteration log, patch operation contracts, phase coverage, and run-manifest planning under the
selected create/update/reuse action before the run is considered complete.

The run manifest records the generated root artifacts and public child-skill
files with size and SHA-256 hashes. It supports remote validation and release
review without embedding downloaded sources, copied local evidence, or long
execution traces. Use `paper2skills.py verify-run-manifest --run <run-dir>`
to re-check recorded file sizes and hashes after transfer or remote validation.

Output retention runs after the run manifest. It copies selected review,
candidate, release, scorecard, and manifest artifacts into
`iteration_versions/`, writes `generation_process.md`, keeps the final
`child_skill/`, keeps root publish and run manifest entry files, and removes
builder-generated process artifacts when `cleanup_process_files` is true. It
deletes only unprotected files recorded as run artifacts plus builder-owned
source/cache directories, so unknown user files in the output directory are not
treated as cleanup targets.
