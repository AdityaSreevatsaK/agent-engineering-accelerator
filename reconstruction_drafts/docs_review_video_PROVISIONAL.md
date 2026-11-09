# Dependency, security and retention review

> **Provisional video transcription, not byte-for-byte original.** This document recovers the visible headings, boundaries and core factual findings of `docs/review.md.webm`. Original line numbering and some passages remain to be verified. Preserve as a reconstruction draft until the full video/source comparison is complete.

The original review focuses on AEA dependencies, data handling, redaction guarantees, metrics retention and security risks. As shown in the recording, the 2.1.0 LangGraph streaming, subgraph and message collection paths and the three 2.1.0 demo agents (triage, policy RAG, helpdesk) were not reviewed in the original scope; see CHANGELOG.

Scope: `pyproject.toml`, `.gitignore`, `README.md`, `src/agent_accelerator/run.py`, `tracing.py`, `scorers.py`, `adapters/__init__.py`, `dataset.py`, `cli.py`, `stats.py`, `run_metrics.py`, `tool_metrics.py`, `trace_summary.py`, and (for 2.2.0) `config.py` and post-2.1.0 changes to `adapters/langgraph.py` and `adapters/strands.py`. Claims outside the reviewed files are marked unverified.

## 1. Dependencies

Runtime (always installed):

- `inspect-ai`: runner, sample/score model and log format (`run.py:build_task`, `run.py:run_task`, `scorers.py:case_checks`). Replacing it requires an async runner, epoch handling and log format.
- `jsonschema`: `expected_json_schema` check (`scorers.py:run_checks`); replaceable with another Draft-compliant validator.
- `opentelemetry-sdk`: tracer provider and JSONL exporter (`tracing.py:configure_tracing`, `tracing.py:JsonlSpanExporter`). Both frameworks emit OpenTelemetry spans.
- `pydantic`: dataset models `dataset.py:Case` and `dataset.py:Dataset` via `BaseModel`. Inspect AI also depends on it.
- `fsspec`: dataset hash normalisation (`dataset.py:dataset_hash`), imported by Inspect AI.

Optional extras:

- `strands` extra, `strands-agents`: only for `--adapter strands`; lazy-loaded by `run.py:_adapter_solver`.
- `langgraph` extra, `langgraph` and `langchain-core`: only for `--adapter langgraph`.
- `langgraph` extra, `openinference-instrumentation-langchain`: OpenTelemetry spans for LangChain/LangGraph; `OPENINFERENCE_HIDE_*` switches provide redaction, rather than a custom mapping layer.
- `bedrock-langgraph` extra (2.1.0), `langchain-aws`: only for live LangGraph demo factories on Bedrock; unnecessary offline.

Python standard library `tomllib` reads `--config` TOML (Python 3.11 minimum). Development group includes Pyright, Pytest and Ruff; build backend `uv_build`.

Dependency bounds are declared in `pyproject.toml`, with `uv.lock` for exact pinned resolution and SHA256 hashes. Running pip without lock resolution may choose newer allowed versions. The recording also describes `uv export -o requirements.txt` and `pip install -r requirements.txt` for pinning a pip-only install.

## 2. Data stored

Each `aea run` creates `runs/<UTC timestamp>/`, or the equivalent under `--runs-dir`.

- Inspect log JSON: task metadata (dataset path/hash/version, agent, adapter, epochs, config/map references when set), run metadata (run ID, capture mode, max samples, accelerator version), sample IDs, scores, explanations, check results, timing, token usage and model ID.
- Default `run.py:scrub`: replaces input/target with `[REDACTED]`, empties messages/events/attachments/store; retains output model name and only `agent_error`, `usage`, `model_id` from sample metadata. LangGraph interrupted flag and values are removed except for check outcomes and judge not-judged reasoning.
- With `--capture-content`, Inspect log retains prompts, targets, outputs, messages, events, tool payloads and (post-2.1.0 LangGraph) JSON-safe interrupt values.
- `traces.jsonl`: append-only OpenTelemetry spans from `tracing.py:JsonlSpanExporter`. Content attributes are disabled and error text redacted by default; full framework attributes appear with capture enabled.
- `report.md`: generated Markdown summary, metrics and trace summary, derived from log/traces and holding no more than the unsanitised inputs.
- Baselines: user-copied logs, conventionally `baselines/<name>.json`. Baselines are not git-ignored and may be committed.
- Network: offline `mockllm/model` makes no model call; any outbound traffic from a custom agent/tool is outside the review and not verified.

## 2a. Metric storage (v1.2)

Metrics are derived, not raw content: reliability statistics (`stats.py`), per-epoch performance (`run_metrics.py`), tool-use metrics (`tool_metrics.py`), and trace summaries (`trace_summary.py`).

Per-epoch metadata surviving scrub includes:

- `output_digest`: 64-bit-truncated HMAC-SHA256 from a per-run random key. Key generated at scorer initialisation and never stored. Digests compare outputs within a run, not across runs.
- `tool_names`: names only; no arguments or results.
- `tool_results`, `tool_errors`, `redundant_tool_calls`: counts. Errors are statuses, not content. Redundant calls identified by a SHA256 hash of `[name, arguments]` computed and discarded during scoring.
- `tool_precision` and `tool_recall`: per-epoch ratios when expected tools are declared, not identities.
- `checks`: per-check pass/fail and explanation, with expected/actual payloads redacted.
- Judge metadata: mode (golden, reference-free, pairwise), criteria, human label, extra key names, error types, not-judged reasoning and pairwise verdict/disagreement. Full answers and extra values are retained only with capture enabled.

Derived post-run but not logged: confidence intervals, pass@k, Fisher and McNemar p-values, bootstrap intervals, tool-use aggregates and trace summaries. Digests/argument hashes cannot be reversed, but log owners with both a captured and scrubbed version of the same run could match outputs. Tool/check names can still carry user-supplied sensitive words.

## 3. Redaction guarantees and their limits

Scrubbed by default (no `--capture-content`):

- Sample input, target, messages, output text, events, attachments, store and case metadata (including LangGraph config).
- LangGraph interrupt values and interrupted flag (except through permitted check/not-judged outcomes).
- Exception message and traceback; agent error reduced to exception type.
- Score answers in sample scores and redactions.
- Expected and actual output values and expected tool arguments in check messages, replaced with `[redacted]` or omitted.
- Span status descriptions and `exception.message`/`exception.stacktrace` attributes.
- Sensitive `gen_ai.*` attributes and OpenInference inputs, outputs, messages, tool definitions and invocation parameters.
- Without capture, Inspect logs use an in-memory filesystem with realtime logging disabled; only scrubbed output is written to disk. Abruptly killing a live run could leave only redacted traces.
- Custom scorers' `answer`, `explanation` and metadata are removed in scrubbed sample scores; `case_checks` keeps its own redacted explanation.
- JSON schema failures retain schema location/validator but not output path/message.

Intentionally kept: pass/fail, check names/results, timing, token usage, model ID, tool names, exception types, sample IDs/epochs, dataset path/hash, agent reference, and optional config/input/output mapping references.

Not protected:

- `--capture-content` runs store unsanitised logs and traces.
- Custom tool/check names or identifiers that themselves encode sensitive content.
- Custom agent/network behaviour, arbitrary user source code, untrusted report exports.

## 4. Security notes

The original recording reviews local reference loading/imports, report/export behaviour, filesystem boundaries, tool metadata, privacy and injection risks. These are historical review findings rather than proof of present security of the reconstructed package.

## 5. Retention

Logs and traces are stored locally under a run directory; baselines copied to the repository may be committed. The review does not describe an automatic data expiration/retention service. Treat retention, sharing and deletion of captured content as operator responsibilities.

## 6. Residual risks

- Argument hashes in tool metrics are SHA256 of `[name, arguments]` at score time, then discarded; a user with original arguments and scorer seed might compare guesses, though the seed is in-memory and changes per run.
- Output digest is HMAC-SHA256 with a per-run random key. An attacker with both captured and scrubbed logs for the same run could match outputs by digest. Do not commit or share `--capture-content` logs.
- Tool and check names remain in reports and score metadata; choose generic names if identifiers could be sensitive.
- `--input-price` and `--output-price` are not type-validated beyond numeric parsing; negative prices give negative cost. This is misleading but not a security risk.
- `aea init --force` overwrites `agent.py` and `dataset.jsonl` in a non-empty directory without another confirmation beyond explicit `--force`.
- HTML/PDF export renders Markdown through a headless-browser subprocess. Exported files are not gitignored. A malicious Markdown report could contain executable HTML/JS; export only reports generated from trusted local runs and baselines.

## 7. Known limits

See [README Known limitations](../README.md#known-limitations); not repeated here.

> **Fidelity boundary:** This is a semantic, evidence-backed partial reconstruction for internal review; original punctuation, rows and section 4/5 details need further direct comparison against the recording.