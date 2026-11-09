# Acceptance criteria for Agent Engineering Accelerator v2.2.0

> **Provisional video transcription, not a byte-for-byte original.** The full recorded document extends to at least line 154. This file preserves high-confidence sections and decisions visible in `docs-acceptance.md.webm`; portions not yet transcribed are explicitly omitted. Do not promote to the original historical path until compared with the recording.

Version: 2.2.0 (released 2026-10-25; content checked at commit 164abd0). Statuses in sections 1 to 5 were assessed 2026-10-19 against commit ff49879 for 2.0.0 and were not re-run for 2.2.0; evidence was updated against the code on 2026-10-25. Section 2a covers 2.1.0 and later and is backed by the `scripts/ci.sh` run noted there.

Criteria derived from confirmed decisions (D1-D22) and agreed scope in `C:\ASK - C Drive\Repos\Information for Claude\agent-engineering-accelerator\decisions.md`.

## Status key

- **Met**: implemented and verified
- **Partly met**: implemented but with known gaps or limitations
- **Not met**: deferred, blocked, or not implemented

## 1. Confirmed decisions

| ID | Decision | Status | Video-evidenced implementation |
| --- | --- | --- | --- |
| D1 | First framework is AWS Strands with a simple tool-calling task | Met | `src/agent_accelerator/adapters/strands.py`, `examples/calculator/` |
| D2 | Reference tool is a deterministic calculator | Met | `examples/calculator/agent.py:calculate`, `examples/calculator/rules.py` |
| D3 | Offline deterministic execution is required; real-model smoke run is optional | Met | `run.py:run_task` uses `mockllm/model`; live model support via `--epochs` and real credentials |
| D4 | Prompt, input and output payloads are not persisted by default; explicit opt-in capture | Met | `run.py:scrub` redacts by default; `--capture-content` flag skips scrub |
| D5 | Baseline comparison and a seeded regression are in the first vertical slice | Met | `aea compare`, exit code 1 on regression; `tests/unit/test_compare.py` |
| D6 | Curated dataset of about 8–12 cases instead of 30 | Met | Calculator 10 cases, orders 11, expense 12; 2.1.0 adds triage 12, policy RAG 11, helpdesk 10 |
| D7 | Adopt OpenTelemetry for execution traces from the start | Met | `tracing.py:configure_tracing`, `opentelemetry-sdk` |
| D8 | Prefer self-contained local trace files | Met | `tracing.py:JsonlSpanExporter` writes local `traces.jsonl`, no collector |
| D9 | Latency and cost initially informational, with blocking thresholds only after repeatability measurement | Partly met | Latency, token and cost metrics implemented in `run_metrics.py` and reports; no blocking gates |
| D10 | OpenTelemetry spans separate from versioned run/case evaluation, linked by run ID | Met | `traces.jsonl` separate from Inspect log JSON, linked by run directory and sample ID |
| D11 | Each run records provenance: dataset hash, config hash, source revision if available, runtime/library versions | Met | `dataset.py:dataset_hash`, run metadata and `--config`/mapping references in task metadata |
| D12 | Use existing tools where they meet the need | Met | Inspect AI runner and log store |
| D13 | Sole developer; reuse proven by a second materially different agent | Met | Calculator, orders and expense; 2.1.0 adds triage, policy RAG and helpdesk |
| D14 | Develop with Claude Code; spike in hours, MVP in 2–3 days | Not applicable | Historical project schedule |
| D15 | Inspect AI as runner and log store; DeepEval dropped | Met | `inspect-ai` dependency; no DeepEval references |
| D16 | Inspect logs scrubbed unless `--capture-content` | Met | `run.py:scrub` redacts inputs, targets, messages, output, events, attachments, store |
| D17 | LangGraph traces via OpenInference instrumentation rather than custom mapping to `gen_ai` | Met | `openinference-instrumentation-langchain` extra, `tracing.py:configure_tracing` |
| D18 | Exception messages and tracebacks redacted without opt-in | Met | `run.py:scrub`, `scorers.py:error_type`, `tracing.py:_redact_errors` |
| D19 | Live-model support through repeats (`--epochs N`) and `--min-case-pass-rate` | Met | Case pass threshold and flaky warnings, reporting |
| D20 | Dataset hash normalises CRLF to LF | Met | `dataset.py:dataset_hash`, tests verify CRLF/LF agreement |
| D21 | `--max-samples` caps concurrency and is recorded in run metadata | Met | CLI and `run.py:build_task` |
| D22 | Common trace shape is report-level summary, not rewriting the trace file | Met | `trace_summary.py:summarise_traces`, report includes a trace summary |

## 2. Agreed scope

The recorded table marks the following as **Met**:

- One Strands tool-calling example, calculator, with a committed baseline.
- JSONL dataset format (`id`, `input`, `target`, etc.).
- Deterministic evaluators for expected output, expected tools/tool calls, forbidden substrings, expected JSON schema, trajectory checks.
- Structured case results and aggregate results with Wilson intervals and pass@k upper bounds.
- Local OpenTelemetry traces in `traces.jsonl`.
- Markdown reports with plain-language summary, reading guidance and glossary.
- HTML/PDF export via `aea export`.
- LLM judge with golden, reference-free and pairwise modes and deterministic `mockllm/aea-judge-double`.
- Baseline comparison with CI exit statuses 0/1/2.
- Setup, trace-limit, retention and framework-gap documentation.
- JSONL and Markdown preference; SQLite and UI deferred.
- Retrieval/citation evaluation deferred; pattern catalogue, model-provider abstraction and benchmark percentage target deferred.

## 2a. Additions since 2.0.0 (2.1.0 and 2.2.0)

The video states these are not decisions from `decisions.md`; they record implemented capabilities verified using `scripts/ci.sh` on 2026-10-25. Visible additions include:

- Local LangGraph adapter accepts compiled `Pregel`, `@entrypoint` and uncompiled `StateGraph`, but rejects deployed graphs.
- Custom state via `--input-map` and `--output-map` only with LangGraph.
- Interrupts detected, scored by `expect_interrupt`, and excluded from judging.
- Interrupt values in sample metadata, scrubbed unless `--capture-content`; all parallel interrupts retained as of 2.2.0.
- Tool-error pairing when call IDs are reused, in both Strands and LangGraph, as of 2.2.0.
- Run provenance includes `input_map`, `output_map` and `config` when set.
- Explicit `--config FILE` TOML support for adapter, agent, input and output maps. Flags take precedence, invalid file exits 2.
- Three local offline demo agents: triage, policy RAG and helpdesk, including baseline and regression flows.
- Policy RAG accepts questions starting with an answer header.
- Helpdesk dataset facts rather than exact phrasing; live-result trial reported by developer but not re-run for 2.2.0.
- Failure hint on stderr recommends rerunning with `--capture-content`.

## 3. Assumptions and recommendations

- A1 **Met:** Do not build a universal model-provider adapter until reference workflow needs one.
- A2 **Met:** Prefer JSONL/Markdown; add SQLite or UI only if demonstrated need.
- A3 **Met:** Token and cost fields distinguish unavailable (`None`) from zero.
- A4 **Met:** Offline path exercises real Strands integration with deterministic model double; live credentials permitted separately.
- A5 **Met:** Version dataset/result schemas and document versioning; no v1.x migration tooling needed.

## 4. Open items from decisions.md

- O1 **Met:** Real offline Strands instrumentation/model double and observable spans.
- O2 **Met:** Local OpenTelemetry exporter and error redaction.
- O3 **Met:** Concrete dataset, Inspect log, comparison and scorer schemas.
- O4 **Met:** Baseline selection and regression semantics with failure, pass-rate and error-rate checks.
- O5 **Met:** Repository, Python >=3.11, uv, Ruff, Pyright, Pytest, CI workflow recorded but not executed on remote.
- O6 **Not applicable:** Benchmark deliberately deferred.
- O7 **Met:** Second adapter and use cases; Strands and LangGraph verified.

## 5. Commands (CLI completeness)

| Command | Video-recorded status | Evidence |
| --- | --- | --- |
| `aea init` | Met | `cli.py:_init`, agent/dataset templates and `test_init.py` |
| `aea run` | Met | `cli.py:_run`, dataset execution, log/trace/report and explicit `--config` |
| `aea compare` | Met | `cli.py:_compare`, regression exit 1 |
| `aea report` | Met | `cli.py:_report` |
| `aea check` | Met | `cli.py:_check`, runs then compares |
| `aea export` (HTML/PDF) | Met | `cli.py:_export` and `export.py` |

## 6. Test coverage (unit tests only; integration/E2E out of scope)

Recorded unit-test coverage addresses datasets, scorers, comparison and statistics, report/reading, export, CLI, init, adapters, run_task, traces and privacy, judge and pairwise judge. **The precise original table rows are not fully transcribed here.**

## 7. Known not-met items (explicitly deferred or blocked)

- CI workflow has not been executed on a remote: no remote available in original assessment.
- Live-model repeatability measurement not conducted; latency/cost metrics remain informational, with no `--max-latency` or `--max-cost` gates.
- Multi-turn cases not implemented; datasets hold a single input and target per case.
- Generic framework adapter beyond Strands and LangGraph deferred.
- LangGraph interrupt resume and deployed graphs unsupported; `interrupt()` ends the case without scripted resume.
- Config file covers four settings only (`adapter`, `agent`, `input_map`, `output_map`); other flags still passed on CLI.

### Further details visible in the recorded deferred-items table

The recording's original section 7 (approximately lines 137–147) distinguishes the following cases:

| Item | Recorded constraint | Stated mitigation or plan |
| --- | --- | --- |
| Remote CI | Historical local-only repository had no git remote; original workflow existed as a template but had never run remotely | Push to a remote, execute the workflow, and review resulting failures |
| Live-model repeatability | D9 needs repeated live-model runs and provider access to measure variance | Latency and cost remain informational; no blocking `--max-latency` or `--max-cost` gates |
| Multi-turn cases | The dataset schema represents a single input/target per case | Explicitly deferred beyond 2.2.0 |
| Additional framework adapter | Only Strands and LangGraph supported; `adapters/__init__.py:load_factory` is a factory-loader, not a universal framework API | Deferred |
| LangGraph interrupt resume and deployed graphs | `interrupt()` ends the evaluation case and `expect_interrupt` checks the stop; there is no scripted resume | Unsupported in 2.2.0 |
| Configuration file coverage | `--config` covers only `adapter`, `agent`, `input_map` and `output_map` | Other options remain command-line flags |

This table is a video-grounded transcription aid, not a replacement for the complete historical Markdown table.

## 8. Summary

2.0.0 verdict, not re-run for 2.2.0: commit `ff49879` meets all 22 confirmed decisions except D9 (latency/cost gates), which is partly met. Agreed scope is met, including LLM judge (golden, reference-free and pairwise), HTML/PDF export, plain-language report guidance, and Cohen's kappa calibration. Explicitly deferred: CI workflow execution (blocked by no remote) and multi-turn cases.

The tool was considered feature-complete for its stated v2.0 scope: offline deterministic evaluation, live-model repeats, judge modes, baseline regression statistics, reporting, export, redacted logs/traces and custom scorer extensibility.

2.2.0 (`master` at `164abd0`, unreleased): section 2a additions were implemented and passed `scripts/ci.sh`; the prior decision and scope verdicts carried forward from 2.0.0; CI was still never run on a remote in that historical assessment.

> **Fidelity boundary:** This is a semantic, evidence-backed partial reconstruction for internal review, not the exact historical Markdown or a new verification of 2026 runtime outcomes.