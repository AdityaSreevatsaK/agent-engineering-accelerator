# Changelog

## Unreleased (development branch, 2026-11-14)

These engineering changes are present on `dev` and are **not** proof of a published package, production approval, or independent team adoption.

- Regression gates now validate finite thresholds and errored epochs; JSON Schema expectations are validated before agent execution. Comparison/statistics checks use independently specified synthetic cases instead of missing fixed-reference logs.
- Default Inspect log scrubbing removes arbitrary custom score values; default OpenTelemetry exports suppress dynamic span names and custom payload attributes. Baseline replacement refuses clearly unredacted or explicitly captured Inspect logs. Identifiers and other metadata still require data governance review.
- Multi-epoch provider-reported token totals and estimated total evaluation cost are distinct from normalised single-pass estimates; missing usage is not silently assumed to be zero.
- Baseline updates preserve existing versions, use cooperative locks and rollback; newly frozen copies use owner-only POSIX file modes. New `aea backups BASELINE` inventories retained copies without deleting them. Windows ACLs and retention policy remain outstanding.
- Module/function reference validation fails before creating runs for malformed agent, mapping and scorer references, with clearer working-directory diagnostics and preserved import-error compatibility.
- Two self-contained synthetic Strands and LangGraph integrations exercise separate application directories, local `aea.toml` settings, deliberate defects, baseline integrity and regression detection. A separate repeatable pilot rehearsal and blank independent-team evidence worksheet are included.
- Full CLI integration acceptance now uses fresh, disposable synthetic reference logs with two declared injected failures. Non-slow CLI tests join the complete unit matrix; the release checks run marked-slow CLI and framework integration tests. All remaining slow unit modules are being added to this explicit acceptance gate.
- Fresh wheel validation exercises the installed `aea` CLI, templates, HTML escaping and read-only backup discovery. See [technical release-candidate checklist](docs/RELEASE_CANDIDATE_CHECKLIST.md).

## 2.2.0 (2026-10-25)

- `--config FILE` on `aea run` and `aea check`: a flat TOML file with `adapter`, `agent`, `input_map` and `output_map`. Explicit only (no auto-discovery); a command-line flag wins over the file, the file over the default; refs still import from the current directory. An unknown key, a non-string value, an unknown adapter, a ref without `:`, invalid TOML, a non-UTF-8 file or an unreadable path exits 2 before a run directory is created. `examples/triage/aea.toml` and `examples/expense/aea.toml` added.
- Run provenance records `input_map`, `output_map` and `config` when set (omitted otherwise).
- LangGraph: the values passed to `interrupt()` are stored in sample metadata `interrupts` (values only, JSON-safe with `repr` as the fallback), kept only with `--capture-content`. Every interrupt is kept when parallel nodes interrupt in the same step. Scoring and the judge still read only `interrupted`.
- Fix: tool error status when calls reuse an id, in both adapters: the nth call with an id now gets the nth result with that id, instead of every call getting the last result's status.
- Fix (policy_rag demo): a question that starts with the answer header no longer raises; a request must start with the header followed by `Question: `.
- helpdesk demo dataset checks facts (ids, times, figures, usernames) and bans made-up details instead of matching the offline double's wording, so live models can pass (Haiku 5.5: 10/10 over 3 epochs, previously 3/10).
- `docs/review.md` and `docs/acceptance.md` updated for 2.2.0; the 2.0.0 verdicts are marked as not re-run.

## 2.1.0 (2026-10-22)

- LangGraph adapter runs any local LangGraph agent: the factory may return a compiled graph (any `Pregel`, including `@entrypoint`) or an uncompiled `StateGraph`, which the adapter compiles; anything else, including deployed graphs, fails with "not a local LangGraph graph; deployed agents are not supported".
- Runs stream `values` and `updates` with subgraphs, so tool calls inside subgraphs and worker graphs reach the trajectory checks; messages are collected from every state key (unwrapping `Overwrite`) and de-duplicated by message id, by tool call id when one copy is id-less, and by object identity, so usage is counted once.
- Each case attempt gets a fresh `thread_id`, so graphs compiled with a checkpointer run unchanged; an optional per-case `config` dataset field is merged into `configurable`.
- Answer read from, in order: `--output-map module:function`, `structured_response` (JSON), the last AI message's text (content blocks joined, not their repr); a graph that adds no AI message is an agent error "no answer produced". `--input-map module:function` builds the input for graphs without a `messages` channel; both flags are LangGraph-only (exit 2 otherwise).
- `interrupt()` is detected: the answer is empty, the sample is marked interrupted, and the new optional `expect_interrupt` dataset field is scored as its own check (an unexpected interrupt fails). The judge skips interrupted samples (`not judged: interrupted`); reports count them separately from agent errors. Dataset format stays version 1.
- `bedrock-langgraph` extra (`langchain-aws>=1.7.9,<1.8`) for live LangGraph agents on Bedrock.
- Three demo agents, each with an offline model double, a planted regression caught by `aea check`, a baseline and a CI check: `examples/triage/` (custom state, router, input/output maps), `examples/policy_rag/` (agentic RAG with a retriever ToolNode and grade/rewrite loop), `examples/helpdesk/` (supervisor with worker subgraphs, checkpointer and an approval `interrupt()`). Their live factories (`build_live_agent`) run on Bedrock without a `temperature`, which Claude Haiku 5.5 rejects.
- Conformance suite `tests/conformance/` runs 13 offline graph shapes through the real solver and CLI in CI.
- `aea run` and `aea check` print a hint on stderr to rerun with `--capture-content` when cases fail.
- README: running an agent from outside the repo, `aea check --update-baseline` as the baseline workflow, `ToolNode(messages_key=...)` for custom state, exact `expected_tool_calls` matching rules, no config file yet.

## 2.0.0 (2026-10-20)

- LLM judge scorer: `aea run ... --judge MODEL` adds the `judge` scorer; golden mode (`--golden FILE`) judges each case with a reference answer against that answer, reference-free mode judges every case against rubric criteria alone (`--judge-rubric FILE` or the built-in rubric), and pairwise mode (`--judge-baseline RUN`) judges each case's answer against the baseline run's answer for the same case (better, worse or same). Judge model runs at temperature 0; `mockllm/aea-judge-double` gives a deterministic offline double.
- Golden and reference-free judging see the agent's tool results in a fenced `TOOL_RESULTS` block (capped at 20,000 characters with an explicit truncation line), so facts from tools count as supported; the LangGraph and Strands adapters now add each tool result to the sample's messages, which the scrub removes. Judge prompt version 2. Pairwise does not include tool results yet.
- A bad `--golden` or `--judge-rubric` file now exits 2 before any runs directory is created, for `aea run` and `aea check`.
- Judge scorer handles model call failures and unparseable replies as judge errors (counted per epoch and shown in the report's Judge section); accepts and reports extra keys in the judge's reply beyond the expected verdict and reason fields.
- Run report gains a `Judge` section when `--judge` is used: judge mode and model, judged case count, judge pass rate, judge error count, criteria verdict distribution (golden and reference-free), human-label agreement and Cohen's kappa (golden with labelled cases; needs at least 10 comparable labels, shown otherwise as undefined or suppressed with a reason), and pairwise answer comparisons with order-disagreement count. Plain-English readings interpret the kappa band, label agreement and disagreements.
- Pairwise judge asks twice with the two answers swapped; a verdict that changes with the order is recorded as `same` (the order decided it, not the content). Pairwise mode warns when the baseline run's dataset hash differs from the current dataset's. Baseline run must have been captured with `--capture-content` (answers are scrubbed otherwise).
- Judge reasons and the full answers are content: kept only with `--capture-content`, redacted from scrubbed logs. Without `--capture-content`, only the verdict structure (mode, model, criteria, label, error flags, pairwise verdict, order disagreement) is stored.
- Reports gain plain-English readings: sentences interpreting figures for readers unfamiliar with the statistics, added after each figure (Wilson intervals, pass@k, pass^k, percentiles, comparison statistics, judge calibration, kappa bands), and a `Glossary` section defining every statistical term used. Readings avoid overclaiming and flag weak evidence (few epochs, wide intervals, small samples).
- `aea export REPORT [--format html|pdf] [--output PATH]`: exports a Markdown report to a self-contained HTML file or PDF; the built-in converter HTML-escapes all text, and PDF is printed through a headless Chromium browser. Export keeps heading links and status cells no-wrap, and handles identifier underscores in titles and Markdown edge cases.
- `examples/expense/`: LangGraph expense-claim reviewer with a simulated model double, 12-case dataset, trajectory checks, the `amounts_grounded` custom scorer, `golden.jsonl` reference answers with human labels for five cases, a baseline run, and a `README.md` demonstrating a prompt regression caught by `aea check`. Judge double demo shows golden calibration (5/5 agreement on the original agent), reference-free mode, pairwise baseline comparison with order swapping, and the regression (3 newly failing cases in golden mode, caught by the pairwise judge).
- Runtime dependencies capped below the next major version (for example `inspect-ai>=0.3.278,<0.4`, `pydantic>=2.14.1,<3`); README gains wheel install instructions.
- Kappa minimum counts only labelled cases with a comparable verdict (both judge and human label are pass or fail, not error or no-verdict); cases where the judge errored or was not asked, or the human label is absent, are excluded from the kappa calculation and the N shown.
- Readings corrected for edge cases: gaps rounded to keep plain-language claims true, zero-latency tails, tie wording, small-sample and single-run phrasing, singular epoch and try grammar, never-passed labels.
- Report shows pass@k and pass^k only when k > 1 (suppressed at one epoch per case).
- Export fixes: emphasis (`*text*`, `**text**`) kept out of Markdown link URLs, closing `#` hashes require a space before them to avoid ID collisions, identifier underscores preserved in titles.

## 1.2.0 (2026-10-16)

- Run report gains `Performance and cost` (latency and token percentiles per case-epoch, cost per case and per passing case), `Failures` (failing epochs by check name) and `Consistency` (output agreement across epochs, from a keyed output digest that `case_checks` now records in score metadata) sections.
- Trajectory checks, each scored on its own: `expected_tools`, `tool_order` (relative order, other calls may interleave), `forbidden_tools`, `max_tool_calls`, `expected_tool_args` (subset match on some call). Read from agent messages, not traces; argument values shown only with `--capture-content`.
- Report case table gains a `Tool calls` column (per-epoch average; `n/a` for logs that predate it).
- `examples/orders/` uses the new checks on four cases; `baselines/orders.json` regenerated.
- Example `examples/expense/` (LangGraph): expense-claim reviewer with a prompt-reading model double, `PROMPT` and `PROMPT_CONDENSED`, a 12-case dataset, the `amounts_grounded` scorer and a five-step `aea check` demo; baseline `baselines/expense/`, checked in `scripts/ci.sh` and the CI workflow.
- `examples/expense/` dataset checks the trajectory on all 12 cases (`expected_tools`, `forbidden_tools`, `expected_tool_args`, `max_tool_calls`); baseline refreshed.
- Run report gains a `Reliability` section when cases ran over several epochs: mean pass@1, pass@k and pass^k (k = fewest epochs any case ran), and per-case pass rates with 95% Wilson intervals.
- `aea compare` and `aea check` run a one-sided Fisher exact test on each shared case whose epoch pass share fell, and on all shared cases pooled; p <= 0.05 warns, and opt-in `--max-p-value ALPHA` makes p <= ALPHA a regression. Skipped (with a warning if the flag is set) when either run has one epoch per case.
- Comparison report gains an informational `Statistics` section: pass rate over cases with 95% Wilson intervals, the pass-rate change with a 95% Newcombe interval, an exact McNemar p on paired case outcomes (works at one epoch), and median per-case latency and token change with a seeded 95% bootstrap interval. No new gates.
- Run report gains a `Tool use` section when any case called a tool: call volume (total, mean/median/max per case-epoch, calls per tool), tool-error rate, redundant calls (same name and arguments earlier in the epoch, compared by a score-time hash) and macro tool-selection precision/recall against `expected_tool_calls`/`expected_tools`. Recorded in `case_checks` score metadata as names and counts only; adapters add a per-call `tool_errors` list.

## 1.1.0 (2026-10-14)

- `output_not_contains` check: case-insensitive substrings that must not appear.
- `aea run --scorer module:function` (repeatable) adds custom Inspect scorers; a case passes only if all pass.
- `aea check DATASET --baseline DIR [--update-baseline]`: run, then compare against a baseline run directory (or freeze the run as the baseline); same flags and defaults as `run` and `compare`.

## 1.0.0 (2026-10-13)

First complete release. Local only.

- `aea run | compare | report | init`: run an agent against a JSONL dataset, score it deterministically, compare against a baseline, exit on regression.
- Adapters for Strands and LangGraph, on dataset and baseline work across both.
- Checks: exact or normalised output, contains, JSON schema, tool calls (exact or subset arguments, order, extras).
- Repeated runs for live models: `--epochs`, `--min-case-pass-rate`, flaky-case warnings; `--max-samples` caps concurrency.
- OpenTelemetry traces to `traces.jsonl` and a framework-neutral trace summary in the report.
- Token usage per case and run; optional estimated cost from user-supplied `--input-price` and `--output-price`.
- Payloads not stored by default: logs scrubbed (including custom scorer fields), exception text redacted, unscrubbed logs never written to disk; `--capture-content` opts in.
- `aea init DIR` scaffolds an agent and dataset from a packaged template.
- Examples: calculator (Strands, LangGraph, live Bedrock), orders (Strands, chained tools).
- Docs: README guide for testing your own agent; `docs/review.md` for dependencies, data retention and security.
