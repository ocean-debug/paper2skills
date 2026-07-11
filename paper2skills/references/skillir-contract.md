# SkillIR Contract

`skill_spec.yaml` is the internal source of truth. It is not copied into the
public child skill.

## Package Fields

- `package.name`: lowercase skill identifier;
- `package.display_name`: human-facing package name;
- `package.description`: trigger-oriented description;
- `package.source_revision`: requested source version or `unresolved`;
- `shared_environment`: evidence-backed environment facts;
- `package_boundaries`: package-wide refusal and interpretation boundaries;
- `shared_troubleshooting`: issues relevant to more than one task.

## Task Fields

Use a mapping keyed by lowercase snake-case `task_type`. Every task requires:

- `output_file`: `task-<hyphen-name>.md`;
- `intent` and `selection_rules`;
- `do_not_select`;
- `accepted_inputs` and `required_metadata`;
- `preflight_checks`;
- `workflow`;
- `api_sequence`, with `api`, `action`, and `evidence_ids` per step;
- `parameters` and `expected_outputs`;
- `refusal_rules`;
- `technical_validation`;
- `biological_boundaries`;
- `reuse_contract`;
- `troubleshooting`;
- `evidence_ids`;
- `verification_status`;
- `execution_evidence` as `E-RUN-*` evidence IDs when execution was attempted.

Use an explicit statement such as `No task-specific metadata requirement was
confirmed` instead of leaving a required section empty.

## Routing Fields

- `aliases`: map common user language to one task type;
- `ambiguity_rules`: distinguish every overlapping task pair;
- `unsupported_cases`: package-level requests that must be refused.

When the skill contains more than one task, at least one ambiguity rule is
required unless each task's selection rules are demonstrably disjoint and the
spec states why.

## API Entries

Prefer structured entries:

```yaml
api_sequence:
  - api: package.Model.setup_anndata
    action: Register required observation metadata before training.
    evidence_ids: [E-SRC-1234, E-TUT-5678]
```

Do not add an API only because it is plausible. It must appear in grounded
source or an official tutorial for the requested version.
