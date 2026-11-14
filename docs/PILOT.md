# AEA internal adoption pilot

**Status:** Proposed. No adoption or productivity gains have been measured yet.

## Objective

Confirm that engineers who did not build AEA can use it to evaluate an existing agent workflow, detect an introduced regression and interpret the report, without needing bespoke AEA changes.

Run two small independent pilots: **one Strands workflow and one LangGraph workflow**, preferably from separate delivery teams. Keep the first evaluation entirely synthetic or use data explicitly approved for this test.

## Automated rehearsal before independent adoption

Run a repeatable local dry run against the shipped synthetic calculator agents for **both** frameworks:

```sh
uv run --locked python scripts/pilot_rehearsal.py --output-dir pilot-rehearsal-output --repeats 3
```

The script refuses to overwrite existing output, freezes a separate redacted baseline for each adapter, performs three unchanged comparisons, introduces a known defective agent, verifies regression exit code 1 and checks baseline integrity. Review `pilot-rehearsal-output/REHEARSAL.md` and `evidence.json`. The CI release job performs a shorter `--repeats 1` rehearsal.

**This is not proof of adoption by independent delivery teams.** It verifies a repeatable technical workflow only. Use the blank [independent pilot evidence worksheet](PILOT_EVIDENCE_TEMPLATE.md) for the two external integrations and actual measured outcomes.

## Pilot set-up

1. Select an existing agent entry point for each framework that can run locally with a deterministic or approved model double. Record the team's current manual regression process and its set-up time.
2. Ask an engineer unfamiliar with AEA to follow the [README](../README.md) and [usage guide](USAGE.md). Record time from first installation attempt to the first valid evaluation report, including troubleshooting.
3. Create a small JSONL dataset, initially 10 to 20 representative cases, with answer and tool-behaviour expectations. Record case-authoring time and any adapter/mapping changes.
4. Freeze a baseline with `aea check --update-baseline`. Rerun the unchanged agent three times; inspect pass/fail, traces, summary and run-to-run consistency.
5. Introduce one controlled, known defect in a disposable feature branch. Run `aea check` again and confirm a regression result and actionable report. Verify that the approved baseline remains untouched.
6. Add the offline check to the delivery team's existing PR pipeline. Do not add any billable model calls to unattended CI.
7. Collect feedback from the non-author engineer and the team's technical lead. Revert the injected defect and record any onboarding blockers.

## Measurement worksheet

Use the same cases and task boundaries for AEA and the team's existing testing approach. Record **observed values**, not estimates, and avoid counting infrastructure or unrelated work.

| Measure | How to record | Proposed success threshold |
| --- | --- | --- |
| Independent set-up time | Minutes from checkout to first valid evaluation report | No more than 30 minutes for a documented local example |
| Integration effort | Engineer-hours to plug in one existing agent factory and mappings | No bespoke changes in AEA's source |
| Authoring productivity | Minutes per validated evaluation case, compared with current method | At least 20% faster, or a clearly documented quality improvement |
| Defect detection | Injected faults caught / faults introduced | 100% for the agreed controlled defects |
| Repeated-run stability | Three unchanged runs compared with the same baseline | No unexpected regressions under deterministic conditions |
| CI reliability | Successful / attempted offline PR checks | No unexplained failures in the pilot |
| Interpretation | Can another engineer explain the failure and locate the relevant case? | Both pilot engineers answer yes |
| Adoption | Independent teams demonstrating an integrated workflow | Two teams, not simply two demos by the toolkit author |

The thresholds are **targets for a pilot**, not claimed results.

## Evidence to retain

For each pilot, save an onboarding timeline, anonymised dataset schema, CI job link, pass/fail totals, defect description, baseline integrity evidence, issues encountered, and a short engineering recommendation. Keep confidential prompts, customer documents and captured model payloads out of public repositories and shared reports.

Suggested record structure:

| Pilot field | Result |
| --- | --- |
| Team or project alias | |
| Framework and entry-point type | |
| Data classification approved? | |
| Starting manual QA approach | |
| First valid run: minutes | |
| Number of cases and tool checks | |
| Case-authoring time: AEA / existing approach | |
| Injected defect detected? | |
| Baseline unchanged? | |
| Repeatability: three runs | |
| CI job and report reference | |
| Adoption blockers and proposed fixes | |
| Technical lead sign-off | |

## Go/no-go

Proceed towards an internal release only when the two teams can reproduce the workflow, the expected regressions are detected, no unacceptable data disclosure is identified, and the security/release owner approves the intended data handling. Pilot success alone is not approval to use confidential production data.

The current automated suite covers local correctness, package installation, cross-platform operation and one deliberate regression. **Live provider stability, pricing, credentials, network failures, client retention policies and team adoption still require separate evidence.**
