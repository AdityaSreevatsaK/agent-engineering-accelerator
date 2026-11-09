#!/usr/bin/env bash
# Local stand-in for .github/workflows/ci.yml: lint, types, unit tests, then each example against its baseline.
# Usage: scripts/ci.sh  (from the repo root; exits non-zero on the first failure)
set -euo pipefail
export PYTHONUTF8=1

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT

uv sync --all-extras --locked
uv run ruff check src examples
uv run ruff format --check src examples
uv run pyright
if [ -d tests/unit ]; then uv run pytest tests/unit -q -m "slow or not slow"; else echo "no unit tests yet"; fi
uv run pytest tests/conformance -q -m "slow or not slow"

check() {  # check NAME BASELINE DATASET ADAPTER AGENT [EXTRA RUN ARGS...]
    uv run aea run "$3" --adapter "$4" --agent "$5" "${@:6}" --runs-dir "$out/$1"
    uv run aea compare "$2" "$out/$1"/*/ --output "$out/$1.md" > /dev/null || { cat "$out/$1.md" 2>/dev/null; return 1; }
    echo "$1: no regression"
}
check calculator-strands baselines/calculator.json examples/calculator/dataset.jsonl strands examples.calculator.agent:build_agent
check calculator-langgraph baselines/calculator.json examples/calculator/dataset.jsonl langgraph examples.calculator.langgraph_agent:build_agent
check orders-strands baselines/orders.json examples/orders/dataset.jsonl strands examples.orders.agent:build_agent
check expense-langgraph baselines/expense examples/expense/dataset.jsonl langgraph examples.expense.agent:build_agent \
    --scorer examples.expense.scorers:amounts_grounded
check triage-langgraph baselines/triage examples/triage/dataset.jsonl langgraph examples.triage.agent:build_agent \
    --input-map examples.triage.agent:to_input --output-map examples.triage.agent:from_output
check policy_rag-langgraph baselines/policy_rag examples/policy_rag/dataset.jsonl langgraph examples.policy_rag.agent:build_agent
check helpdesk-langgraph baselines/helpdesk examples/helpdesk/dataset.jsonl langgraph examples.helpdesk.agent:build_agent
echo "ci: all checks passed"
