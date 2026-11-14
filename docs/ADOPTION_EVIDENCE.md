# AEA 2.2.0: controlled adoption evidence protocol

**State:** Not yet demonstrated. These are instructions and templates, not a claim of independent users, saved engineering time or security approval.

## Evidence hierarchy

| Evidence category | Available today | What it permits us to claim |
| --- | --- | --- |
| Deterministic CI | Cross-platform unit tests, slow acceptance and fresh-wheel install | Technical functionality in the tested combinations |
| Self-authored integration | One Strands and one LangGraph synthetic application | Cross-framework feasibility on two checked local examples |
| Synthetic regression benchmarking | Measured CLI subprocess durations and injected faults | Observed local runtime and controlled-defect detection, **not** human productivity |
| Independent onboarding | **Not measured** | No claim of independently demonstrated ease of adoption |
| Independent delivery teams | **Not achieved** | No claim of multi-team reuse |
| Security/operations authorisation | **Not approved** | No claim of readiness for sensitive production inputs |

## A fair and reproducible pilot

Use [issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) as the external approval gate.

1. Choose one existing Strands and one existing LangGraph agent owned by separate delivery teams. Define the same task and fixed synthetic/approved cases **before** observing results.
2. Have a non-author engineer complete the [first evaluation onboarding](ONBOARDING.md), noting start/finish timestamps, tool versions, support requests, errors and whether the factory/mappers needed code changes.
3. Compare the team's *actual existing evaluation approach* to AEA on the same input cases, required failure signals and outputs. Do not compare a weak manual test against a much stronger AEA run without reporting the difference.
4. Counterbalance task order between pilot engineers where possible. Record time to first valid report, case-authoring minutes, integration support minutes, repeated-check time and baseline interpretation.
5. For both approaches, run three unchanged comparisons and a declared, controlled defect. Record pass/fail, true detections, missed defects and unexpected failures.
6. Verify the baseline fingerprints and data-handling policy. Have the authorised reviewer assess output identifiers, permissions, traces, backups and retention before sharing any results.
7. Make a separate documented *adoption* decision and *security* decision. A technically successful synthetic rehearsal alone satisfies neither.

## Data to record for each engineer

| Field | Value |
| --- | --- |
| Pilot/team alias (non-identifying) | Not yet recorded |
| Framework, commit and Python version | Not yet recorded |
| Approved data class and reviewer | Not yet recorded |
| Evaluation tasks and number of cases | Not yet recorded |
| Control workflow definition | Not yet recorded |
| AEA setup and case-authoring minutes | Not yet recorded |
| Control setup and case-authoring minutes | Not yet recorded |
| Support and troubleshooting minutes | Not yet recorded |
| Controlled faults injected/detected in each approach | Not yet recorded |
| Three unchanged reruns (per approach) | Not yet recorded |
| Baseline fingerprints verified | Not yet recorded |
| CI job and approved evidence location | Not yet recorded |
| Engineer feedback and proposed change | Not yet recorded |
| Security and release decisions | Pending |

Do not put client identifiers, personal data, prompts or raw provider output in public GitHub issues or committed worksheets. Keep identifying evidence in an authorised private system.

## Leadership decision sheet

**Ask:** Approve a two-team, synthetic or expressly approved-data pilot, with security review and measurable onboarding and regression criteria.

**Existing engineering case:** The common AEA CLI currently exercises two frameworks, deterministic 12-case example applications, reproducible baseline checks and controlled defect detection. See [value assessment](VALUE_ASSESSMENT.md) and [benchmark methodology](BENCHMARKING.md) for exact provenance.

**Hypothesis to test:** A reusable quality gate reduces duplicated evaluation infrastructure, makes agent regressions easier to diagnose and lowers comparable engineer effort.

**Success requirements:** No bespoke AEA changes for the two integrations; controlled faults detected; results interpretable; no unapproved data exposure; actual engineering effort captured against a credible control.

**Failure or hold decisions:** An unusable adapter, unacceptable metadata leak, unrecoverable baseline, excessive authoring effort or missing reviewer means remediate or halt the rollout, even when CI is green.

**Non-claims:** No percentage productivity improvement, independent multi-team adoption, live-provider reliability or customer production clearance is established yet. Keep `master` untouched until separately authorised.
