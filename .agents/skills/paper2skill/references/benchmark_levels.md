# Independent Benchmark Levels

Benchmark evaluation is independent from build-time validation. It evaluates a
generated child skill against a gold-standard case.

## L0

Checks package shape, required files, policy safety, and absence of local path
leakage.

## L1

Compares evidence and contracts against gold expectations:

- source collection
- tutorial trace
- workflow DAG
- IO and Bio contracts
- algorithm routing contract (`applicability`, `recommended_execution`, refusal rules)
- environment evidence
- adapter review
- evidence bundle

## L2

Runs reviewed official minimal/example adapter execution with expected outputs.
Demo-mode summary runs are not sufficient for L2.

## L3

Runs gold new-data adaptation and validates the output contract.

## L4

Evaluates an agentic trace showing that an agent used the child skill
end-to-end, including decisions and error recovery.

## Command

```bash
python scripts/paper2skill.py benchmark run \
  --case path/to/case.yaml \
  --level L0
```
