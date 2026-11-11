# Fresh AEA baselines (2026 reconstruction)

This folder is intentionally **separate from the historical `baselines/`** directory.

The seven reproducible offline baselines below are generated from the *current reconstructed agents* and are **new evaluation runs**, not recovered 2026 historical log files. Existing originals may later be restored under `baselines/` without conflicting with this directory.

| Generated baseline | Agent | Dataset |
| --- | --- | --- |
| `calculator-strands/` | `examples.calculator.agent:build_agent` | `examples/calculator/dataset.jsonl` |
| `calculator-langgraph/` | `examples.calculator.langgraph_agent:build_agent` | same calculator dataset |
| `orders/` | `examples.orders.agent:build_agent` | `examples/orders/dataset.jsonl` |
| `expense/` | `examples.expense.agent:build_agent` | `examples/expense/dataset.jsonl` |
| `triage/` | `examples.triage.agent:build_agent` | `examples/triage/dataset.jsonl` |
| `policy_rag/` | `examples.policy_rag.agent:build_agent` | `examples/policy_rag/dataset.jsonl` |
| `helpdesk/` | `examples.helpdesk.agent:build_agent` | `examples/helpdesk/dataset.jsonl` |

**Known historical discrepancy (do not "fix" the original):** The video-verified
`examples/orders/rules.py` replies **"Carol has spent 17.50 across 2 orders."**,
whereas the screenshot-verified Orders dataset expects **"Carol spent 17.50 across 2 orders."**.
The reconstructed Orders agent therefore passes **10/11**, with only `total_spend`
failing. The generator explicitly records this documented mismatch in
`manifest.json` and **rejects any additional failure**. All six other agent
baselines must pass every case. We do not rewrite original evidence to obtain
misleading green baseline counts.

Each permitted generation produces an Inspect evaluation log (`.json`), a derived `report.md`, redacted `traces.jsonl`, and the top-level `manifest.json` recording generator revision, dataset hashes, baseline log hashes and run characteristics. The generator uses `aea check --update-baseline` **without** `--capture-content` or paid model providers; it refuses to overwrite an existing baseline.

## Generate all seven baselines

Install Python 3.11 or 3.12 and, from the repository root:

```powershell
python -m pip install -e ".[langgraph,strands]"
python -m reconstruction_tools.generate_fresh_baselines --dry-run
python -m reconstruction_tools.generate_fresh_baselines
```

The workflow **AEA fresh reconstructed baseline bundle** also executes these commands on a GitHub Actions runner and uploads the generated `baselines-new/` directory as an artifact for review. The workflow does **not** commit run outputs or touch `master`.

The tracked `baselines-new/.gitignore` deliberately prevents accidental `git add` of generated run directories or `manifest.json`. Review downloaded logs, traces and metadata for privacy before any explicit `git add -f`; being generated offline does not guarantee that all metadata is anonymous. The CI artifact remains the preferred distribution mechanism until a human review authorises a frozen reference bundle.

Generation is intentionally **non-destructive**: to regenerate, archive or move the existing generated subfolders and `manifest.json` first. Do not copy a new evaluation log into `baselines/` under an original historic filename and claim authenticity.

## Important boundaries

- Default scrub mode suppresses case prompts, completions, messages and tool arguments from log files, but still retains identifiers, case IDs, model/tool names and metadata. Use only the bundled synthetic examples for shareable artifacts; review logs before redistributing.
- `--capture-content` is never used. No credentials or live model calls are needed.
- Generated baselines do **not** increase the historical inventory's recovered count (97/117); original `baselines/` remains reserved for recovered evidence.
- Running this generator requires the reconstructed AEA package and its LangGraph/Strands dependencies; Python standard library alone is not enough.
