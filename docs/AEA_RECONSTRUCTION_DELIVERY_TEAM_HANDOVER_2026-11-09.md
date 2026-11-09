# AEA reconstructed toolkit: delivery-team handover

**Checkpoint:** 9 November 2026
**Review branch:** reconstruction/wip-checkpoint-2026-10-30
**Release status:** Under reconstruction, not approved for master or production.

This is newly authored operator material, NOT an original v2.2.0 source file. The historical root README.md stays intact.

## Who it helps

Agent Engineering Accelerator (AEA) is a **local-first evaluation, tracing and regression harness for existing AI agents**. It is separate from the Agentic Engineering Toolkit (AET), whose responsibility is creating new agent project scaffolds.

| Capability | Team benefit | Offline evidence |
| --- | --- | --- |
| Dataset-backed agent evaluations | Repeatable test cases for workflows | Native Strands and LangGraph adapters, recovered examples |
| Deterministic output and tool scorers | Catch incorrect content, tool usage and route changes | Calculator, triage, expense, helpdesk and policy RAG |
| Baseline freeze/check/compare | Detect prompt/agent regressions, preserve earlier behaviour | Planted two-case and three-case regression comparisons |
| OpenTelemetry and Inspect AI | Summarise per-case quality, time, tokens and tool activity | Local traces and JSON logs |
| Judge interface | Golden, reference-free and pairwise analysis | Offline mock judge; external provider judging not included in CI |
| Markdown/HTML/PDF output | Share an evaluation report | Report/export tests; PDF requires browser support |
| Default content redaction | Minimise prompt disclosure in stored logs | Strands starter E2E and LangGraph privacy probe |

Users: delivery-team AI engineers, agent owners and QA engineers. This is not a hosted evaluation product, agent orchestrator, general provider abstraction or code sandbox.

## Offline quick start

Requirements: Python 3.11 or 3.12, Windows or Linux, repository cloned, working directory at repo root. Use deterministic offline example factories only.

~~~sh
git checkout reconstruction/wip-checkpoint-2026-10-30
python -m pip install -e ".[strands,langgraph]"
~~~

**Strands starter.** The first check freezes a local redacted baseline; the second verifies unchanged behaviour. Expect five passing cases.

~~~sh
python -m agent_accelerator.cli init demo_agent
python -m agent_accelerator.cli check demo_agent/dataset.jsonl --agent demo_agent.agent:build_offline_agent --runs-dir runs --baseline baseline --update-baseline
python -m agent_accelerator.cli check demo_agent/dataset.jsonl --agent demo_agent.agent:build_offline_agent --runs-dir runs --baseline baseline
~~~

**LangGraph custom-state triage.** TOML supplies the adapter, agent and state maps. Expect 12 passing cases.

~~~sh
python -m agent_accelerator.cli run examples/triage/dataset.jsonl --config examples/triage/aea.toml --runs-dir runs --max-samples 1
~~~

**LangGraph approval-interrupt helpdesk.** Expect 10 passing cases, including two admin requests that *stop at a human-approval interrupt*, not grant admin access.

~~~sh
python -m agent_accelerator.cli run examples/helpdesk/dataset.jsonl --adapter langgraph --agent examples.helpdesk.agent:build_agent --runs-dir runs --max-samples 1
~~~

**Repeat the disposable regression and redaction tests.** This creates no permanent captured logs or historical baselines.

~~~sh
python -m reconstruction_tools.verify_recovered_example_baselines --scenario all
python -m reconstruction_tools.verify_langgraph_capture_privacy_e2e --scenario all
python -m reconstruction_tools.audit_release_evidence --format markdown
~~~

All generated probe inputs use synthetic values and are deleted with their temporary run artefacts.

## Expected outputs and operating practice

The CLI prints each run directory. A run contains an Inspect JSON evaluation log, traces.jsonl, and report.md. A baseline comparison additionally produces comparison.md with an OK or REGRESSION verdict.

~~~sh
python -m agent_accelerator.cli report PATH_TO_RUN_DIRECTORY
python -m agent_accelerator.cli export PATH_TO_RUN_DIRECTORY/report.md --format html --output report.html
~~~

For an illustrative regression, the good triage factory passes all cases, while build_reworded_agent fails two urgent-billing cases. The expense build_condensed_agent exposes three missing-receipt regressions. See reconstruction_audits/2026-11-09_disposable_baseline_replay.md for the verified seeded cases.

## Security and privacy boundaries

1. Default runs redact sample prompts and outputs, plus sensitive trace attributes. Explicit --capture-content retains prompts, messages, tool payloads and outputs and can create sensitive logs. Never commit captured client data; use disposable folders and delete them.
2. Imported agent, scorer and state-map factories execute trusted Python code. These are not sandboxed plugins. A custom tool can make network requests or change real-world state regardless of AEA logging configuration.
3. Logs still retain context such as case IDs, tool names, dataset paths/hashes, timing and check names. Avoid sensitive identifiers even when raw payloads are scrubbed.
4. Review every prospective checked-in baseline and exported report. Custom --runs-dir paths and exported HTML may fall outside Git ignore rules. Do not treat redaction as anonymisation.
5. Keep external provider credentials unset for offline demos. Never instantiate build_live_agent during CI.

The new LangGraph privacy regression covers default redaction versus explicit capture for both custom-state triage and helpdesk approval interrupts. It is a **synthetic-input behavioural test**, not an audit of arbitrary user-provided agents.

## Reconstruction state and limitations

Historical file presence: **97/117**. Missing: 14 original baseline artefacts, two original calculator captured fixtures, two original acceptance/security documents, the original uv.lock and the historical CI workflow at its active path. The workflow source is archived but cannot yet safely run as historical CI. Original documents are represented by provisional drafts only.

Existing reconstruction CI verifies native code paths on Windows/Ubuntu and Python 3.11/3.12. It **does not** prove byte-identical recovered source, provider-level repeatability or release approval.

Known scope limits: multi-turn evaluation, remote/deployed LangGraph, scripted interrupt resume, universal provider support and live-model variance/cost thresholds are not validated capabilities.

## Release gates and measurable pilot

Before merging reconstructed AEA into master:
1. Review ambiguous video-derived source against original recordings and document nonidentical functional adaptations.
2. Resolve or formally waive the 20 missing originals without inventing fixture contents; assess privacy before recovering logs.
3. Validate original locked CI or obtain approval for a defined replacement release suite.
4. Obtain security/dependency review, operator acceptance and a named sign-off.
5. Pilot with at least two different agent workflows from delivery teams before presenting quantified productivity claims.

For the pilot, measure **setup/integration time**, test authoring effort, confirmed seeded and real regressions detected, failure triage effort and reuse across teams. Report measurements, not inferred savings from passing demo tests.

Supporting evidence: [previous offline guide](AEA_RECONSTRUCTION_OPERATOR_GUIDE_2026-11-06.md), [provisional acceptance transcript](../reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md), [provisional security transcript](../reconstruction_drafts/docs_review_video_PROVISIONAL.md), [release audit](../reconstruction_audits/2026-11-09_release_evidence_readiness.md).
