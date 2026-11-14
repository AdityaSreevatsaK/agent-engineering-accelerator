# AEA v2.2.0: synthetic performance and value measurement

**Status:** Repeatable local technical benchmark. It does **not** demonstrate time saved by engineers, superiority to a manual workflow, live-provider quality or independent team adoption.

## What we measure today

The [standalone Strands warranty application](../integrations/equipment_strands/README.md) and [LangGraph supplier application](../integrations/vendor_langgraph/README.md) each have 12 synthetic evaluation cases, their own `aea.toml`, and a deterministically defective agent.

From the repository root:

```sh
uv sync --all-extras --group dev --locked
uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir benchmark-evidence
```

The output directory must **not already exist**. Review `benchmark-evidence/BENCHMARK.md` and `evidence.json`. These are generated on the machine running the benchmark. The script also creates local redacted baselines and run reports under the output directory; do **not** publish the entire directory. A CI release job uses `--repeats 2` and retains *only* the summary Markdown and JSON for 14 days.

The benchmark records: baseline-freeze elapsed time, each unchanged AEA comparison's subprocess elapsed time, median/p95 of those observations, one deliberately faulty evaluation's elapsed time, total CLI time, expected 12-case pass count, unchanged reruns and detected controlled regressions. Each comparison must preserve the baseline byte-for-byte. The same public CLI and adapter settings are exercised as in the example onboarding guides.

### Measurement definitions

| Name | Meaning | Exclusions |
| --- | --- | --- |
| Baseline freeze time | Wall time from initiating the CLI subprocess until it returns after writing the first baseline | Initial dependency installation, source checkout and authoring cases |
| Repeat check time | Wall time for a new AEA subprocess to run all 12 cases and compare with its baseline | An engineer interpreting the report or creating cases |
| Median / p95 | Median of observed repeat check durations; p95 is the **nearest observed rank** | Not a service SLO or stable tail-latency estimate with only 2-3 repetitions |
| Regression detection | Controlled bad agent exits 1, names a known defective case and retains the original baseline | Unknown faults or general detection sensitivity |
| Stability | Number of repeated unchanged evaluations that exit 0 without unexpected regression | Real model nondeterminism, provider timeouts and rate limiting |

The timing includes Python interpreter startup, imports, agent and model-double execution, scoring, report writing, process scheduling, and local disk I/O. The scenarios are **not workload matched**. Do not infer that one framework is faster from these figures. GitHub Actions runners have variable contention; record Python version, OS, repeat count and full job URL with any result.

## How to measure engineering productivity later

No percentage improvement is claimed until an actual comparison study is performed. Use an independent engineer and the **same** agreed test tasks for both approaches.

1. Freeze the task description in advance: connect one existing agent, author a fixed number of cases, execute passing and deliberately defective variants, capture actionable failure evidence. Record the repository revision, case list and strict start/stop conditions.
2. Define a credible control workflow without AEA (current manual testing or the team's existing framework). It must detect and explain the *same* deliberately introduced faults. An unfair uninstrumented control cannot be counted as equivalent coverage.
3. Use an engineer who has not built AEA. Ideally counterbalance execution order between at least two engineers to reduce learning effects; capture failed attempts, support time and environmental blockers.
4. Record **observed** first-report setup minutes, mapping effort, case-authoring minutes, execution time, errors found, false positives, rerun reliability and report interpretation. Preserve itemised timings, not a single self-reported estimate.
5. Calculate improvements only for directly comparable tasks: `100 * (control_minutes - aea_minutes) / control_minutes`, requiring a positive control time. Report the sample size, per-task results, uncertainty and exceptions. If AEA finds more defects but takes longer, describe that trade-off rather than forcing a speedup claim.
6. Obtain permission before sharing any internal evaluation data, project names, customer prompts or staff identifiers. Store real adoption evidence in an approved restricted system, not in this public repo.

See [the pilot worksheet](PILOT_EVIDENCE_TEMPLATE.md) and [open approval gate](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111).

## Limitations and pass criteria

The current engineering benchmark is considered technically complete only when **both** synthetic applications freeze a 12/12 passing baseline, pass all unchanged comparisons, detect the expected injected fault with CLI exit 1, and retain unchanged baseline bytes. Nonzero exit codes for intentionally broken agents are expected test evidence.

When presenting results to leadership, distinguish **observed local execution costs** from **unmeasured human productivity**. Never invent time saved, model-token costs, client adoption or production security clearance. The default AEA redaction retains some case/tool identifiers and file paths, so review generated files before sharing.

Run the separate [adversarial resilience checks](RESILIENCE.md) for safety under corrupted inputs, concurrent writes and partial failures. These are correctness gates, not throughput benchmarks.
