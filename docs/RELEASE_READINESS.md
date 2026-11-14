# AEA 2.2.0 release-readiness assessment

**Assessment date:** 14 November 2026  
**Integration branch:** `dev`  
**Default/release branch:** `master` (not promoted)  
**Decision:** Suitable for further controlled internal evaluation with approved synthetic data. **Not approved for confidential production use or general release.**

## Evidence and scope

This pass reviewed the project guide, README, architecture and security documents, CI workflow, key execution and scoring paths, framework adapters, dataset validation, baseline transaction logic, default redaction and focused test modules. It inspected actual GitHub CI runs rather than relying exclusively on prior assessments.

CI runs execute on Windows and Linux with Python 3.11 and 3.12. Two additional jobs exercise offline examples and regression/privacy/demo/rehearsal/installed-wheel acceptance. These verify the tested offline paths, not all external provider combinations. All hardening and rehearsal PRs passed their six CI checks before merge; every final integrated `dev` revision must still pass before any release decision.

## Technical findings addressed

| Priority | Issue | Correction and evidence |
| --- | --- | --- |
| P1 | Non-finite or out-of-range quality thresholds could silently bypass comparison decisions | [PR #102](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/102), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43573990019): bounded flag/API validation and regression tests |
| P1 | Arbitrary custom score values could retain payload strings in otherwise redacted Inspect logs | [PR #103](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/103), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43574184162): minimise nonstandard score values and test sample/reduction paths |
| P1 | Samples recording an execution error could still count as passing when a scorer had already returned a correct result | [PR #104](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/104), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43574471945): treat errored epochs as failures and test affected comparisons |
| P2 | Four previously deferred comparison tests could use the synthetic Inspect capture or a disposable modified copy | [PR #105](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/105), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43575043376): restore those checks; reduce explicit deferred groups from eleven to seven |
| P2 | Invalid JSON Schema expectations were detected after an agent ran instead of when loading a dataset | [PR #106](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/106), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43575199182): preflight draft-aware JSON Schema validation and negative tests |
| P2 | Normalised one-pass cost could be mistaken for total multi-epoch spend | [PR #108](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/108), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43576640025): separately report observed summed epoch tokens and estimate full-evaluation cost only with complete usage |
| P2 | Seven comparison/statistics test groups still depended on unavailable fixed run data | [PR #109](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/109), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43576857425): replace all seven with independently checkable synthetic tests; no missing source data was recreated |
| P2 | No repeatable dual-framework baseline/regression onboarding rehearsal | [PR #110](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/110), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43577524707): validate separate Strands and LangGraph baselines, unchanged comparisons, deliberate faults and baseline hashes; this is not team adoption |
| P1 | Arbitrary trace span names were retained in default output and captured Inspect logs could be accepted as previous baselines | [PR #115](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/115), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43587901379): mask dynamic span names and refuse obvious captured/unredacted previous logs before replacement |
| P2 | Malformed or misspelt module/function references had poor diagnostics | [PR #116](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/116), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43588405693): fail before allocating run directories for invalid shapes, preserve ImportError compatibility and differentiate missing dependencies |
| P2 | Newly frozen baseline permissions depended on source directory modes, and retained backups lacked a discovery command | [PR #117](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/117), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43588708832): owner-only POSIX snapshots plus read-only `aea backups`; retention and Windows ACL approval remain manual |

These changes preserve the `aea` CLI's published exit-code contract and do not introduce paid model-provider calls into CI.

## What is actually verified

- Offline Strands and LangGraph examples, with separate local LangGraph conformance checks.
- Deterministic regression detection against a retained baseline, including a deliberately defective Orders agent.
- Existing guarded baseline update, backup preservation and rollback scenarios under fault injection.
- Newly introduced security checks for dynamic trace-name masking, explicit capture rejection in baseline updates, and non-destructive retained backup listing.
- Synthetic privacy sentinel checks for both supported adapters, with default payload minimisation.
- Built-wheel installation and CLI smoke checks in a disposable environment.
- Windows/Linux Python 3.11/3.12 CI for each merged hardening change.
- All eleven previously excluded comparison/statistics case groups are now covered by independent synthetic checks, including four earlier restored and seven newly replaced groups.
- The complete CLI module now runs on synthetic references: PR #119 recorded 2,646 passing non-slow unit tests and a separate 54-case slow CLI/conformance gate. The follow-up broadens slow selection to every marked-slow unit case; its final run must be checked before publication.
- The two-adapter synthetic pilot rehearsal succeeds, but has not been executed by independent delivery teams.
- Two separate synthetic applications validate the public CLI from independent working directories: 12/12 case baselines for each, unchanged checks, expected regression detection and unchanged approved baseline files ([6/6 CI evidence](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43586061939)). Ready-to-use local TOML configuration and an [integration developer experience audit](INTEGRATION_DEVELOPER_EXPERIENCE.md) make the onboarding procedure reproducible. These do not count as independent delivery-team usage.
- Full reported multi-epoch token usage is distinguished from a normalised single-pass estimate; missing provider usage is not extrapolated.

These are technical test results. They do not establish universal compatibility, security certification or user adoption.

## Open issues and limitations

| Priority | Remaining item | Release implication |
| --- | --- | --- |
| P1, approval | Formal security review, sensitive identifier classification and file access/retention policy | Required before handling confidential customer data |
| P2, validation | Live Strands/LangGraph provider execution, errors, latency, usage and spending | Needs approved credentials and authorised provider-specific tests outside the no-cost CI |
| P2, coverage | The complete original CLI test module now uses disposable synthetic calculator references: non-slow tests run in all four OS/Python lanes, while the release lane runs marked-slow cases from **all** unit modules and LangGraph conformance | [PR #119](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/119), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43590375757) verified CLI-only slow acceptance; verify the expanded all-unit slow gate before declaring it complete |
| P2, operations | New baseline snapshots use owner-only permissions on POSIX, and `aea backups` lists retained versions without deletion. Backup folders still need an owner-defined retention process and Windows ACL review; stale locks require investigation and external writers do not observe AEA's lock | Define operational procedures before team-wide use |
| P2, privacy | Case IDs, tool/model names, paths and certain numerical metadata may identify workloads; arbitrary non-root span names are now removed from default traces. `--capture-content` intentionally retains raw content. Baseline updates now reject raw sample fields and captured flags before preservation. The GitHub repository is public | Do not commit confidential pilot evidence, customer inputs, team identities or internal approvals; use approved restricted systems for real pilot records |
| P2, adoption | The synthetic two-framework rehearsal passed, but independent delivery-team integration and productivity outcomes have not yet been measured | Complete the [independent pilot worksheet](PILOT_EVIDENCE_TEMPLATE.md) and [approval issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) with authorised reviewers |
| P3, scope | Additional source-level adversarial review and unusual graph/provider integration scenarios remain | Extend targeted tests and review before claiming a finished broad security and correctness audit |

**No claim of complete independent security assurance is made.** The application executes trusted Python factories, mapping functions and scorers; it is not a sandbox. Local tests cannot prove safe operation for arbitrary client workflows or remote providers.

## Recommended gates before promotion

1. Verify fresh integrated `dev` CI: all six jobs pass at the same revision.
2. Keep the complete CLI and comparison/statistics tests enabled in the fast/slow CI lanes; confirm each marked-slow unit and conformance case ran, not merely that the jobs were green.
3. Perform an approved security, dependency and licence review; decide where logs, trace files, backups and captured data may reside and how long they are retained.
4. Use [PILOT.md](PILOT.md) and the [blank evidence worksheet](PILOT_EVIDENCE_TEMPLATE.md) to validate real Strands and LangGraph applications in separate independent delivery-team pilots. The shipped rehearsal does not satisfy this gate.
5. Obtain explicit approval for live provider tests, then observe representative model responses, tool errors, rate limits and token/cost reporting.
6. Produce the pilot evidence and request release approval before changing `master`, adding a tag or distributing the package.

See [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md), [SECURITY_REVIEW.md](SECURITY_REVIEW.md), [TESTING.md](TESTING.md), [PILOT.md](PILOT.md) and [release gate issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) for detail.
