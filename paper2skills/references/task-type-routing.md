# Task-Type Routing

Task-type routing tells the agent how to choose a capability inside the same
child skill.

The generated child skill should guide the agent through this order:

1. Match user intent to candidate `task_type` entries.
2. Check input modality and data format.
3. Check required metadata and parameters.
4. Prefer `execution_verified` task types over merely `source_grounded` task
   types when both match.
5. If multiple task types still match, ask the user for the missing goal or
   metadata distinction.
6. If no task type matches, refuse with an evidence-backed reason.

Routing is not a hidden classifier. It is an explicit reference-backed decision
aid for the agent.

`routing_fixture.yaml` is the static check surface for this behavior. It should
contain at least one select case and one structured-refusal case for every
`task_type`, one unsupported-task refusal case for the whole skill, and
ambiguity cases for each conflict-matrix pair.
