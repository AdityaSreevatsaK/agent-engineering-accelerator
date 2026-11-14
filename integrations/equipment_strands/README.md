# Equipment warranty, standalone AWS Strands integration

Synthetic equipment-support agent with a two-step `find_equipment` → `check_warranty` tool workflow, unknown equipment handling, a 12-case JSONL evaluation dataset, and a deliberately defective factory.

## Manual onboarding from an installed AEA environment

At the AEA repository root, install `uv sync --all-extras --group dev --locked`, then activate the environment: `.venv\\Scripts\\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. From this application directory:

```sh
aea check dataset.jsonl --adapter strands --agent agent:build_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1 --update-baseline
aea check dataset.jsonl --adapter strands --agent agent:build_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
aea check dataset.jsonl --adapter strands --agent agent:build_broken_agent --baseline runs/approved --runs-dir runs/evals --max-samples 1
```

Expected: 12/12 passing when the baseline is frozen, then a matching run (exit 0). The defective agent ignores warranty expiry, causing new failures for the expired equipment (exit 1). Inspect `runs/evals` and the comparison report; no application changes are needed to AEA.

All values are invented and the model is deterministic. This does not simulate live LLM reliability or demonstrate independent adoption. Never commit the `runs/` directory.
