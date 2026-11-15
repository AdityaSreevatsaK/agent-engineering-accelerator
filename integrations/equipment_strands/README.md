# Equipment warranty: standalone AWS Strands app

This is a self-contained synthetic equipment-support application. Its `agent.py` uses the real Strands execution and tool loop with a deterministic model double, plus `dataset.jsonl` (12 cases).

For **every explicit step**, Windows PowerShell commands, exit-code handling and expected report paths, follow [the complete Strands walkthrough](../../docs/STEP_BY_STEP.md#b-full-aws-strands-equipment-warranty-flow).

## One-command walkthrough (recommended)

From the AEA repository root, after installation:

```sh
uv run --locked python scripts/validate_independent_integrations.py --only equipment-strands --repeats 1 --output-dir strands-001
```

Read `strands-001/evidence.json`. It covers baseline, normal check, deliberately broken check and baseline safety without editing code. See the [simple step-by-step guide](../../docs/STEP_BY_STEP.md).

## Manual individual CLI commands (optional)

From the AEA repository root, run `uv sync --all-extras --group dev --locked` and activate the resulting virtual environment: `.venv\\Scripts\\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Then change into `integrations/equipment_strands`.

```sh
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
aea check dataset.jsonl --config aea.toml --baseline runs/approved --runs-dir runs/evals --max-samples 1
aea check dataset.jsonl --config aea.toml --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
```

The local `aea.toml` selects the Strands adapter and `agent:build_agent`. The last command overrides the configured factory without modifying AEA or the application's baseline.

**Expected results:** 12/12 passes on initial evaluation, 12/12 on the unchanged check (exit 0), and newly failing expired-warranty cases on the faulty variant (exit 1). Inspect the generated comparison report in `runs/evals`.

**Important:** run `aea` from **this directory**, so Python can import `agent`. The default redaction does not guarantee that metadata is anonymous. The model and equipment records are synthetic; no cloud services or real adoption claims are involved. Do not commit `runs/`.
