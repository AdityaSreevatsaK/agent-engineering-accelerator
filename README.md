# Agent Engineering Accelerator (AEA)

Local-first evaluation, regression testing and observability for **existing AI agents**.

AEA runs JSONL evaluation datasets against Python agent factories and produces Inspect AI logs, Markdown reports and OpenTelemetry trace summaries. It supports AWS Strands and LangGraph. Local deterministic examples require no model-provider account.

## Capabilities

| Capability | Description |
| --- | --- |
| Evaluation | Validate expected answers, JSON schemas, tool calls, ordering, arguments and interrupts |
| Framework adapters | AWS Strands and local LangGraph graphs, including custom state input/output mappings |
| Regression checks | Compare runs with frozen baselines, quality thresholds and statistical tests |
| LLM judging | Optional reference-based, rubric-based and pairwise judging; offline judge double for testing |
| Observability | Token usage, tool metrics, run latency and OpenTelemetry trace summaries |
| Reports | Markdown and self-contained HTML; PDF requires Edge, Chrome or Chromium |
| Privacy | Prompts and output payloads are redacted by default; explicit opt-in capture is available |

## Requirements

Python **3.11 or 3.12**, Git and [uv](https://docs.astral.sh/uv/). Windows, macOS and Linux can use native Python environments.

From the project root:

```sh
python -m pip install uv
uv lock
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

The lock is generated from the current project dependencies. Use your team's own approved dependency-pinning process for releases.

## Quick start

Run the offline Strands calculator example:

```sh
uv run --locked aea run examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --runs-dir runs --max-samples 1
```

Run a LangGraph example using TOML configuration:

```sh
uv run --locked aea run examples/triage/dataset.jsonl --config examples/triage/aea.toml --runs-dir runs --max-samples 1
```

Freeze a local, redacted baseline, then check for regressions:

```sh
uv run --locked aea check examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --baseline local-baseline --runs-dir runs --update-baseline
uv run --locked aea check examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --baseline local-baseline --runs-dir runs
```

Use a dedicated baseline directory. An update keeps the previous version in a uniquely named hidden backup folder beside the baseline. A lock prevents simultaneous AEA writers. Restore a prior version manually if needed; do not remove a lock unless you have confirmed no update is running.

A run normally creates a JSON evaluation log, `traces.jsonl` and `report.md`. CLI exit codes: `0` success, `1` detected regression, `2` command or run error.

## Example agents

`examples/` includes calculator (Strands and LangGraph), orders (Strands), expense, triage, policy RAG and helpdesk (LangGraph). They use local deterministic model doubles; cloud calls are not required for CI.

All seven offline example scenarios have matching expected outputs under the deterministic model doubles. This does not guarantee behaviour or repeatability with live model providers.

## Quality checks

```sh
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/check_examples.py
uv run --locked python scripts/verify_regression_gate.py
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

CI runs supported operating-system and Python combinations without provider credentials or billable model calls.

## Security and limitations

Default redaction does **not** guarantee anonymity: case IDs, tool names, span names, timing, paths and derived metrics may remain. `--capture-content` deliberately retains inputs, outputs and tool payloads. Only run trusted agent factories and scorers, since they execute Python code in the current environment.

AEA is a testing toolkit, **not** an agent sandbox, hosting service or cross-provider abstraction. Live model repeatability, deployed LangGraph execution, end-to-end data-retention controls and production adoption are outside the current offline guarantees. Formal client data/security review is required before production use.

See [usage](docs/USAGE.md), [architecture](docs/ARCHITECTURE.md), [security guidance](docs/SECURITY.md) and [contributing/tests](docs/TESTING.md).
