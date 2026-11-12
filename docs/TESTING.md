# Development and CI

Use Python 3.11 or 3.12 and uv 0.10.0. The repository includes a reviewed `uv.lock`; resolve dependencies reproducibly via `uv lock --check` before syncing.

```sh
uv lock --check
uv sync --all-extras --group dev --locked
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/check_examples.py
```

The offline test runner executes every listed module except the fixed-reference CLI contract module, with specific snapshot-only cases explicitly deselected. It fails if another test file appears without being classified. The calculator, triage, expense, policy RAG and helpdesk examples provide deterministic smoke coverage.

When adding a new agent adapter or scorer, add focused unit tests, use synthetic evaluation data, and verify that default logs and traces do not leak prompts or tool arguments.

CI runs on Windows and Linux using Python 3.11 and 3.12. Keep live cloud-provider calls out of automated checks.

See [engineering assessment](ENGINEERING_AUDIT.md) for current coverage gaps and release criteria.

Additional release gates:

```sh
uv run --locked python scripts/verify_regression_gate.py
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

The regression check freezes a passing Orders evaluation and verifies that a deliberately faulty refund-policy agent produces a non-zero regression exit while leaving the baseline untouched. The distribution check installs the built wheel into a disposable environment, then verifies CLI help, starter creation and escaped HTML output. Both are offline with respect to model providers.
