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
uv lock --check
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

Dependencies are pinned in the committed `uv.lock`, generated with uv 0.10.0. CI checks it without resolving a different version. To update intentionally, run `uv lock --upgrade`, review the lockfile changes, then commit them together with any dependency updates.

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

Use a dedicated baseline directory. An update keeps the previous version in a uniquely named hidden backup folder beside the baseline. A lock prevents simultaneous AEA writers. Run `aea backups local-baseline` to inspect retained previous versions without deleting them. Newly frozen folders have private permissions on POSIX; Windows NTFS ACLs must be reviewed for the deployment. Restore a prior version manually if needed; do not remove a lock unless you have confirmed no update is running.

A run normally creates a JSON evaluation log, `traces.jsonl` and `report.md`. CLI exit codes: `0` success, `1` detected regression, `2` command or run error.

## Example agents

`examples/` includes calculator (Strands and LangGraph), orders (Strands), expense, triage, policy RAG and helpdesk (LangGraph). They use local deterministic model doubles; cloud calls are not required for CI.

All seven offline example scenarios have matching expected outputs under the deterministic model doubles. This does not guarantee behaviour or repeatability with live model providers.

## Quality checks

```sh
uv run --locked python scripts/run_checks.py
uv run --locked python scripts/run_checks.py --slow  # full subprocess and other marked-slow acceptance
uv run --locked python scripts/check_examples.py
uv run --locked python scripts/verify_regression_gate.py
uv run --locked python scripts/check_privacy_e2e.py
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

CI runs supported operating-system and Python combinations without provider credentials or billable model calls.

For a more realistic integration check, see [two standalone application projects](integrations/README.md). They exercise only the published CLI, with independent working directories, synthetic policy data and intentional regressions:

```sh
uv run --locked python scripts/validate_independent_integrations.py --repeats 2
```

These are self-authored test applications, not evidence of independent team adoption.

For repeatable **synthetic performance and regression evidence** (actual CLI wall time and known-defect detection), run:

```sh
uv run --locked python -m scripts.benchmark_agent_evaluations --repeats 3 --output-dir benchmark-evidence
```

See the [benchmark methodology](docs/BENCHMARKING.md). Timings are observed for this local environment only; they are not developer time savings or live-provider performance. The [resilience verification matrix](docs/RESILIENCE.md) documents deterministic tests for simultaneous baseline writers, malformed logs and partial filesystem writes.
See the [developer experience audit](docs/INTEGRATION_DEVELOPER_EXPERIENCE.md) for observed outcomes, configuration examples and remaining onboarding risks.

## Leadership and value assessment

Start with the [leadership showcase](docs/LEADERSHIP_SHOWCASE.md), [evidence-based value assessment](docs/VALUE_ASSESSMENT.md) and [dependency/security self-review](docs/DEPENDENCY_SECURITY_REVIEW.md). These distinguish synthetic engineering results from actual developer time saved, independent adoption and production security approval.

The locked package source/hash inventory can be checked without external APIs:

```sh
uv run --locked python scripts/dependency_inventory.py
```

This command does **not** scan published vulnerability advisories or verify licences. The separate observational [PR #124 public-advisory scan](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43627751480) returned zero known findings for 116 exported packages; [security review](docs/DEPENDENCY_SECURITY_REVIEW.md) explains the unscanned variants and pending approvals.

## Leadership demonstration

Generate a self-contained [local demonstration](docs/DEMO.md) using synthetic
orders and a deliberately defective refund-policy agent:

```sh
uv run --locked python scripts/leadership_demo.py --output-dir demo-output
```

The command preserves the passing baseline and produces an HTML regression report, a Markdown briefing and a machine-readable synthetic evidence summary. Follow the five-minute presenter script in the demo guide.

## Synthetic pilot rehearsal

The [pilot guide](docs/PILOT.md) includes a repeatable Strands and LangGraph baseline/regression rehearsal:

```sh
uv run --locked python scripts/pilot_rehearsal.py --output-dir pilot-rehearsal-output --repeats 3
```

It generates redacted local evidence for both adapters. **It does not constitute independent team adoption or security approval.** Record actual pilot findings using the [blank evidence worksheet](docs/PILOT_EVIDENCE_TEMPLATE.md).

## Security and limitations

Default redaction does **not** guarantee anonymity: case IDs, tool/model names, timing, paths and derived metrics may remain; arbitrary non-root span names are masked by default. `--capture-content` deliberately retains inputs, outputs and tool payloads. Only run trusted agent factories and scorers, since they execute Python code in the current environment.

AEA is a testing toolkit, **not** an agent sandbox, hosting service or cross-provider abstraction. Live model repeatability, deployed LangGraph execution, end-to-end data-retention controls and production adoption are outside the current offline guarantees. Formal client data/security review is required before production use.

See [leadership showcase](docs/LEADERSHIP_SHOWCASE.md), [value assessment](docs/VALUE_ASSESSMENT.md), [release-candidate checklist](docs/RELEASE_CANDIDATE_CHECKLIST.md), [release readiness](docs/RELEASE_READINESS.md), [usage](docs/USAGE.md), [architecture](docs/ARCHITECTURE.md), [security guidance](docs/SECURITY.md), [security review](docs/SECURITY_REVIEW.md), [tests](docs/TESTING.md), [engineering assessment](docs/ENGINEERING_AUDIT.md) and [internal adoption pilot](docs/PILOT.md).
