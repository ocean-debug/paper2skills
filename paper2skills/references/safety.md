# Safety

paper2skills creates operational agent skills, so unsupported claims can lead
to wrong scientific analysis. Prefer explicit uncertainty over implied support.

## Must Not

- fabricate APIs, parameters, outputs, or evidence
- silently install dependencies
- silently patch upstream source or site-packages
- mark unexecuted paths as verified
- bundle long copyrighted excerpts
- bundle tutorial datasets in public child skills by default
- publish credentials, private keys, personal contact identifiers, or
  machine-local paths in public child skills

## Public Release Audit

Generated child skills must pass two separate Markdown audits before publish:

- code-fence audit: machine-local paths and ungrounded API calls
- public safety audit: credentials, private keys, contact identifiers, and long
  copied excerpts

## Remote-Only Validation

When the user specifies remote-only validation rules, local work is limited to
inspection, search, and editing. Tests, builds, lint, benchmarks, tutorial
reproduction, and commands that execute project code must run only on the
specified remote server, folder, environment, node, and CPU allocation.
