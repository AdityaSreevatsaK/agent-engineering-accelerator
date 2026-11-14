# AEA 2.2.0 release-readiness assessment

**Assessment date:** 14 November 2026  
**Integration branch:** `dev`  
**Default/release branch:** `master` (not promoted)  
**Decision:** Suitable for further controlled internal evaluation with approved synthetic data. **Not approved for confidential production use or general release.**

## Evidence and scope

This pass reviewed the project guide, README, architecture and security documents, CI workflow, key execution and scoring paths, framework adapters, dataset validation, baseline transaction logic, default redaction and focused test modules. It inspected actual GitHub CI runs rather than relying exclusively on prior assessments.

CI runs execute on Windows and Linux with Python 3.11 and 3.12. The remaining two jobs exercise offline examples and regression/privacy/demo/installed-wheel acceptance. These verify the tested offline paths, not all external provider combinations. Individual PR checks passed 6/6 before each merge; the final integrated `dev` revision must also be checked before any release decision.

## Technical findings addressed

| Priority | Issue | Correction and evidence |
| --- | --- | --- |
| P1 | Non-finite or out-of-range quality thresholds could silently bypass comparison decisions | [PR #102](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/102), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43573990019): bounded flag/API validation and regression tests |
| P1 | Arbitrary custom score values could retain payload strings in otherwise redacted Inspect logs | [PR #103](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/103), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43574184162): minimise nonstandard score values and test sample/reduction paths |
| P1 | Samples recording an execution error could still count as passing when a scorer had already returned a correct result | [PR #104](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/104), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43574471945): treat errored epochs as failures and test affected comparisons |
| P2 | Four previously deferred comparison tests could use the synthetic Inspect capture or a disposable modified copy | [PR #105](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/105), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43575043376): restore those checks; reduce explicit deferred groups from eleven to seven |
| P2 | Invalid JSON Schema expectations were detected after an agent ran instead of when loading a dataset | [PR #106](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/106), [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43575199182): preflight draft-aware JSON Schema validation and negative tests |

These changes preserve the `aea` CLI's published exit-code contract and do not introduce paid model-provider calls into CI.

## What is actually verified

- Offline Strands and LangGraph examples, with separate local LangGraph conformance checks.
- Deterministic regression detection against a retained baseline, including a deliberately defective Orders agent.
- Existing guarded baseline update, backup preservation and rollback scenarios under fault injection.
- Synthetic privacy sentinel checks for both supported adapters, with default payload minimisation.
- Built-wheel installation and CLI smoke checks in a disposable environment.
- Windows/Linux Python 3.11/3.12 CI for each merged hardening change.
- Four additional independent comparison tests restored to the normal offline runner.

These are technical test results. They do not establish universal compatibility, security certification or user adoption.

## Open issues and limitations

| Priority | Remaining item | Release implication |
| --- | --- | --- |
| P1, approval | Formal security review, sensitive identifier classification and file access/retention policy | Required before handling confidential customer data |
| P2, validation | Live Strands/LangGraph provider execution, errors, latency, usage and spending | Needs approved credentials and authorised provider-specific tests outside the no-cost CI |
| P2, reporting | Reported token totals and estimated cost describe a normalised single dataset pass using per-epoch averages, not the full spend of all epochs | Clarify the user-facing label and add an optional measured full-run cost metric before relying on it for billing or capacity decisions |
| P2, coverage | Seven fixed-reference comparison/statistics test groups remain deferred; full CLI archived-log integration tests and marked-slow tests are not in the regular matrix | Do not claim complete test coverage; create independent new oracles and exercise slow paths selectively |
| P2, operations | Backup folders need an owner-defined retention process; stale cooperative locks require investigation; external writers do not observe AEA's lock | Define operational procedures before team-wide use |
| P2, privacy | Case IDs, tool/span/model names, paths and certain numerical metadata may identify workloads; `--capture-content` intentionally retains raw content | Require data classification and reviewed output-sharing policy |
| P2, adoption | Independent use by a Strands delivery team and a LangGraph delivery team has not yet been measured | Execute the two-team pilot and record real setup/authoring time, defect detection and feedback |
| P3, scope | Additional source-level adversarial review and unusual graph/provider integration scenarios remain | Extend targeted tests and review before claiming a finished broad security and correctness audit |

**No claim of complete independent security assurance is made.** The application executes trusted Python factories, mapping functions and scorers; it is not a sandbox. Local tests cannot prove safe operation for arbitrary client workflows or remote providers.

## Recommended gates before promotion

1. Verify fresh integrated `dev` CI: all six jobs pass at the same revision.
2. Keep the seven deferred test groups visible, replacing them only when independent synthetic oracles are available.
3. Perform an approved security, dependency and licence review; decide where logs, trace files, backups and captured data may reside and how long they are retained.
4. Validate at least one real existing Strands and one real existing LangGraph application in separate independent pilots with approved synthetic data.
5. Obtain explicit approval for live provider tests, then observe representative model responses, tool errors, rate limits and token/cost reporting.
6. Produce the pilot evidence and request release approval before changing `master`, adding a tag or distributing the package.

See [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md), [SECURITY_REVIEW.md](SECURITY_REVIEW.md), [TESTING.md](TESTING.md) and [PILOT.md](PILOT.md) for detail.
