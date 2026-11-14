# AEA 2.2.0: evidence-backed engineering value assessment

**Audience:** Engineering leadership assessing whether to pilot a reusable evaluation asset.  
**As of:** 14 November 2026. **Status:** Synthetic technical validation completed; real team-value measurement pending.

## One-page scorecard

| Question | Verified evidence | Confidence |
| --- | --- | --- |
| Can two types of agent be evaluated through a shared interface? | Standalone Strands equipment support and LangGraph supplier onboarding, each with 12/12 synthetic baseline cases and a checked regression scenario | High for these local integrations |
| Can it identify a deliberate quality regression? | A known injected defect in each 12-case app triggers exit 1 and a named failing case; the 11-case Orders demo also detects a bad refund policy | High for these planted faults |
| Does the baseline remain intact during normal comparisons and tested failure cases? | SHA checks in integration/benchmark runners; deterministic concurrency, partial-copy, corrupted-log and backup-retention tests | High within enumerated fault models |
| Can a new engineer install the wheel and run CLI workflows? | Automated fresh-wheel CLI, templates and export checks pass; human onboarding experience is not measured | Automated installation only |
| What is the runtime cost of an unchanged check? | Run [43609227896](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43609227896) measured two repeat checks per application; medians **2.342 s** and **2.613 s**, on one CI runner | Descriptive, small-sample |
| How much engineering time is saved? | **No measured control group or independent engineer yet** | Unknown |
| Is it used by multiple delivery teams? | No independent adoption record. [Pilot approval gate](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/issues/111) is still open | Not demonstrated |
| Can it process confidential production data? | Default scrub/privacy tests pass; a dated [public advisory scan](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43627751480) returned zero known findings among 116 exported packages. Security, licence, retention and access controls remain unapproved | Not approved |

## Technical evidence and provenance

- **Latest assessed integrated `dev` for resilience:** `9eb93107fe481b6f7b60d00ad876d554c3f30794`, [6/6 CI](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43610474918).
- **Automated coverage at that revision:** Windows/Linux with Python 3.11/3.12; an Ubuntu job reported **2,671 passing non-slow unit tests** and **13 passing non-slow LangGraph conformance tests**. Separate slow acceptance has **74 passing cases**. Counts are executions of parametrised tests, not distinct workflows or evidence of live-cloud compatibility.
- **Independent application structure:** Two separately structured synthetic test projects, not integrations contributed by independent teams. `integrations/equipment_strands` exercises a tool-using Strands agent; `integrations/vendor_langgraph` exercises a custom-state LangGraph with input/output mappings.
- **Local runtime:** Wall-clock includes CLI process startup, imports, agent logic, scoring, comparison, report generation and local I/O. The applications have different work, so **2.342 s versus 2.613 s is not a framework speed ranking**.
- **Quality evidence:** 2/2 planted application defects detected in their corresponding benchmark scenarios; this is not a statistical estimate of sensitivity to unseen defects, false-positive rate or genuine model nondeterminism.

All timings and counts must be rechecked on the specific CI run before a leadership presentation. Refer to [benchmark definitions](BENCHMARKING.md) and [resilience matrix](RESILIENCE.md).

## Value hypothesis and measurement plan

The organisational proposition is **one reusable evaluation contract** instead of every delivery team independently assembling testing, tracing, scoring and regression reporting. This could improve onboarding speed and repeatability, but its effect size is not yet known.

| Outcome to test | Method | Current number |
| --- | --- | --- |
| Time to first passing evaluation | Independent engineer, same pre-agreed task, AEA vs a credible control workflow | Not measured |
| Time to introduce and diagnose a regression | Identical planted defect; measure complete investigation time and success | Not measured |
| Effort to integrate a second framework | Record agent factory, mappings, test authoring and configuration time | Not measured |
| Reliability of quality gating | Multiple clean reruns plus defect trials; report unexpected failure rate | Local deterministic cases only |
| Quality and breadth of detected issues | Pre-register failures and controls, compare true detections/false alerts | Known planted cases only |
| Multi-team adoption | Two separate delivery teams run their own approved projects and record feedback | Not completed |

If a comparable manual/control task takes `M` observed minutes and the AEA version takes `A` observed minutes, report `(M - A) / M × 100%`, **only when M > 0** and scope/outcomes are matched. Report individual timings, task order, sample size and uncertainties rather than an unsupported single organisation-wide average.

## Risks and responsible claims

**Safe claim:** “We have a reusable technical evaluation framework with two locally validated adapters, repeatable CI regression gates and a synthetic fault-detection demo.”

**Not yet supportable:** “AEA saves 50% of engineering effort”, “is adopted by three teams”, “is provider-independent for every deployment”, “is production-certified”, or “beats framework X”.

For confidential work, address local storage, log and trace metadata, optional raw capture, previous baseline retention and Windows ACLs. Reviewed agent factories and scorers run in-process with Python permissions. Follow the [security assessment](DEPENDENCY_SECURITY_REVIEW.md).

## Recommendation to leadership

**Approve an independent two-project synthetic pilot with measured onboarding effort.** Keep the scope bounded: one Strands and one LangGraph application, one fixed test set each, a matching control task, a planted defect, explicit data classification and a reviewer. Accept/reject release only after real evidence, governance approval and the [v2.2.0 release checklist](RELEASE_CANDIDATE_CHECKLIST.md). Do not promote `master` based solely on the synthetic results.
