# Agent Engineering Accelerator (AEA)

**Reconstructed engineering candidate • v2.2.0 interfaces • not production approved**

> This README was written for the **reconstructed application** in November 2026. It is **not a verified transcription of the original README**. The currently available `master` branch contains only a title, but that snapshot **does not establish what the full historical README originally contained**. Historical source fidelity, missing baselines, security review and formal release acceptance are tracked separately. Do not treat a passing CI workflow as approval to publish client data or deploy to production.

AEA is a **local-first evaluation, regression and observability toolkit for existing AI agents**. It is not an agent-building framework or the separate Agentic Engineering Toolkit (AET) scaffolder.

## What it does

| Capability | Why a delivery team would use it |
| --- | --- |
| Dataset-driven evaluation | Exercise defined JSONL cases against a real agent adapter |
| AWS Strands and LangGraph | Evaluate these two frameworks through native integrations |
| Output and tool-use checks | Catch incorrect answers, unexpected tools and control-flow changes |
| Baselines and quality gates | Freeze an intentionally redacted run and fail on regressions |
| Inspect AI and OpenTelemetry | Produce local per-case logs, traces and Markdown reports |
| Judge and pairwise comparison | Run optional golden/reference-free/pairwise judging, including a deterministic offline double |
| Reporting and export | Read generated Markdown and export HTML; PDF requires a supported browser |

The included **offline** agent examples are calculator (Strands and LangGraph), orders (Strands), expense, triage, policy RAG and helpdesk (LangGraph). They use deterministic model doubles for CI; no cloud API account is needed.

## Quick start (Windows PowerShell or Linux)

Requirements: **Python 3.11 or 3.12**, Git, and `uv`. Windows can run this natively: WSL is **not** required. From the repository root on the reconstruction review branch:

```sh
git checkout reconstruction/wip-checkpoint-2026-10-30
python -m pip install uv
uv lock
uv sync --python 3.11 --all-extras --group dev --locked
uv run --locked aea --help
```

The `uv lock` command creates a **new, present-day dependency resolution** from `pyproject.toml`. It is **not** the lost historical `uv.lock`; do not label it as original or count it as recovered source evidence. The CI workflow generates a temporary lock in each job and uploads a short-lived copy as an artifact. If the lockfile is intentionally adopted for the new release, it needs separate provenance review.

If using a Windows virtual environment or PyCharm interpreter, choose the `.venv` Python interpreter created by `uv sync`. No WSL or paid model provider is required for the examples below.

## First offline run

**Strands calculator:** a correctly functioning agent should pass all ten recovered example cases.

```sh
uv run --locked aea run examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --runs-dir runs --max-samples 1
```

**LangGraph triage with custom state:** the TOML file supplies its adapter, agent and input/output mappings. Expect 12 passing cases.

```sh
uv run --locked aea run examples/triage/dataset.jsonl --config examples/triage/aea.toml --runs-dir runs --max-samples 1
```

**Freeze and check a local baseline:** choose a dedicated local baseline directory and review it before copying or sharing. `--update-baseline` refuses explicit captured-content runs.

```sh
uv run --locked aea check examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --runs-dir runs --baseline local-calculator-baseline --update-baseline
uv run --locked aea check examples/calculator/dataset.jsonl --adapter strands --agent examples.calculator.agent:build_agent --runs-dir runs --baseline local-calculator-baseline
```

The CLI returns **0** for success, **1** for a detected regression, and **2** for CLI/run errors. A successful run typically creates an Inspect JSON log, `traces.jsonl` and `report.md` in its run directory.

## Automated reconstruction checks

The new cross-platform dependency workflow **does not use the historical lockfile or historical baselines**. It generates a fresh temporary lock, installs with `--locked`, and runs native offline tests.

```sh
uv run --locked python -m reconstruction_tools.run_integrated_offline_safe
uv run --locked python -m reconstruction_tools.replay_original_ci_example_matrix --scenario all
uv run --locked python -m reconstruction_tools.audit_release_evidence --format markdown
```

The seven-example regression replay uses **disposable** redacted baselines: each example is run twice with its correct agent and once with a seeded regression, with two comparisons. It deliberately preserves one original orders data-vs-rules wording discrepancy and must **not** be mistaken for a recovered historical baseline.

For full source-fidelity and provenance work, see [the recorded video reconstruction audit](reconstruction_audits/2026-11-10_six_new_recordings_fidelity.md) and [the current acceptance/security reassessment](docs/AEA_RECONSTRUCTION_ACCEPTANCE_SECURITY_REASSESSMENT_2026-11-09.md).

## Security and data handling

The default Inspect log redacts prompts, targets, outputs and sensitive trace attributes, **but this is not full anonymisation**: case IDs, tool names, dataset paths and derived metrics may remain. `--capture-content` deliberately retains raw content; **never commit or share captured client traces**. Delete local runs according to your project's retention policy.

Agents, tools, custom scorers and `--input-map`/`--output-map` references execute arbitrary trusted Python code. AEA is **not** a sandbox, a hosted data-protection boundary or a universal cloud-provider abstraction. The offline examples have no provider credentials; never exercise `build_live_agent` in CI or on real customer systems without separate authorisation.

## Current limits and release status

- The reconstruction is functionally tested offline on Windows and Linux with Python 3.11 and 3.12, but has **not** been approved for production.
- **97 of 117** historical paths were recovered at the latest documented checkpoint; historical baseline logs, calculator capture fixtures, original acceptance/security Markdown and original lock/CI path are outstanding. Presence of source files alone does not certify byte identity.
- Original `uv.lock` is unavailable and intentionally **not required** for the modern replacement tests; a generated lock is contemporary dependency evidence, not historical provenance.
- Live-model repeatability, scripted LangGraph interrupt resume, deployed graphs, multi-turn support and latency/cost gating are not fully established capabilities.
- Production security/retention approval and real multi-team adoption metrics remain necessary before release or promotion-related claims.

**Review branch:** `reconstruction/wip-checkpoint-2026-10-30`. The production `master` branch remains separate until explicit release authorisation.

Further reading: [delivery-team handover](docs/AEA_RECONSTRUCTION_DELIVERY_TEAM_HANDOVER_2026-11-09.md), [release-readiness evidence](reconstruction_audits/2026-11-09_release_evidence_readiness.md), and [provisional original acceptance](reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md) / [security-review](reconstruction_drafts/docs_review_video_PROVISIONAL.md) transcriptions.
