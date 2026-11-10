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

The recording's **Security notes** section (approximately source lines 113–126) identifies the following concrete trust boundaries:

- Agent references (`--agent module:function`), scorer references (`--scorer module:function`) and LangGraph `--input-map`/`--output-map` references are imported and **executed** in the current Python process. They are trusted code, not sandboxed plug-ins. Only run references you trust.
- An explicitly supplied `--config FILE` is a TOML document containing import references for `adapter`, `agent`, `input_map` and `output_map`. Configuration is not silently auto-discovered. CLI flags override the file. Missing/invalid TOML, non-UTF-8 input, unknown keys and invalid reference values produce configuration errors before run-directory creation.
- A custom scorer receives each sample's `TaskState` before redaction and can inspect the completion, messages and metadata. It can also make network or filesystem calls. Scrubbing afterwards does not protect against a malicious scorer.
- Dataset contents are data, not code, but may cause a trusted agent to invoke real tools. Treat datasets as trusted inputs where tools have real-world effects.
- `tracing.py:configure_tracing` sets process-wide environment variables, so other components within that process can inherit those settings.
- The reviewed files do not load provider credentials themselves; framework clients may use environment credentials (for example, AWS credentials for Bedrock). This is not evidence that a custom user agent is credential-safe.
- The CLI failure hint directing users to rerun with `--capture-content` is only an operator suggestion, not an automatic capture or upload.

## 5. Retention

The recorded **Retention** section (approximately lines 98–111) states that AEA does not automatically remove run directories; `JsonlSpanExporter` opens `traces.jsonl` in append mode.

| Artefact | Content by default? | With `--capture-content`? | Retention responsibility |
| --- | --- | --- | --- |
| `runs/<timestamp>/log.json` | No, scrubbed | Yes, full prompts, answers, messages and tool payloads | User manually deletes run directory |
| `runs/<timestamp>/traces.jsonl` | No, redacted spans | Yes, full framework attributes | User manually deletes run directory |
| `runs/<timestamp>/report.md` | No raw payloads, derived from log and traces | Report still derives from the captured data | User manually deletes run directory |
| `baselines/<name>.json` | Depends on whether copied from scrubbed or captured run | May contain full captured content | User; not git-ignored, may be committed |
| `comparison*.md` | Metrics, pass/fail, no content by default | No additional capture setting | User; ignored by default |
| Custom `--runs-dir` outside default patterns | Same as run artefacts | Same as run artefacts | User; may not match git-ignore patterns |

The video recommends deleting an entire run directory (for example, `rm -rf runs/<run-id>`) and choosing a project retention period. There is no built-in clean command. The recorded `.gitignore` excludes `runs/`, `runs-*/` and `comparison*.md`; baselines are committed by design and should contain only intentionally shareable scrubbed logs.

## 6. Residual risks

- Argument hashes in tool metrics are SHA256 of `[name, arguments]`, computed at score time then discarded; the hash does not survive scrubbing. Someone with access to the running process, the original arguments and the scorer's random seed could recompute guesses. The source review calls the risk low when the attacker has no access to the running process; this hash only counts redundant calls within one run.
- Output digest is keyed HMAC-SHA256 with a per-run random key that is never stored. Someone with both a `--capture-content` log and scrubbed log from the same run could match outputs using a digest. The compare warning (`compare.py:compare`) flags when either side was captured. Mitigation: do not commit or share `--capture-content` logs.
- Tool and check names in reports and score metadata are intentionally retained. If a name encodes a sensitive identifier (for example, a customer name as a function name), it appears in logs and reports. Mitigation: use generic names.
- Negative or zero prices: `--input-price` and `--output-price` are parsed as numbers but the recorded review found no further non-negative validation. Negative values can produce negative cost; zero yields zero cost. This can mislead operators but is not in itself a security risk. (Re-check against newer reconstructed runtime separately.)
- `aea init --force` overwrites `agent.py` and `dataset.jsonl` in a non-empty directory without another confirmation beyond explicit `--force`.
- HTML/PDF export (`aea export`, `cli.py:_export`) converts Markdown to HTML or PDF via a headless-browser subprocess (`export.py`). Markdown is parsed to HTML and the renderer is launched with a `file://` URL; exports written by `--output` are not git-ignored automatically. Report content (pass/fail, metrics, explanations) is rendered rather than intentionally executed, but malicious Markdown could embed executable HTML/JS that the browser renders during PDF generation, and the exported file could retain it. The historical command was described as local-only, with no automatic upload or external request made by the export command; this does **not** guarantee arbitrary embedded HTML cannot itself reach external resources. Mitigation: export only Markdown from trusted local runs and baselines.

## 7. Known limits

See [README Known limitations](../README.md#known-limitations); not repeated here.

> **Fidelity boundary:** This is a semantic, evidence-backed partial reconstruction for internal review; original punctuation, rows and section 4/5 details need further direct comparison against the recording.