# Human engineering effort pilot: measurement instructions

**Status: ready to execute, not yet conducted.** No non-author engineer has independently completed this protocol. GitHub Actions onboarding timings are machine-execution evidence, not human-time observations.

## Two questions that still require humans

1. Can an engineer who did not build AEA integrate and interpret an existing Strands or LangGraph agent without bespoke AEA source changes?
2. Does AEA improve measured effort or fault detection compared with that engineer's team's current QA approach, at equivalent coverage?

Synthetic CI cannot answer either on its own.

## Participation and scope

Use one independent Strands engineer and one independent LangGraph engineer, preferably from different delivery teams. If they are unavailable, a solo author trial is only a diagnostic rehearsal, not independent adoption. Use synthetic data unless explicit security approval covers real inputs, identifiers, traces and retention. Do not publish participant identities, internal project details or customer prompts.

## Identical benchmark task

Both approaches must execute the real existing agent on the same frozen test dataset. They must confirm golden answers and ordered tool calls where applicable, exercise three unchanged reruns, identify all failing cases after the same injected defect, explain the root cause and leave the reference baseline intact.

Do not treat the minimal direct-framework control as feature-equivalent to AEA's trace reports, scoring and retained baselines. Record those coverage differences separately.

## Stopwatch boundaries

| Activity | Begin timing | Stop timing |
| --- | --- | --- |
| Environment setup | First checkout/install action | Target application and test tool can import |
| Agent integration | First factory/config/mapping change | First valid agent invocation |
| Test-case authoring | First new case | Reviewed case set frozen |
| First valid result | Launch selected testing workflow | Complete usable test report/result produced |
| Fault investigation | Run the intentionally defective agent | Engineer can name exact failing case and root cause |
| CI integration | Begin pipeline change | Working repeatable offline quality gate |
| Troubleshooting/support | First unexpected blocker | Resolved, abandoned or escalated |

Record active work minutes and wall-clock elapsed minutes separately. Log interruptions, support requests, temporary workarounds and failures. Include authoring a conventional test harness if the control needed one. Count any AEA adaptation time too.

## Fairness constraints

Counterbalance task order where possible: control first for one engineer, AEA first for the other. Keep equivalent input cases and success criteria, use clean worktrees and record any shared code. An author-only rehearsal cannot establish a generalisable productivity percentage.

## Blank per-engineer timecard

Duplicate this template into an authorised private workspace when an eligible participant exists.

| Field | Existing QA control | AEA |
| --- | --- | --- |
| Participant/team alias, date, repo revision | Pending | Pending |
| Tool versions and prior experience | Pending | Pending |
| Setup active/elapsed minutes | Pending | Pending |
| Agent integration active minutes | Pending | Pending |
| Case authoring active minutes | Pending | Pending |
| First complete report active minutes | Pending | Pending |
| Fault investigation active minutes | Pending | Pending |
| CI integration active minutes | Pending | Pending |
| Troubleshooting/support active minutes | Pending | Pending |
| Cases passed / expected | Pending | Pending |
| Failing case IDs after injected defect | Pending | Pending |
| Root cause explained correctly | Pending | Pending |
| Three unchanged reruns | Pending | Pending |
| Artefact handling approved | Pending | Pending |
| Reviewer and evidence reference | Pending | Pending |

## Calculation

For genuinely comparable scope: saved active minutes = control active minutes - AEA active minutes. If control active minutes are positive, percentage saved = 100 * saved minutes / control active minutes. Report negative savings if AEA took longer, plus sample size, task exclusions, confidence limitations and quality differences. Do not report a quantitative gain while any needed timecard fields remain unmeasured.

Stop and escalate if confidential data enters unapproved outputs, either workflow misses known defects, reports cannot be interpreted or paid model calls appear without permission.

## What automation already covers

The scripted [onboarding rehearsal](../scripts/onboarding_rehearsal.py) measures a fresh CI virtual-environment dependency sync, AEA preflight, first baseline report, unchanged comparison and deliberately broken agent, alongside a direct-framework check. It covers two distinct synthetic applications.

Its output must retain the classification **script-driven synthetic evidence**. All human case-authoring, integration, support and report-interpretation minutes remain null. It is never a substitute for an independent engineer.

Final adoption and security decisions are tracked in [Issue #111](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111). Keep master unchanged until a separate production-release approval.
