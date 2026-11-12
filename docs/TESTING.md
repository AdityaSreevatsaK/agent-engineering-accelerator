# Development and CI

Use Python 3.11 or 3.12 and `uv`.

```sh
uv lock
uv sync --all-extras --group dev --locked
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/check_examples.py
```

The unit-test runner selects offline tests that do not require external service accounts or unavailable captured fixtures. The calculator, triage, expense, policy RAG and helpdesk examples provide deterministic smoke coverage.

When adding a new agent adapter or scorer, add focused unit tests, use synthetic evaluation data, and verify that default logs and traces do not leak prompts or tool arguments.

CI runs on Windows and Linux using Python 3.11 and 3.12. Keep live cloud-provider calls out of automated checks.
