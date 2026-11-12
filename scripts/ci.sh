#!/usr/bin/env bash
# Offline local checks for AEA. Run from the repository root.
set -euo pipefail
export PYTHONUTF8=1
uv lock
uv sync --all-extras --group dev --locked
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/check_examples.py
