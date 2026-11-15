# AEA v2.2.0: Release decision

**Checked:** 15 November 2026  
**Decision:** Engineering checks passed. **Release NOT APPROVED.**  
**Scope:** Local demonstrations and synthetic evaluation only.

## Evidence verified

| Check | Evidence | Result |
| --- | --- | --- |
| Integrated candidate | `dev` commit `6bcf6849f1ee2109f623a43d850e529c48bb21a7` | Verified |
| Windows and Linux Python 3.11/3.12 | [Integrated CI run #43726515353](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43726515353) | Four jobs passed |
| Offline examples, fresh onboarding and release tests | Same integrated CI run | Three jobs passed; **7/7 total** |
| Slow CLI and framework acceptance | Same release CI job | **75 passed** |
| Public dependency advisories | Same release CI job | **126/126 locked registry versions checked; 0 known public findings reported** |
| Previous affected dependency | [Soup Sieve remediation](SOUPSIEVE_SECURITY_REMEDIATION.md) | Three published advisories addressed; Python minimum now 3.11.5 |
| Distribution | Isolated wheel install, CLI flows and generated reports | Passed in tested CI |
| Release branch | `master` commit `5fbcb5e15d4179ed60c99444e286d90fcbfeba21` | Unchanged |

These are self-authored, synthetic engineering tests. Public vulnerability feeds cannot establish complete security assurance.

## Release blockers

| Requirement | State | Who must complete it |
| --- | --- | --- |
| Existing independent Strands application pilot | Not done | An engineer outside AEA's development |
| Existing independent LangGraph application pilot | Not done | An engineer outside AEA's development |
| Measured onboarding effort and regression evidence | Not done | Those engineers and team reviewers |
| Licence permissions, confidential-data policy, Windows NTFS permissions, retention and provider access | Not approved | Authorised security, licence and data owners |
| Final release decision for the reviewed commit | Not approved | Authorised release owner |

**No independent engineers or approved security reviewers are currently available.** They cannot be replaced with a synthetic rehearsal or an automated sign-off.

Issue [#111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) was closed as **deferred/not planned at present**, not completed. Its mandatory release conditions remain in force.

## Exact next steps when reviewers are available

1. Ask the two independent engineers to use [the step-by-step guide](STEP_BY_STEP.md) on their existing Strands and LangGraph applications with **approved synthetic inputs**. Record actual setup effort and regression results in [the pilot worksheet](PILOT_EVIDENCE_TEMPLATE.md).
2. Give the authorised reviewers [the security approval worksheet](SECURITY_APPROVAL_HANDOFF.md) and CI evidence. Require written decisions on package licences, data handling, access, retention and permitted deployment scope.
3. Obtain an explicit release-owner decision referencing a **newly verified `dev` commit** and its green CI run. Only then consider a PR to `master`, a version tag or distribution.

**Until all three steps are completed:** Do not merge `dev` into `master`, tag a release, publish a package, evaluate confidential data or claim independent adoption.
