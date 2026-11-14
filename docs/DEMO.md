# Leadership demonstration

**Goal:** Show how AEA evaluates an existing agent, records quality metrics and
detects a controlled regression with a readable failure explanation.

## Run locally

```sh
uv lock --check
uv sync --all-extras --group dev --locked
uv run --locked python scripts/leadership_demo.py --output-dir demo-output
```

The script refuses to overwrite an existing destination. Choose another folder
for a repeat demonstration. Open `demo-output/DEMO.md` for the generated summary
and `demo-output/regression-report.html` for the exported comparison. The script
uses synthetic data and no cloud model credentials.

## Five-minute presentation

1. **Problem (45 seconds):** Agents can change unexpectedly when prompts,
   tool calls and business rules evolve, and manual testing does not scale.
2. **Integration (45 seconds):** Show JSONL cases and an existing Strands agent
   factory. LangGraph integration is also demonstrated in the offline CI suite.
3. **Passing evaluation (60 seconds):** Show the passing 11/11 baseline, recorded
   trace and report and the unchanged-agent comparison.
4. **Controlled regression (90 seconds):** Show the intentionally defective
   refund-policy agent, non-zero exit code, affected case and HTML comparison.
5. **Delivery-team adoption (60 seconds):** Show CI, reproducible dependencies and
   the proposed two-team pilot. Claim productivity gains only when independently
   measured.

## Optional measured runtime exhibit

Run `uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir benchmark-evidence` and show the generated `BENCHMARK.md`. It measures local subprocess wall time and controlled regression detection for two self-authored synthetic integrations. **No developer-hours saved or external-team adoption are established** by this measurement. See the [benchmark protocol](BENCHMARKING.md).

## Evidence and limitations

The demo proves deterministic local baseline and regression behaviour, not live
model repeatability, client security sign-off, or adoption across teams. The
generated outputs are redacted by default but may still contain case IDs, paths,
model identifiers and trace metadata. Review outputs before sharing.

See [security assessment](SECURITY_REVIEW.md) and [pilot plan](PILOT.md).
