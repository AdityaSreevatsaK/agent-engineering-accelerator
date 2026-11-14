# AEA engineering assessment

**Scope:** Local-first evaluation engine, agent framework adapters, regression checks, baseline snapshots, privacy boundary, test selection, packaging and delivery-team onboarding.

## Executive assessment

AEA has functional Strands and LangGraph adapters, a deterministic seven-scenario local smoke matrix, Inspect AI evaluation, case/tool checks, optional judging, run comparison and reports. It is useful for internal pilots, but passing offline CI is not proof of safe handling of production customer data or complete live-provider compatibility.

## Findings and required actions

| Priority | Finding | Evidence and impact | Disposition |
| --- | --- | --- | --- |
| P0 | Baseline updates previously removed an existing destination after a separate pre-run check | `cli._check` could erase intervening files or leave no baseline after a copy failure | Addressed with staged validation, cooperative writer lock, retained prior snapshot and rollback tests |
| P1 | Earlier CI did not exercise the complete CLI and slow integration suites | Only selected parser/config tests ran from `test_cli.py`, and other marked-slow paths were omitted | The full CLI module now uses fresh synthetic calculator fixtures; non-slow tests run in all four matrix lanes, and a distinct release gate runs every marked-slow unit/conformance case; original missing archives are not represented as restored |
| P1 | No conformance gate in the streamlined CI | Non-standard LangGraph state, tool calls and interrupts could regress without integration coverage | Resolved: dedicated local conformance suite runs on Windows/Linux Python 3.11 and 3.12 |
| P1 | Deterministic Orders example had one inconsistent expected sentence | The program calculated the correct total but only reported 10/11 passing cases | Corrected dataset and added end-to-end tool-plan assertion |
| P1 | Fixed log assertions need an unavailable reference capture and baseline archive | Blindly inventing those fixtures would make results meaningless | Replaced all seven remaining fixed-reference comparison/statistics groups with synthetic verification without implying the missing archive was restored |
| P1 | Dependency resolution previously changed on every CI run | Dynamically resolving packages can introduce different versions despite green CI on the prior commit | Resolved: commit a multi-platform `uv.lock`, validate it with `uv lock --check` and require locked installs on every CI lane |
| P1 | The installer and packaged CLI are not independently exercised by the streamlined CI | Source checkout imports can pass while a built distribution is incomplete | Added an isolated wheel-install and CLI smoke gate |
| P1 | Positive-case smoke does not prove regression detection | Seven passing model doubles do not verify detection of a deliberately broken agent from an approved baseline | Added a good-to-broken Orders CLI check as a separate CI release gate |
| P1 | Expense scorer/test referral expectations disagreed | One case was previously deselected even though referrals must approve no money | Resolved: corrected the test expectation and restored the omitted case to routine CI without changing scorer behaviour |
| P1 | Trace redaction is not universal anonymisation | Dynamic non-root span names are now masked by default; case IDs, tool names, timing and metadata remain. Opt-in capture still persists raw content | Keep documented boundaries, review identifiers and file access before client pilots |
| P2 | Model, judge and framework compatibility are not tested against live providers | Local deterministic doubles cannot establish model stability, latency, spend or rate-limit behaviour | Undertake a controlled non-CI integration pilot with approved credentials |
| P2 | No validated multi-team onboarding data | CI success is not equivalent to engineering productivity or adoption | Follow the two-team [adoption pilot](PILOT.md), collect baseline productivity measurements and independent engineering sign-off |

## Verified safeguards

- Run logs default to redacted Inspect content; arbitrary custom OpenTelemetry payloads and non-root span names are minimised unless capture is requested.
- Local evaluation examples require no cloud keys or billable model calls in CI.
- Baseline update validation refuses explicit content capture and non-redacted sample payloads. New POSIX baseline copies use owner-only modes; previous versions are retained, and `aea backups` can inventory them without deletion. Windows permissions require an explicit ACL review.
- The broken-refund-policy CLI gate confirms that the deliberately faulty agent generates exit code 1 and an actionable comparison report while leaving its baseline untouched. This does not establish performance against live providers.
- Code, dataset, scoring function and custom mappings are **trusted executable Python**, not sandboxed user input.

## Verified local release gates (14 November 2026)

The audited CI revision passed **6/6 jobs**, including Windows and Linux with Python 3.11 and 3.12, locked dependency installation, the complete local example suite, deliberate-regression detection, and a fresh-environment wheel installation.

The [PR #119 verification](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43590375757) recorded **2,646 passing non-slow unit tests**, 13 passing non-slow conformance tests, and **54 passing slow CLI/conformance cases**. The expanded release gate [PR #120 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43591507776) subsequently passed **74 slow cases** covering all unit modules and LangGraph conformance, including token-price and domain-example end-to-end paths. The original archived calculator logs were not restored: their missing inputs are replaced with explicitly constructed synthetic references. These figures are evidence for that commit, not coverage of live providers.

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

The [14 November 2026 release-readiness assessment](RELEASE_READINESS.md) records the hardening PRs, their six-job CI evidence, reduced test exclusions and remaining approvals. [PR #115](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/115) tightened trace/baseline privacy, [PR #116](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/116) improved invalid-reference handling, and [PR #117](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/117) added private POSIX copies and a read-only backup inventory. Those verified changes support a controlled internal pilot using approved synthetic data, not production clearance or automatic promotion of `master`.

## Known limits

The snapshot backups are append-only and need retention management. Review the [release candidate checklist](RELEASE_CANDIDATE_CHECKLIST.md) before requesting any promotion. A cooperative lock does not coordinate arbitrary third-party writers. Existing comparator statistics are informative unless threshold options explicitly activate gates. The sample Orders and Expense data are illustrative, not client-domain acceptance tests.
