# Workflow

## 1. Prepare a Request

Copy `assets/build-request.yaml` to a working directory. Keep the run output
outside the installed `paper2skills/` folder.

Required request facts:

- package name and display name;
- official repository URL or local source path;
- official tutorial/example paths or URLs when available;
- output directory.

Use `source_revision` to pin the source being described. Add explicit key APIs
when the user already knows which interfaces matter.

## 2. Initialize

```bash
python paper2skills/scripts/paper2skills.py init --request request.yaml
```

Initialization writes normalized request, empty evidence/SkillIR state, and a
compact event log. It does not fetch, install, or execute the target package.

If only `repo_url` was supplied, obtain the requested official revision under
`<run-dir>/sources/repository/` and add its path to `request.yaml.source_paths`.
Prefer a normal Git checkout. If Git is unavailable, use an official archive or
user-provided checkout and record the revision or archive identity. Apply the
same rule to tutorial URLs: save inspected official content locally and add it
to `tutorial_paths` before grounding whenever possible.

## 3. Ground Sources

```bash
python paper2skills/scripts/paper2skills.py ground --run <run-dir>
```

Grounding statically indexes local Python source, Markdown/RST usage guides,
scripts, and notebooks. URLs are registered as external evidence; Codex must
read or fetch them through an available web/GitHub tool before relying on
their content.

After inspecting a registered URL, update its record in `evidence.yaml` with a
specific claim type and concise summary. Do not change an uninspected URL record
merely because its title looks relevant. Ground executable APIs from a local
official checkout whenever possible.

Read `source_report.yaml` and `agent_packet.md`. If local source is missing,
obtain an official checkout inside the run directory or another user-approved
workspace, update `request.yaml`, and rerun grounding.

## 4. Synthesize Task Contracts

Fill `skill_spec.yaml`. Each task must be an analysis goal and must include:

- selection and non-selection rules;
- inputs, metadata, and preflight checks;
- workflow and grounded API sequence;
- outputs and refusal rules;
- technical validation and biological interpretation boundaries;
- reuse and troubleshooting guidance;
- evidence IDs and task-specific verification status.

If two candidates differ only by dataset, tutorial, parameter, or plot, merge
them. If multiple tasks overlap, add explicit ambiguity rules.

## 5. Render and Review

```bash
python paper2skills/scripts/paper2skills.py render --run <run-dir>
python paper2skills/scripts/paper2skills.py validate --run <run-dir>
```

Inspect `child_skill/<package>/` as a fresh Codex instance would. The entry
skill must link every task file directly. A selected task file should contain
the complete task-specific contract without requiring unrelated task files.

For bounded changes, copy `assets/patch-proposal.yaml`, edit it, and run:

```bash
python paper2skills/scripts/paper2skills.py apply-patch \
  --run <run-dir> --proposal patch-proposal.yaml
```

Rerender after every SkillIR change.

## 6. Publish

```bash
python paper2skills/scripts/paper2skills.py publish --run <run-dir>
```

Publishing fails when validation has blockers. It copies only the child skill
to `<run-dir>/published/<package>/` and writes a run-local manifest. It never
installs into a Codex directory.

## Optional Execution Feedback

Execution is separate and opt-in. Use the exact host, directory, environment,
node, and core count supplied by the user. Record successful or failed results
in the relevant task contract. Upgrade only a successfully exercised task to
`execution_verified`; failures should improve troubleshooting instead.
