# Supplier onboarding: standalone LangGraph app

This is a self-contained synthetic supplier-compliance workflow using a compiled LangGraph with custom `TypedDict` state, policy screening and conditional routing. It evaluates 12 cases without a model-provider account.

## Get started

From the AEA repository root, run `uv sync --all-extras --group dev --locked` and activate the environment: `.venv\\Scripts\\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Then change into `integrations/vendor_langgraph`.

```sh
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
```

The local `aea.toml` defines `adapter`, `agent`, `input_map` and `output_map`. The final command overrides only the agent factory, leaving the custom-state mappings intact.

**Expected results:** 12/12 initial passes; unchanged comparison exit 0; a defective policy that approves blocked suppliers is detected with exit 1.

**Common onboarding issue:** the CLI resolves `agent:...` relative to the current working directory. This graph does not have a conventional `messages` channel, so both mapping hooks are mandatory. Avoid deleting them when adapting the configuration to another application. All records are synthetic. Do not commit `runs/` or infer independent team uptake from these checks.
