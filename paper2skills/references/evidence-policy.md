# Evidence Policy

## Priority

1. Official runnable tutorial or example
2. Current source code, public API signature, or official test
3. Official documentation or repository usage instruction
4. Paper Methods or supplement
5. Paper abstract

Use lower-priority evidence to supplement, not override, higher-priority
operational evidence.

## Evidence IDs

Use stable IDs with a source-kind prefix:

- `E-TUT-*`: tutorial, example, demo, or notebook;
- `E-SRC-*`: source symbol, signature, branch, or official test;
- `E-DOC-*`: official documentation or repository guide;
- `E-PAPER-*`: paper or supplementary method;
- `E-RUN-*`: validated execution record.

Every API call, required input, refusal condition, output expectation, and
verification claim must cite relevant IDs.

Executable APIs require at least one inspected `E-SRC-*` or `E-TUT-*` record.
Documentation and papers may explain an API but cannot be its only grounding.

## Inference Boundary

When no tutorial exists, workflow inference may use source, official tests,
documentation, and repository usage instructions. Mark inferred steps with
their evidence and uncertainty. Do not represent them as officially
recommended or execution-verified.

Do not infer missing biological labels, control/treatment semantics, species,
modality, units, normalization state, or resource availability.

## Conflicts

When tutorial code conflicts with the requested source revision:

1. record both sources;
2. prefer the current source behavior;
3. describe the tutorial as version-stale when evidence supports that result;
4. do not silently rewrite an API without recording the conflict.

## Claim Labels

- `source_grounded`: supported by official static evidence;
- `execution_verified`: supported by successful versioned execution evidence;
- `execution_failed`: execution failed and informed troubleshooting;
- `unsupported`: outside the available package or evidence boundary.
