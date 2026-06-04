# Contributing

## Development Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Safety Rules

- Do not add online LLM calls.
- Do not auto-install dependencies in generated skills.
- Do not run unknown repository install scripts during build or tests.
- Keep generated public outputs free of absolute local paths.

## Pull Request Expectations

- Add or update tests for behavior changes.
- Keep toy Python and toy R examples passing.
- Mark demo-only execution clearly; do not present it as real algorithm execution.
