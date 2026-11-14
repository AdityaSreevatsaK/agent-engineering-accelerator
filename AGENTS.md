# AGENTS.md: Complete Project Guide for AI Coding Agents and Engineers

> **Purpose:** A durable, high-context guide for anyone or any AI coding agent who is asked to understand, maintain, extend, test, demonstrate or assess the Agent Engineering Accelerator (AEA). Read this file first, then inspect the actual implementation and tests before changing behaviour.
>
> **Source of truth:** The checked-out Python implementation, tests, `pyproject.toml`, `uv.lock`, and GitHub Actions are authoritative. This document describes the architecture and intended contracts as implemented on the maintained development branch. If code changes, update this guide in the same change.
>
> **Current release posture:** The local-first implementation has verified offline quality gates and is suitable for a controlled internal pilot using approved synthetic data. It is **not** certified for confidential production workloads, all live model providers, or independent multi-team adoption.
>
> **Branch rule:** `dev` is the integration branch. `master` is the default branch and must not be changed, reset, rebased, or promoted without the repository owner's explicit release approval.

---

## 1. Project identity, problem and value proposition

**Project name:** Agent Engineering Accelerator, abbreviated **AEA**.

**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`.

**Python distribution:** `agent-accelerator`, currently declaring version `2.2.0` in `pyproject.toml`.

**Python import namespace:** `agent_accelerator`.

**Command-line executable:** `aea`, registered as `agent_accelerator.cli:main`.

**The problem:** Engineering teams can build agents in frameworks such as AWS Strands or LangGraph, but often lack a reusable, objective way to answer:

- Did a code, prompt, tool, model or orchestration change make our agent worse?
- Which exact expected answers, tool selections, arguments or ordering requirements failed?
- Is the failure repeatable across several executions or specific to one run?
- Can we keep an approved baseline and reject known regressions in CI?
- What happened during a run, how long did it take, and what metrics can safely be reported?
- Can an independent engineer evaluate an existing agent without rebuilding that agent in an evaluation framework?
- Can a team gather credible evidence of improved test quality and developer productivity?

**AEA's answer:** Provide a local-first CLI and Python library which accepts an agent factory plus JSONL evaluation cases, wraps the agent in an Inspect AI task, evaluates answer and tool contracts, records execution metrics and OpenTelemetry traces, optionally adds LLM-as-judge scoring, and compares new runs with an approved baseline.

**Primary users:**

1. Engineers maintaining existing agent workflows.
2. Technical leads reviewing the quality of agent changes.
3. AI platform/tooling engineers adding shared validation to delivery projects.
4. CI maintainers creating offline regression gates.
5. Technical stakeholders evaluating whether a reusable engineering asset deserves broader adoption.

**Intended organisational impact:** Faster onboarding into agent evaluations, earlier detection of behavioural changes, comparable quality evidence, less duplicated evaluation infrastructure, and adoption across separate delivery teams. These are *desired outcomes*, not measured achievements. The proposed measurements live in `docs/PILOT.md`.

**Critical distinction:** AEA **evaluates existing agents**. It is not an agent creation framework, multi-provider infrastructure abstraction, autonomous deployment platform, managed observability service or security sandbox. Model/provider selection normally remains inside the supplied agent factory.

---

## 2. Read these files in this order

When starting an unfamiliar task, read the narrowest relevant implementation, but use this orientation sequence for a general assessment:

1. `README.md`: scope, setup, supported capabilities, local examples and links.
2. `pyproject.toml`: packaging, Python requirements, optional integrations, formatting rules.
3. `docs/ARCHITECTURE.md` and this file: component boundaries and data flow.
4. `src/agent_accelerator/cli.py`: command surface and orchestration control flow.
5. `src/agent_accelerator/dataset.py`: validated case schema.
6. `src/agent_accelerator/run.py`: Inspect task construction and default data protection.
7. `src/agent_accelerator/adapters/`: Strands and LangGraph behavioural bridges.
8. `src/agent_accelerator/scorers.py` and `tool_metrics.py`: deterministic contract evaluation.
9. `src/agent_accelerator/compare.py`, `stats.py`, `report.py`, `readings.py`: regression interpretation.
10. `src/agent_accelerator/baseline.py`: safe baseline update and retention.
11. `src/agent_accelerator/tracing.py` and `trace_summary.py`: trace collection and minimisation.
12. `src/agent_accelerator/judge.py` and `judge_double.py`: optional judge modes.
13. `scripts/run_checks.py`, `scripts/check_examples.py`, `scripts/verify_regression_gate.py`: test acceptance.
14. `scripts/check_privacy_e2e.py`, `scripts/check_distribution.py`: privacy/package gates.
15. `.github/workflows/ci.yml`: required automated verification matrix.
16. `docs/ENGINEERING_AUDIT.md`, `docs/SECURITY_REVIEW.md`, `docs/RELEASE_READINESS.md`, `docs/PILOT.md`: explicit limitations, independent hardening evidence and adoption requirements.
17. `docs/DEMO.md` and `scripts/leadership_demo.py`: local leadership demonstration.

**Do not infer a capability solely from a README statement.** Verify the corresponding runtime path and tests, especially where optional agents, model providers, metrics, data handling or security are involved.

---

## 3. Architecture at a glance

```text
                         Existing application code
                         (Strands or LangGraph)
                                   |
                              agent factory
                            module:function
                                   |
              +--------------------+------------------+
              |  CLI: aea run / aea check / aea compare |
              +--------------------+------------------+
                                   |
              validated JSONL cases + optional TOML settings
                                   |
                        dataset.py -> run.py
                                   |
                     Inspect AI Task / MemoryDataset
                                   |
                     framework-specific Solver
                     /                     \
              adapters/strands.py     adapters/langgraph.py
                     \                     /
                       normalised output:
              answer + tool calls + errors + usage
                                   |
                      scorers.py (case_checks)
                      optional custom scorers
                      optional judge.py scorer
                                   |
                    Inspect AI evaluation/log
                                   |
                  run.py: default content scrub
                                   |
           +-----------------------+----------------------+
           |                       |                      |
      evaluation log          traces.jsonl            report.md
      Inspect JSON           OpenTelemetry            report.py
           |                       |                      |
           +----------+------------+----------------------+
                      |
            compare.py + stats.py
                      |
           baseline versus current
                      |
             comparison.md
                      |
                export.py
               HTML / PDF
```

Cross-cutting responsibilities:

- `cli.py` validates user intent, executes runs, selects command results and maps them to exit codes.
- `dataset.py` validates structured case expectations.
- The adapters translate framework messages, tool activity, usage and errors to a common Inspect-compatible representation.
- `tool_metrics.py` captures safe, aggregatable tool metrics.
- `tracing.py` must initialise instrumentation **before** framework imports.
- `baseline.py` isolates high-risk baseline file operations.
- `readings.py` adds restrained plain-English interpretation to numerical reports.
- `scripts/` and the CI workflow make the above behaviour testable without paid LLM calls.

---

## 4. What AEA does and does not own

| Concern | Owned by AEA | Owned by agent/application |
| --- | --- | --- |
| JSONL case validation | Yes | Supplies relevant cases |
| Test-run orchestration | Yes | Supplies an importable factory |
| Agent business logic | No | Yes |
| Prompt design | No | Yes |
| Tools, functions and backends | No | Yes |
| Framework selection | Adapter choice | Agent implementation |
| Provider/model credentials | No | Yes, through approved environment/secrets |
| Expected answers and tool trajectories | Validation logic | Application team defines expectations |
| Optional LLM judge prompts and score parsing | Yes | Chooses approved judge/model and criteria |
| Run logs, metrics and reports | Yes | Reviews and stores them safely |
| Baseline comparison and quality thresholds | Yes | Approves reference baseline/thresholds |
| Production hosting/deployment | No | Yes |
| Customer-data classification and retention | No | Organisation and owning team |
| Team productivity/adoption evidence | Measurement framework | Pilot team provides observed data |

The supported adapters are **Strands** and **local LangGraph**. Optional dependencies exist for these integrations, and an additional optional LangGraph/Bedrock dependency group is declared. That optional extra does not mean AEA provisions Bedrock, credentials or infrastructure.

---

## 5. Repository map and responsibility by module

### 5.1 Core package

| Path | Responsibility | Typical change reason |
| --- | --- | --- |
| `src/agent_accelerator/cli.py` | Argument parsing, command routing, run/check/compare/report/export, exit semantics | New safe CLI option, control-flow fix |
| `config.py` | Explicit TOML configuration loading and validation | Add or validate supported settings |
| `dataset.py` | Versioned, strict Pydantic JSONL case format | Add expectation type or schema validation |
| `run.py` | Build Inspect tasks, execute evaluation, scrub default log content | Modify evaluation lifecycle or privacy boundary |
| `scorers.py` | Case answer and tool-contract scoring | New deterministic assertion |
| `tool_metrics.py` | Tool counts, ordering/selection measurements, error and redundancy metrics | New safe tool telemetry |
| `run_metrics.py` | Latency/token/cost/failure/consistency readings | New informational performance metric |
| `compare.py` | Load run results, classify case transitions, decide regressions | New threshold or changed gate semantics |
| `stats.py` | Pure reliability and significance maths | Statistical correctness |
| `readings.py` | Explain run/comparison figures without overclaiming | Reporting language improvements |
| `report.py` | Markdown run and comparison reports | New report sections |
| `export.py` | Escaped HTML and browser-backed PDF output | Safe presentation/export |
| `baseline.py` | Validated staging, cooperative lock, prior snapshot preservation and rollback | Baseline correctness/safety |
| `tracing.py` | OpenTelemetry span export and content minimisation | Framework instrumentation/privacy |
| `trace_summary.py` | Framework-neutral trace summaries | Additional trace interpretation |
| `judge.py` | Golden, reference-free and pairwise judging | Judge prompt/score/metrics change |
| `judge_double.py` | Deterministic offline judge model for tests | Non-billable judge test coverage |
| `adapters/__init__.py` | Safe import of `module:function` factories | Factory validation |
| `adapters/strands.py` | AWS Strands adapter to Inspect solver | Strands-specific interaction |
| `adapters/langgraph.py` | Local LangGraph adapter, state mapping and interrupts | LangGraph-specific interaction |
| `template/` | Bundled starter `agent.py` and `dataset.jsonl` | Fresh-project onboarding |
| `py.typed` | Marks import package as typed | Packaging/type checking |

### 5.2 Examples

| Example directory | Purpose |
| --- | --- |
| `examples/calculator/` | Small Strands and LangGraph deterministic agent; also illustrates a live-agent alternative that must not be enabled in ordinary CI |
| `examples/orders/` | Strands order-service cases; includes a deliberately faulty variant for a reliable regression demonstration |
| `examples/expense/` | LangGraph expense decisions, policy/referral rules and domain-specific scoring |
| `examples/triage/` | LangGraph routing workflow and TOML configuration |
| `examples/helpdesk/` | Helpdesk flow with tool use and reference cases |
| `examples/policy_rag/` | Local policy lookup and RAG-oriented checks |

Examples are **illustrative engineering contracts**, not evidence that those scenarios satisfy any real client's domain requirements.

### 5.3 Tests, CI and supporting scripts

- `tests/unit/`: focused tests for virtually every core component and example.
- `tests/conformance/`: local LangGraph conformance cases, including non-standard state and tool/interrupt handling.
- `tests/fixtures/`: minimal synthetic test assets.
- `tests/conftest.py`: test fixture definitions and slow-test selection.
- `scripts/run_checks.py`: controlled offline unit selection, temporary synthetic fixture generation, explicit exclusions and inventory completeness check.
- `scripts/make_test_log.py`: generate a disposable Inspect AI log in the format expected by selected unit tests.
- `scripts/check_examples.py`: seven full deterministic CLI smoke scenarios; `--quick` for short jobs.
- `scripts/verify_regression_gate.py`: approved baseline, matching agent, intentionally broken agent, and baseline-integrity assertions.
- `scripts/check_privacy_e2e.py`: synthetic sentinel against both adapters, with explicit-capture control.
- `scripts/check_distribution.py`: isolated wheel installation and CLI-template/export checks.
- `scripts/leadership_demo.py`: generate a locally viewable, reproducible demonstration.
- `scripts/check_repository_hygiene.py`: fail if retired process-only artefacts or wording return to tracked source.
- `scripts/ci.sh`: local command helper.
- `.github/workflows/ci.yml`: matrix/verification gates.

---

## 6. CLI commands and their meaning

The CLI executable is defined in `pyproject.toml`. The parser and exit logic live in `src/agent_accelerator/cli.py`.

### 6.1 `aea init`

```sh
uv run --locked aea init new-agent-folder
```

Creates a starter agent factory and JSONL dataset from packaged templates. `--force` is available, but the implementation contains path and symlink safeguards. Do not weaken the requirement to avoid accidentally writing through linked directories or overwriting unrelated user data.

### 6.2 `aea run`

```sh
uv run --locked aea run examples/calculator/dataset.jsonl \
  --adapter strands \
  --agent examples.calculator.agent:build_agent \
  --runs-dir runs \
  --max-samples 1
```

On Windows Command Prompt, enter as a single line rather than using the Unix line-continuation characters.

It validates cases, imports the agent factory, executes the Inspect task, scores output, records traces, writes an Inspect JSON log and `report.md`, and prints a case-by-case summary.

**Important:** a *successfully completed evaluation* can contain failed quality cases and still return exit code 0 for `aea run`. To enforce a regression gate, use `aea check` or `aea compare`.

### 6.3 `aea check`: freeze a baseline

```sh
uv run --locked aea check examples/calculator/dataset.jsonl \
  --adapter strands \
  --agent examples.calculator.agent:build_agent \
  --baseline local-baseline \
  --runs-dir runs \
  --update-baseline
```

The baseline directory must be dedicated to AEA. Update mode rejects opt-in content capture, symlink traversal, unrelated files and unsafe overlapping run directories. It stages and validates the candidate, coordinates with other AEA writers using a local exclusive lock, and retains the earlier version in a sibling backup directory. Backups require an explicit retention process.

### 6.4 `aea check`: compare with a baseline

```sh
uv run --locked aea check examples/calculator/dataset.jsonl \
  --adapter strands \
  --agent examples.calculator.agent:build_agent \
  --baseline local-baseline \
  --runs-dir runs
```

Runs the agent, compares the new run with the frozen baseline, writes `comparison.md`, and chooses a successful/regression/error exit code.

### 6.5 `aea compare`

```sh
uv run --locked aea compare BASELINE_PATH CURRENT_RUN_PATH \
  --max-new-failures 0 \
  --max-pass-rate-drop 0 \
  --max-error-rate-increase 0 \
  --output comparison.md
```

Both positions may reference either an Inspect JSON log or a directory containing exactly one such log. This command does not execute the agent. It loads and compares existing evidence.

### 6.6 `aea report` and `aea export`

```sh
uv run --locked aea report RUN_DIRECTORY
uv run --locked aea export RUN_DIRECTORY/report.md --format html --output report.html
```

`aea report` writes a human-readable Markdown summary to standard output. `aea export` converts a Markdown report to HTML or PDF. HTML is self-contained and escapes raw source text. PDF uses a local Chrome/Edge/Chromium process and is not guaranteed on a machine with no supported browser.

### 6.7 Exit-code contract

| Exit code | Meaning |
| --- | --- |
| `0` | Command succeeded; for compare/check, no configured regression gate was tripped |
| `1` | A comparison or check detected a regression |
| `2` | Usage, validation, execution or another command error |

Do not change these codes without explicit compatibility approval and regression tests. CI depends on them.

---

## 7. Inputs: strict JSONL dataset contract

The dataset format is versioned with `DATASET_FORMAT_VERSION = 1` and implemented using Pydantic in `dataset.py`.

Each non-empty line is one JSON object, validated as a `Case`. Unknown fields are forbidden. A case must have a unique string `id` and an `input` string.

### 7.1 Complete case field map

| Field | Type / default | Semantics |
| --- | --- | --- |
| `id` | Required string | Stable identifier for a test case |
| `input` | Required string | User input supplied to the agent |
| `expected_output` | Optional string | Exact output expectation |
| `output_contains` | Optional list of strings | Substrings required in the output |
| `output_not_contains` | Optional list of strings | Substrings forbidden in the output |
| `expected_json_schema` | Optional JSON Schema object | Expected structured output contract |
| `expected_tool_calls` | Optional list of call specifications | Ordered call/name/argument expectations |
| `allow_extra_tool_calls` | Boolean, default false | Allow additional calls around required ones |
| `expected_tools` | Optional list of names | Each listed tool should occur |
| `tool_order` | Optional list of names | Names must appear in relative order |
| `forbidden_tools` | Optional list of names | None of these tools may be invoked |
| `max_tool_calls` | Optional non-negative integer | Upper bound on tool count |
| `expected_tool_args` | Optional list of tool/argument requirements | A call to the named tool must match provided argument subset |
| `expect_interrupt` | Optional boolean | LangGraph interrupt expectation |
| `config` | Optional object | Per-case LangGraph configurable state |
| `metadata` | Object, default empty | Case-owned extra metadata |

`expected_tool_calls` entries have `name`, `arguments`, and `match` (`exact` or `subset`). `expected_tool_args` entries have `tool` and `args`.

**Critical semantics:**

- A missing expectation means that particular property is not checked.
- `expected_tool_calls: []` means no tool may be called; it does not mean "do not check tools".
- Tool arguments can match exactly or as a subset, as configured.
- `expect_interrupt` is meaningful for supported LangGraph execution.
- IDs must remain stable across baseline/current runs for meaningful pairing.
- Changing the input cases changes the dataset hash and can make comparison results less directly comparable.
- Do not place credentials, secrets, proprietary documents or real client payloads in tracked demo datasets.

### 7.2 Example case

```json
{
  "id": "order-total-001",
  "input": "How much did this customer spend?",
  "expected_output": "The total is 17.50.",
  "output_contains": ["17.50"],
  "forbidden_tools": ["issue_refund"],
  "expected_tools": ["find_customer"],
  "max_tool_calls": 5,
  "metadata": {"purpose": "illustrative order total"}
}
```

This is a schema illustration, not a claim that the supplied example agent produces this exact answer. One object should be serialised on a single JSONL line in a real dataset.

### 7.3 Validation invariants

- Use `load_dataset(path)`; do not bypass Pydantic validation. Any `expected_json_schema` must be a valid JSON Schema and is checked before agent execution, not after provider calls.
- Report malformed case data with the file and line number.
- Reject duplicate IDs.
- Keep backward compatibility with dataset-format version 1 unless a deliberate version upgrade is agreed.
- When changing the schema, update `dataset.py`, `scorers.py`, the relevant adapter if needed, all JSONL examples and focused tests.

---

## 8. Adapters: integrating existing agent frameworks

### 8.1 Shared contract

The CLI accepts `--agent module:function` and optionally `--adapter strands|langgraph`. The factory is imported from Python code, and the adapter executes it within an Inspect AI solver. The agent's implementation, prompts, tools and provider integration remain separate.

Do not assume that an arbitrary object implementing `invoke()` is sufficient for both adapters. Their accepted runtime types and output handling are framework-specific.

### 8.2 Strands adapter

Implementation: `src/agent_accelerator/adapters/strands.py`.

The factory returns a new AWS Strands `Agent` for each invocation. The adapter uses a framework-specific execution path and extracts:

- Final response text.
- Tool calls and their argument dictionaries.
- Tool completion/error signals.
- Optional usage and model metadata.
- Trace spans identifying the case.

Important tests: `tests/unit/test_adapters.py`, `tests/unit/test_run_task.py`, calculator/order smoke checks.

Do not enable the example's live-provider factory in no-cost CI. Run provider-specific validation only when explicitly authorised.

### 8.3 LangGraph adapter

Implementation: `src/agent_accelerator/adapters/langgraph.py`.

The factory must return a local LangGraph `Pregel` or a supported `StateGraph` that can be compiled. The adapter supports common message-based state and optional custom mappings for graphs with a different state schema.

Options:

- `--input-map module:function`: convert a case question to the graph's input dictionary.
- `--output-map module:function`: convert the final graph state into an answer string.
- Dataset `config`: per-case values merged into the graph's `configurable` execution settings.
- `expect_interrupt`: verify expected pause/interrupt behaviour.

The adapter also reconstructs tool messages and failure indications for scoring, with careful handling of LangChain message representations and tool-call identities.

Important tests: `tests/unit/test_langgraph_adapter.py`, `tests/conformance/test_conformance.py`, calculator LangGraph and triage smoke checks.

**Non-goal:** This implementation does not claim compatibility with every deployed graph runtime, remote graph endpoint, custom streaming transport or provider integration. Validate an unusual graph locally before asserting support.

### 8.4 Adding another framework

A new adapter is a significant extension, not an alias:

1. Define a clear accepted agent factory protocol and lifecycle.
2. Map the framework's answer, tool trajectory, exceptions, usage, interrupts and trace attribution.
3. Keep Inspect AI solver output consistent with current scoring assumptions.
4. Ensure default trace and log privacy.
5. Add test doubles, unit tests and end-to-end cases.
6. Add the dependency as an optional extra, not a mandatory cloud dependency.
7. Update the CLI adapter choices and config validation.
8. Preserve existing Strands/LangGraph behaviour, exit codes and baseline compatibility.
9. Never put paid model calls in CI.

---

## 9. Evaluation lifecycle, scoring and artifacts

### 9.1 How a run is executed

1. `cli.main()` parses flags and merges explicit TOML config.
2. The CLI validates prices, optional judge settings and basic paths.
3. The CLI allocates a new timestamped run directory.
4. `configure_tracing()` initialises OpenTelemetry **before framework imports**.
5. `build_task()` loads JSONL cases and constructs Inspect `Sample` objects.
6. The selected adapter wraps the application factory as an Inspect solver.
7. The default `case_checks`, custom scorers and optional judge are attached.
8. Inspect executes the task, including epochs/concurrency settings.
9. The run log is either explicitly captured or scrubbed before disk write.
10. Tracing shuts down and buffered spans are flushed.
11. The CLI loads results, creates `report.md`, prints summary/case lines and returns a code.
12. For `check`, it either safely updates a baseline or writes `comparison.md`.

Maintainers should preserve this ordering. Importing a framework before configuring tracing can invalidate redaction or instrumentation assumptions.

### 9.2 Deterministic scorer

`scorers.case_checks` validates the optional expectations present in each case and returns an Inspect `Score`. Relevant checks include:

- Answer equivalence and substring constraints.
- JSON Schema shape.
- Required, forbidden and ordered tool calls.
- Argument equality/subset requirements.
- Maximum tool-call count.
- Interrupt expectation.
- Aggregated errors and explanations.

Repeated `--scorer module:function` flags attach additional Inspect scorers. A case passes only when the applicable scorers pass. The scorer pipeline is an evaluation contract, not an alternative to user-facing business rules.

### 9.3 Tool behaviour and metrics

`tool_metrics.py` computes tool-use information from recorded calls:

- Number of calls and tool errors.
- Required-tool selection recall/precision where expectations exist.
- Redundant/repeated call information.
- Per-case and per-run aggregations.

Argument data are processed into safe hashes at score time rather than preserved as raw payload metrics. This is **data minimisation**, not an anonymity guarantee.

### 9.4 Multiple epochs

`--epochs N` executes each case multiple times. A case passes when its pass share meets `--min-case-pass-rate`, whose default is 1.0. An epoch with a recorded execution error counts as failed even when another scorer previously returned `CORRECT`. A case passing some but not all epochs is classified as flaky.

Metrics distinguish case counts from epoch counts. Do not sum per-epoch passes and present that as the number of passing unique cases.

`--max-samples` controls concurrency. Low values are useful when measuring live provider latency honestly and avoiding excessive load.

### 9.5 Standard outputs

| Output | Source | Content |
| --- | --- | --- |
| Run directory | `run.new_run_dir()` | Timestamped evaluation folder |
| Inspect JSON | `run.run_task()` | Case scores and permitted metadata |
| `traces.jsonl` | `tracing.py` | OpenTelemetry spans, minimised by default |
| `report.md` | `report.py` | Run summary, cases, failures, tool/latency/token readings |
| `comparison.md` | `cli._check()` | Baseline/current changes and regression verdict |
| HTML | `export.py` | Escaped self-contained report |
| PDF | `export.py` | Browser-rendered report requiring supported Chromium |

These are local files. AEA does not automatically apply an organisation's access controls, retention schedule or encrypted storage.

---

## 10. Baseline and regression correctness

### 10.1 Terminology

- **Baseline:** An approved prior evaluation run used as a reference.
- **Current run:** A newer evaluation being assessed.
- **Newly failing:** A case that passed in the baseline and fails now.
- **Newly passing:** A case that failed before and passes now.
- **Still failing:** A case that failed in both.
- **Added:** A new case ID absent from the baseline.
- **Removed:** A baseline case ID absent from the current dataset.
- **Regression:** A condition that crosses an active configured quality threshold.
- **Warning:** Informational concern that does not automatically block CI.

### 10.2 Default gating

`compare.py` constructs `Thresholds` with defaults:

- `max_new_failures = 0`
- `max_pass_rate_drop = 0.0`
- `max_error_rate_increase = 0.0`
- `max_p_value = None` (statistical significance gate is opt-in)

The comparison engine also treats a non-successful current run status as a regression condition when comparing existing completed logs.

Dataset changes, removed cases, capture warnings and some statistical observations are warnings, not always blocking conditions. Report users must read both sections.

**Important:** Statistical intervals do not automatically create a regression. Do not accidentally make informational findings into new gates unless the CLI contract and tests intentionally change.

### 10.3 Statistical evidence

`stats.py` and `compare.py` cover:

- Wilson intervals for pass-rate uncertainty.
- Newcombe intervals for current-minus-baseline pass-rate change.
- Exact McNemar test on cases shared by two runs.
- Per-case and pooled one-sided Fisher tests where repeated epochs allow them.
- Deterministic bootstrap confidence bounds for paired median latency/token differences.
- `pass@k`, `pass^k` and Cohen's kappa for appropriate reliability/judging views.

The Fisher `--max-p-value` gate is opt-in, applies only when both runs supply sufficient repeated epochs and uses a strict interpretation of the supplied alpha. Warnings may be displayed with a conventional reference level independently of gating.

The bootstrap uses a fixed seed and fixed number of resamples, so the same logs generate reproducible figures.

Avoid interpreting observed statistical significance as proof of causal model quality or production reliability.

### 10.4 Baseline update safety

`baseline.py` contains deliberately defensive file operations:

1. Validate the destination path before starting the evaluation.
2. Reject capture-enabled baseline updates.
3. Revalidate after evaluation and after taking the cooperative writer lock.
4. Stage a validated new snapshot on the same filesystem.
5. Move an existing baseline to a uniquely named retained backup.
6. Switch in the new version using a directory rename.
7. Attempt rollback if activation fails.
8. Preserve prior data if an unrelated external writer races the update.
9. Never recursively delete an existing baseline as part of the update.

Caveats:

- The active baseline may be briefly absent during rename.
- The lock only coordinates tools that follow AEA's local lock convention.
- A process crash can leave a stale lock requiring operator inspection.
- Backups are retained, not automatically expired.
- Do not try to "simplify" this into `rmtree(old); copytree(new)`.

Tests: `test_baseline_replacement_safety.py` and `test_baseline_transaction.py` cover hostile paths, changed targets, rollback, lock contention and data preservation.

---

## 11. Optional judging: what it really means

Implementation: `judge.py` with a deterministic `judge_double.py` for local tests.

AEA offers three broad judgement modes:

1. **Golden-reference:** Compare the agent answer with a supplied reference for a matching case ID.
2. **Reference-free:** Assess an answer against configured rubric criteria without a case-specific reference.
3. **Pairwise:** Compare the new answer against one from a prior *captured* baseline; answer order is swapped to reduce position bias.

Related flags: `--judge MODEL`, `--golden FILE`, `--judge-rubric FILE`, `--judge-baseline RUN`.

Judge configuration and files are validated before the evaluation as far as practical. Judgement failures, parse errors and interruptions have explicit score/error handling. The judge stores provenance and safe score metadata for reporting.

**Privacy warning:** External LLM-as-judge calls transmit material to the selected judge model, even if AEA later redacts local logs. Default log redaction is not consent for sending customer material to a third-party provider. Use mock/double judging in CI and obtain provider/data approval before any real judge call.

**Quality warning:** A passing judge score does not prove factual correctness; test with calibrated cases, human labels and known adversarial examples. Pairwise comparison can still be biased and provider-dependent.

---

## 12. OpenTelemetry and privacy boundaries

### 12.1 What is minimised by default

`run.scrub()` replaces or clears typical payload-bearing fields including:

- Sample question/input and target answer.
- Agent messages and output text.
- Structured events, attachments and state stores.
- Unsafe arbitrary scorer explanations, metadata and free-form score values; standard categories and numeric grades are retained.
- Error text and tracebacks that might quote prompts.
- Duplicate content carried in scorer reductions.

`tracing._redact_errors()` minimises unexpected span attributes, exception descriptions and non-exception event fields. It preserves only fields needed by summary logic when capture is disabled.

`trace_summary.py` reduces Strands and LangGraph span conventions to a common view. **Trace statistics are informational; scoring and comparison do not read traces as an oracle.**

### 12.2 What may still identify data or people

Even default logs/traces can contain:

- Case IDs and names.
- Agent/tool identifiers, span names or model identifiers.
- Relative paths or configuration provenance.
- Timings, token counts, tool counts and run metadata.
- Derived scores and error-type information.

Never describe default output as fully anonymised, universally safe to publish or automatically compliant with a customer's security policy.

### 12.3 Explicit capture

`--capture-content` intentionally stores prompts, output, tools and other evaluation content in the run artefacts. It is for approved local debugging, not routine shared CI. Such logs may be sensitive; do not commit or upload them.

The project includes `scripts/check_privacy_e2e.py`: a synthetic private sentinel is tested end-to-end with both adapters in default mode; opt-in capture is also checked using a temporary directory.

### 12.4 Execution trust boundary

User-supplied factory references and scorers import and execute **Python code**. An untrusted factory may access the local filesystem, environment and network. AEA is not a Python sandbox or process security boundary.

### 12.5 Security review still needed

See `docs/SECURITY_REVIEW.md`. A passing synthetic sentinel check is useful but does not establish:

- Enterprise-wide data-loss prevention.
- Confidential-production approval.
- Complete identifier anonymisation.
- Remote provider permissions or network egress policy.
- Dependency vulnerability/licence acceptance.
- Backup retention compliance.

---

## 13. Reports, metrics and cost interpretation

`report.py` generates Markdown based on `RunResults`, tool metrics, available traces and optional judging. `readings.py` adds restrained plain-English context: what passed, what failed, where tool use was unusual, what the median figures mean, and when uncertainty prevents a strong conclusion.

`run_metrics.py` calculates:

- Latency distribution and observed percentile values.
- Token usage when the adapter/provider emits usage records.
- Estimated cost from **caller-supplied prices**.
- Failure causes, check failures and output consistency metrics.

**Cost caveat:** `--input-price` and `--output-price` are specified in **USD per million tokens**. The cost figure is an *estimate* derived from reported usage and the prices supplied by the caller. It is not an actual invoice, and usage can be unavailable. Do not insert invented model prices or claim currency conversion is performed automatically.

`export.py` supports a deliberately constrained Markdown-to-HTML path with escaping. Do not replace it with raw HTML insertion of report content. Browser-backed PDF output has an external local browser requirement; it is not a cloud conversion service.

For any new report metric:

1. Define measurement semantics and missing-data handling.
2. Provide a corresponding unit test, including absent/partial metadata.
3. Confirm no payload-bearing data is retained by default.
4. Explain whether the value is informational or part of a regression threshold.
5. Keep `readings.py` explanations appropriately qualified.

---

## 14. Local setup and reproducibility

### 14.1 Requirements

- Python 3.11 or 3.12 for the supported CI matrix.
- Git.
- `uv` (CI uses version 0.10.0).
- Optional browser for PDF export.
- No Docker, WSL or paid model API required for the maintained offline examples.

The project declares `requires-python >=3.11`, but the verified CI matrix is 3.11 and 3.12. Do not imply every newer Python runtime has been tested.

### 14.2 Installation

```sh
uv lock --check
uv sync --all-extras --group dev --locked
uv run --locked aea --help
```

The committed `uv.lock` is part of the reproducibility contract. Prefer locked commands. Do not regenerate the file during routine CI. To update dependencies intentionally, modify the project requirements, run an approved `uv lock --upgrade`, examine the resolved changes and rerun the entire quality matrix.

### 14.3 Windows-specific notes

Native Windows with Python and `uv` is a supported target. Use PowerShell, Command Prompt or a Windows IDE terminal. Commands with Unix-style backslash continuation must be converted to a single line on Command Prompt. Bash helper scripts may require a compatible shell; core Python commands do not.

For a clean setup on a Windows laptop, prefer native Python and `uv` before introducing WSL.

### 14.4 Isolated package installation

```sh
uv build --wheel
uv run --locked python scripts/check_distribution.py
```

The distribution smoke expects a single wheel in `dist/`; do not leave multiple competing build artefacts there. It creates a disposable environment and verifies the import location, package metadata, CLI entry point, bundled templates, generated starter and escaped HTML output.

---

## 15. Exactly how quality gates work

### 15.1 Routine unit gate

```sh
uv run --locked python scripts/run_checks.py
```

The script creates a disposable synthetic calculator Inspect log and runs the selected offline unit tests. It checks that every unit-test file is either fully included or explicitly classified. It protects the fixture path against pre-existing files and refuses to delete changed fixture content.

The current project contains a very large collection of parametrised unit tests. **Do not equate a total passing count with proof that every test in the repository ran.** Inspect the runner and pytest summary for deselections.

Known test limitations:

- The independent CLI parser/configuration test groups in `tests/unit/test_cli.py` are selected, but its full integration contract suite is not included because some fixed-reference comparison inputs are absent.
- All comparison/statistics groups are now active using synthetic test oracles. The unavailable archived comparison fixture was not restored.
- The default pytest configuration excludes tests marked `slow`; inspect their purpose before expanding CI time or enabling live execution.

Do not manufacture undocumented reference fixtures simply to turn the test count green. Prefer adding independently checkable synthetic tests with a stated oracle.

### 15.2 Framework conformance

```sh
uv run --locked python -m pytest -q -m "not slow" tests/conformance
```

Validates important LangGraph cases under the local conformance harness. Use this for changes to message translation, state mapping, tool calls and interrupts.

### 15.3 Example CLI smoke

```sh
uv run --locked python scripts/check_examples.py --quick
uv run --locked python scripts/check_examples.py
```

The full suite covers seven deterministic scenarios across the example folders. Tests must remain offline. Do not replace a test with a hardcoded passing result.

### 15.4 Regression detection

```sh
uv run --locked python scripts/verify_regression_gate.py
```

This deliberately:

1. Runs a good local Orders agent.
2. Freezes a baseline and verifies the expected 11/11 tally.
3. Re-runs the same agent and checks for no regression.
4. Runs a known defective refund-policy agent.
5. Asserts exit code 1 and a report naming the affected refund behaviour.
6. Confirms the approved baseline is unchanged.

A green result here demonstrates **detection**, which is stronger than only checking that good agents pass.

### 15.5 Privacy contract

```sh
uv run --locked python scripts/check_privacy_e2e.py
```

The test runs both adapters with a synthetic private marker and verifies default output minimisation, then confirms that intentional capture behaves differently. It uses temporary files and no external model account.

### 15.6 Leadership demonstration

```sh
uv run --locked python scripts/leadership_demo.py --output-dir demo-output
```

Refuses a pre-existing destination. Produces a baseline, current runs, a comparison report, an exported HTML report and a short Markdown summary. The actual demonstration has been exercised by CI. See `docs/DEMO.md`.

### 15.7 Repository and static checks

```sh
uv run --locked ruff check src examples
uv run --locked pyright
uv run --locked python scripts/check_repository_hygiene.py
```

The repository uses Ruff with Python 3.11 target, maximum line length 120, and selected `E`, `F`, `I`, `UP`, `B` rules. Pyright basic-mode checking covers `src`.

### 15.8 GitHub Actions matrix

`.github/workflows/ci.yml` runs:

- Windows, Python 3.11.
- Windows, Python 3.12.
- Ubuntu, Python 3.11.
- Ubuntu, Python 3.12.
- Full offline example suite, dependent on the matrix.
- Offline regression/privacy/demo/wheel acceptance suite, dependent on the matrix.

**All six jobs must succeed before merging changes to the integration branch.** The existing CI deliberately clears common provider credentials and checks the committed dependency lock.

---

## 16. How to change the code safely

### 16.1 General development contract

1. Check the current `dev` head and any open PRs.
2. Read the affected source, adjacent files and related tests.
3. Write down the exact observed issue and expected behaviour.
4. Implement the smallest meaningful change.
5. Add a regression test that fails before the fix where practical.
6. Run focused tests, static checks and the relevant end-to-end gate.
7. Run the full Windows/Linux CI before merging.
8. Do not merge a failing or incomplete check just to move forward.
9. Keep `master` unchanged until explicit release approval.
10. Delete superseded topic branches after merge, without deleting unmerged work.
11. Update documentation and this file when a contract or architecture boundary changes.

### 16.2 Modification matrix

| Proposed work | Read first | Tests to run |
| --- | --- | --- |
| Add JSONL expectation | `dataset.py`, `scorers.py`, example cases | Dataset/scorer/unit tests, example smoke |
| Change Strands behaviour | `adapters/strands.py`, tracing | Adapter tests, Strands smoke, privacy gate |
| Change LangGraph behaviour | `adapters/langgraph.py`, config, tracing | Adapter tests, conformance, LangGraph smoke, privacy gate |
| Change baseline publishing | `baseline.py`, `cli._validate_baseline_target` | Both baseline safety suites, CLI regression gate |
| Modify thresholds | `compare.py`, `stats.py` | Comparison, statistics and CLI threshold tests |
| Add judge capability | `judge.py`, `judge_double.py` | Judge parsing, pairwise, offline judge tests |
| Modify reports/export | `report.py`, `readings.py`, `export.py` | Report/export/privacy/wheel tests |
| Modify model usage/cost | `run_metrics.py`, adapter usage extraction | Metrics tests, missing-data tests |
| Change packaging | `pyproject.toml`, `uv.lock` | Lock check, wheel build and installed-package smoke |
| Change CI | `.github/workflows/ci.yml`, `scripts/` | Observe fresh CI run with all required jobs |

### 16.3 Coding guidelines

- Keep imports lazy where framework integration requires tracing to be initialised first.
- Prefer typed, explicit pure functions for metrics and statistics.
- Preserve stable case IDs, score keys and CLI exit codes unless deliberately versioned.
- Avoid introducing filesystem side effects while importing modules.
- Keep error paths deterministic and report actionable errors without leaking private payloads.
- Do not retain raw tool argument bodies in default score metadata.
- Preserve strict schema validation and fail closed for unsafe file paths.
- Use temporary directories in tests and refuse to overwrite unrelated user files.
- Never turn an optional cloud dependency into a required default dependency without review.
- Ensure output remains usable on Windows and Linux.
- Write British English in user-facing project documentation.
- Use independent expected values for tests; do not just assert that a function equals itself.

### 16.4 AI coding agent-specific constraints

An AI agent working in this repository must:

- **Inspect before editing.** Do not assert what a function does solely from its name.
- **Remain within the authorised branch.** No force pushes or default-branch changes without approval.
- **Preserve the no-paid-CI invariant.** Never add credentials, provider keys or billable judge execution to CI.
- **Protect user data.** Never print real secrets, place sensitive logs in source control or share captured output as demonstration evidence.
- **Keep test gaps visible.** Do not hide failures through new exclusions without a documented, reviewable reason.
- **Separate observation from assumption.** Treat clean local tests as local evidence, not all-provider validation.
- **Preserve working functionality.** New functionality requires backward-compatibility checks.
- **Keep PRs narrow.** Prefer small independently testable changes.
- **Avoid self-declared production readiness.** Independent security and pilot evidence are mandatory.
- **Report exact verification.** State which commit, run and checks passed or failed.

---

## 17. Operational troubleshooting

### 17.1 `uv lock --check` fails

Possible causes: a requirement changed without updating `uv.lock`, a lock generated by a different dependency policy, or an unsupported environment. Inspect `pyproject.toml` and the lock diff. Do not quietly run a fresh unreviewed resolution in CI.

### 17.2 `module:function` cannot be imported

Confirm the module path, Python working directory and callable export. `aea.toml` is only read when `--config` is explicit. A config directory should not silently become part of the Python module search path. Ensure a factory returns the expected framework object.

### 17.3 A LangGraph graph has no normal message channel

Supply explicit `--input-map` and `--output-map`, with functions in an importable module. Validate them through a local conformance example. Do not blindly assume standard `messages` state.

### 17.4 A run returned code 0 but failed cases

That is expected for a completed `aea run`. A run command reports evaluation results. Use `aea check` against a baseline for regression quality gates.

### 17.5 A comparison warns about a changed dataset

Check the JSONL SHA-256 provenance and case IDs. Added and removed cases affect the measured population. Regenerate or approve a new baseline deliberately rather than silently treating the results as directly equivalent.

### 17.6 Too many flaky cases

Increase `--epochs`, inspect per-epoch failures and provider/model variability, and set an intentional `--min-case-pass-rate`. Avoid loosening thresholds merely to make CI green.

### 17.7 The baseline lock remains after failure

Verify that no AEA update writer is active. Inspect the lock and backup paths. Only then decide whether to remove a stale lock. Never delete retained backups reflexively.

### 17.8 Default output may still carry sensitive identifiers

The default privacy check protects a synthetic payload, not every possible sensitive field. Rename sensitive case IDs, avoid customer names in span/tool identifiers, restrict output files and obtain security review for sharing.

### 17.9 PDF export fails

HTML export does not require a browser. PDF does. Check that a supported Chrome, Edge or Chromium executable is installed and available to the exporter.

### 17.10 Wheel smoke finds multiple distributions

The packaging test expects exactly one wheel in `dist/`. Inspect generated artefacts before cleaning them. Use a clean workspace or remove only known, disposable build products.

### 17.11 A new test module fails the inventory check

Update the explicit test-module inventory in `scripts/run_checks.py` and add appropriate fixture-independent tests. Do not suppress the inventory error by broad file ignores.

---

## 18. Leadership demo: what to show and what not to claim

The recommended demo is a **controlled regression** rather than a large architecture diagram alone.

1. Show that the same tool can target existing agent factories.
2. Run the passing Orders dataset, freeze 11/11 as a baseline.
3. Run the unchanged agent and show a successful comparison.
4. Run the deliberately faulty refund variant and demonstrate a detected regression.
5. Open `comparison.md` and the exported HTML report.
6. Explain how the offline CI gate detects the defect automatically.
7. Show the privacy sentinel result and the Windows/Linux CI matrix.
8. Explain the two-team independent pilot rather than claiming it has happened.

Supporting files: `docs/DEMO.md`, `scripts/leadership_demo.py`, `docs/PILOT.md`.

**Supported statement:** "AEA detects this known defect on a deterministic, local agent workflow and produces an actionable regression report."

**Unsupported statement:** "AEA is proven secure for all customer data, works with every provider, saves a measured percentage of development time, or is already adopted by multiple teams."

A strong project presentation distinguishes reusable capability, measured verification and next evidence needed for organisational scale.

---

## 19. Release-readiness criteria and limitations

### 19.1 Automated release checks already available

- Local/offline deterministic evaluation examples.
- Strands and LangGraph adapter smoke coverage.
- Windows/Linux Python 3.11/3.12 tests.
- Conformance and focused unit tests.
- Locked dependency resolution.
- Wheel installation in a disposable environment.
- Deterministic known-defect regression detection.
- Baseline snapshot and rollback tests.
- Synthetic privacy sentinel checks.
- A generated leadership demonstration.

These are tested technical capabilities, not production clearance.

### 19.2 Current explicit gaps

- Full legacy CLI integration test group is not entirely active without its fixed reference assets; selected independent contracts run, and the runner documents remaining gaps.
- Comparison/statistics groups have no explicit exclusions after synthetic replacements. The standalone CLI module is still only partially selected; do not claim its full suite passed.
- Slow tests are not part of the standard quick gate.
- Live model/provider compatibility, availability, network errors, cost and rate limits have not been validated in the offline matrix.
- Real customer-data retention and access controls need independent approval.
- Provider credentials, third-party data transfers and remote judge behaviour need authorisation.
- Multi-team pilot productivity and adoption results remain unmeasured.
- The default branch must not be promoted without explicit release permission.

### 19.3 Proposed release candidate decision

A release candidate may be presented for review once technical CI is green and the maintained documentation is coherent. A **production-approved** or **organisation-wide adopted** release requires separate independent security, live-integration and pilot evidence.

Do not create a release tag or publish packages merely because `pyproject.toml` declares version 2.2.0. Version string, CI status, tag, publication and release approval are different things.

---

## 20. Independent adoption and measurement

`docs/PILOT.md` contains the detailed plan. For reference, the intended pilot is:

- One independently configured Strands application.
- One independently configured LangGraph application.
- Preferably separate delivery teams and engineers who did not author AEA.
- Synthetic or otherwise approved input data only.
- Time-to-first-valid-run and time-to-author-cases recorded.
- Known controlled defects introduced and detected.
- Repeatability, report interpretability and CI stability evaluated.
- No bespoke changes required to AEA's core for each pilot.
- Technical lead and security/release sign-off documented.

Suggested metrics include set-up time, integration hours, case authoring effort, known-defect detection rate and independent team adoption. Targets are hypotheses until observed. Do not include invented gains in READMEs, management presentations or release notes.

---

## 21. Glossary of project terms

**Adapter:** Code translating a particular agent framework's execution into an Inspect solver result.

**Agent factory:** Importable callable such as `package.module:build_agent` returning an agent/graph instance.

**Case:** One unique JSONL evaluation item with an input and optional expected behaviour.

**Case check:** Deterministic scorer built from JSONL expectations.

**Epoch:** One repeated execution of a case; multiple epochs inform flakiness and reliability.

**Inspect AI:** Evaluation engine providing task, solver, scorer and log abstractions.

**Golden answer:** Trusted reference used by an optional judge.

**Reference-free judge:** Rubric scoring without case-specific answer text.

**Pairwise judge:** Judge comparing an old answer with the current one, including order swapping.

**Baseline:** Saved reference run approved for later comparison.

**Regression gate:** Rule which changes a comparison/check exit code when quality declines beyond a configured threshold.

**OpenTelemetry span:** Trace event carrying timing and diagnostic metadata; potentially sensitive.

**Content capture:** Explicit opt-in to retain prompt/output/tool payloads.

**Redaction:** Removal or replacement of certain content fields; not a guarantee of anonymity.

**CI double:** Local deterministic agent or judge behaviour that needs no paid provider.

**Conformance test:** Check that an adapter handles a representative framework execution contract.

**Release candidate:** A build proposed for assessment, not proof of production authorisation.

---

## 22. A practical checklist for the next AI agent session

Before proposing new work:

- [ ] Confirm current `dev`, `master`, open PRs and most recent CI run.
- [ ] Read this guide, README and the requested component.
- [ ] Locate the precise code path, current tests and any known deferrals.
- [ ] Distinguish a defect, missing test, feature request and deployment limitation.
- [ ] Check privacy implications and whether any call could incur provider charges.
- [ ] Decide on the smallest isolated change and regression test.
- [ ] Run targeted tests before full integration CI.
- [ ] Confirm all required Windows/Linux jobs and end-to-end gates are green.
- [ ] Update documentation and this guide for changed contracts.
- [ ] Preserve `master` and clean up merged topic branches when safe.
- [ ] Report observed outcomes with exact links and clearly identify remaining blockers.

**Final operating principle:** AEA should make existing agents more *testable, observable and safely comparable* without taking ownership of their application logic or claiming guarantees the evidence cannot support.
