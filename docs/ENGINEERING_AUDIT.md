# AEA engineering assessment

**Scope:** Local-first evaluation engine, agent framework adapters, regression checks, baseline snapshots, privacy boundary, test selection, packaging and delivery-team onboarding.

## Executive assessment

AEA has functional Strands and LangGraph adapters, a deterministic seven-scenario local smoke matrix, Inspect AI evaluation, case/tool checks, optional judging, run comparison and reports. It is useful for internal pilots, but passing offline CI is not proof of safe handling of production customer data or complete live-provider compatibility.

## Findings and required actions

| Priority | Finding | Evidence and impact | Disposition |
| --- | --- | --- | --- |
| P0 | Baseline updates previously removed an existing destination after a separate pre-run check | `cli._check` could erase intervening files or leave no baseline after a copy failure | Addressed with staged validation, cooperative writer lock, retained prior snapshot and rollback tests |
| P1 | The original streamlined suite missed six test modules | Comparison, statistics, token metrics and pairwise judging lacked routine coverage | Resolved for routine coverage: 43 complete modules plus 20 independent CLI test groups; fixed-reference CLI integration tests remain partially selected; all comparison/statistics groups now have runnable synthetic replacements |
| P1 | No conformance gate in the streamlined CI | Non-standard LangGraph state, tool calls and interrupts could regress without integration coverage | Resolved: dedicated local conformance suite runs on Windows/Linux Python 3.11 and 3.12 |
| P1 | Deterministic Orders example had one inconsistent expected sentence | The program calculated the correct total but only reported 10/11 passing cases | Corrected dataset and added end-to-end tool-plan assertion |
| P1 | Fixed log assertions need an unavailable reference capture and baseline archive | Blindly inventing those fixtures would make results meaningless | Replaced all seven remaining fixed-reference comparison/statistics groups with synthetic verification without implying the missing archive was restored |
| P1 | Dependency resolution previously changed on every CI run | Dynamically resolving packages can introduce different versions despite green CI on the prior commit | Resolved: commit a multi-platform `uv.lock`, validate it with `uv lock --check` and require locked installs on every CI lane |
| P1 | The installer and packaged CLI are not independently exercised by the streamlined CI | Source checkout imports can pass while a built distribution is incomplete | Added an isolated wheel-install and CLI smoke gate |
| P1 | Positive-case smoke does not prove regression detection | Seven passing model doubles do not verify detection of a deliberately broken agent from an approved baseline | Added a good-to-broken Orders CLI check as a separate CI release gate |
| P1 | Expense scorer/test referral expectations disagreed | One case was previously deselected even though referrals must approve no money | Resolved: corrected the test expectation and restored the omitted case to routine CI without changing scorer behaviour |
| P1 | Trace redaction is not universal anonymisation | Span names, case IDs, timing and tool names remain; opt-in captured logs intentionally carry data | Keep documented boundaries, review filenames and identifiers before client pilots |
| P2 | Model, judge and framework compatibility are not tested against live providers | Local deterministic doubles cannot establish model stability, latency, spend or rate-limit behaviour | Undertake a controlled non-CI integration pilot with approved credentials |
| P2 | No validated multi-team onboarding data | CI success is not equivalent to engineering productivity or adoption | Follow the two-team [adoption pilot](PILOT.md), collect baseline productivity measurements and independent engineering sign-off |

## Verified safeguards

- Run logs default to redacted Inspect content, and arbitrary custom OpenTelemetry span payloads are minimised unless capture is requested.
- Local evaluation examples require no cloud keys or billable model calls in CI.
- Previous baseline snapshots remain available as explicit on-disk backups rather than being silently deleted.
- The broken-refund-policy CLI gate confirms that the deliberately faulty agent generates exit code 1 and an actionable comparison report while leaving its baseline untouched. This does not establish performance against live providers.
- Code, dataset, scoring function and custom mappings are **trusted executable Python**, not sandboxed user input.

## Verified local release gates (12 November 2026)

The audited CI revision passed **6/6 jobs**, including Windows and Linux with Python 3.11 and 3.12, locked dependency installation, the complete local example suite, deliberate-regression detection, and a fresh-environment wheel installation.

The Ubuntu Python 3.11 evidence showed **2,444 passing unit tests, 34 deselected cases and 13 passing non-slow LangGraph conformance tests**. One conformance test is intentionally marked slow; a fixed-reference CLI module is also excluded and documented in the runner. These figures describe the tested revision, not a claim that every available test or provider scenario is verified.

**Engineering verdict:** viable for an internal pilot using approved synthetic/local data. **Not yet approved** for confidential production workloads or a default-branch release. Outstanding approvals require a security/data-retention assessment, a live-provider validation plan and independent delivery-team pilot evidence.

## Acceptance criteria for the next release candidate

1. All Windows/Linux Python 3.11/3.12 checks pass, with the test inventory and deferrals visible.
2. Good-agent and deliberately degraded-agent end-to-end CLI gates give the expected pass/regression exit codes.
3. A built distribution installs in a fresh environment and provides the documented CLI and templates.
4. No unintended prompt or tool payload is written during default capture-off runs.
5. Baseline update, rollback and snapshot retention survive the failure-injection tests.
6. Documentation differentiates demonstrated offline support from provider-dependent behaviour.
7. A security review signs off on sample identifiers, retention and trace/report sharing.
8. `master` promotion requires explicit release approval.

## Current release recommendation

The [14 November 2026 release-readiness assessment](RELEASE_READINESS.md) records the additional hardening PRs, their six-job CI evidence, reduced test deferrals and remaining approvals. Those verified changes support a controlled internal pilot using approved synthetic data, not production clearance or automatic promotion of `master`.

## Known limits

The snapshot backups are append-only and need retention management. A cooperative lock does not coordinate arbitrary third-party writers. Existing comparator statistics are informative unless threshold options explicitly activate gates. The sample Orders and Expense data are illustrative, not client-domain acceptance tests.
