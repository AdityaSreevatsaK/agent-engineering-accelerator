# Development and CI

Use Python 3.11 or 3.12 and uv 0.10.0. The repository includes a reviewed `uv.lock`; resolve dependencies reproducibly via `uv lock --check` before syncing.

```sh
uv lock --check
uv sync --all-extras --group dev --locked
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/check_examples.py
uv run --locked python scripts/validate_independent_integrations.py --repeats 1
```

The offline test runner executes all standalone test modules and a selected set of CLI parser/configuration tests from the fixed-reference CLI integration module. The seven snapshot-dependent comparison/statistics groups have now been replaced with independently constructed synthetic cases, so none of those groups are excluded. The fixed-reference CLI integration module remains partially selected, and its unselected tests are not claimed as passing. A new test file must be classified before CI can pass. The calculator, triage, expense, policy RAG and helpdesk examples provide deterministic smoke coverage.

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
