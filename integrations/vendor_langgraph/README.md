# Supplier onboarding, standalone LangGraph integration

Synthetic supplier-registration and policy-screening workflow. It uses custom `TypedDict` state instead of LangGraph's standard `messages` channel. Accordingly, **both** mapping hooks are required for AEA.

## Manual onboarding from an installed AEA environment

At the AEA repository root, run `uv sync --all-extras --group dev --locked`, then activate `.venv\\Scripts\\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. From this application directory:

```sh
aea check dataset.jsonl --adapter langgraph --agent agent:build_agent --input-map agent:to_request --output-map agent:read_decision --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
aea check dataset.jsonl --adapter langgraph --agent agent:build_agent --input-map agent:to_request --output-map agent:read_decision --baseline runs/approved --runs-dir runs/evals --max-samples 1
aea check dataset.jsonl --adapter langgraph --agent agent:build_broken_agent --input-map agent:to_request --output-map agent:read_decision --baseline runs/approved --runs-dir runs/evals --max-samples 1
```

Expected: 12/12 passes, then a matching comparison (exit 0), then a regression on vendors with sanctions holds (exit 1). This exercises a real compiled LangGraph state machine with conditional edges, without requiring cloud model services.

Common onboarding pitfall: without `--input-map`, the default AEA mapping expects a `messages` channel, which this application deliberately does not have. Without `--output-map`, the custom `response` field cannot be interpreted as a standard AIMessage. Never commit `runs/` or infer external-team productivity from this integration.
