# AEA reconstruction Part 56: Original full-CLI prompt regression replay

Date: 7 November 2026.
Target branch: reconstruction/wip-checkpoint-2026-10-30; master untouched.

## Original evidence and newly runnable tests

Original video transcripts available as:
- reconstruction_drafts/test_triage_FULL_VIDEO_CANDIDATE.py
- reconstruction_drafts/test_expense_FULL_VIDEO_CANDIDATE.py

Both drafts contain a @pytest.mark.slow test whose original body launches the actual AEA CLI in a separate subprocess and verifies every one of 12 dataset cases.

| Source | Original parameter IDs | Expected failure set |
| --- | --- | --- |
| Triage good prompt | good_prompt | none |
| Triage reworded prompt | reworded_prompt | charged_twice_furious, angry_invoice_dispute |
| Expense full prompt | full_prompt | none |
| Expense condensed prompt | condensed_prompt | receipt_missing_over_75, receipt_missing_after_conversion, reject_no_receipt |

After recovery of original agent and scorer modules, both 12-case datasets and the screenshot-derived golden files, all four original parameterisations can now run against real AEA CLI, LangGraph, Inspect AI and run comparison loading.

## Implementation

- reconstruction_tools/replay_original_example_slow_cli.py validates the immutable source candidates and restored screenshot golden files, then stages each original candidate as a temporary source under tests/unit without modifying its contents.
- It runs exactly the original @pytest.mark.slow test selector for each suite, letting pytest expand its two original variants. Each test creates a fresh CLI subprocess, avoiding OpenTelemetry provider reconfiguration across executions.
- The original source candidates have known editor-count discrepancies and remain immutable provisional evidence. A green test does not establish historical source-byte identity.
- A four-platform Ubuntu/Windows by Python 3.11/3.12 workflow runs each suite independently. Provider credentials are blanked; model doubles are offline and paid APIs are never requested.
- Earlier fast original-video test replay comments are updated because the golden/slow cases now have separate replay lanes.

## Validation scope and limitations

Passing these four original test parameterisations shows that full CLI evaluations catch planted triage and receipt-policy regressions, including per-case result aggregation, rather than merely passing unit tests. These 4 x 12 = 48 case evaluations happen on each OS/Python matrix combination (192 aggregate across four jobs).

This is **new coverage**, not additional historical original file recovery: the source-file count remains 66/117. It does not resolve the known scorer explanation disagreement or the 5-line/447-character triage and 2-line/84-character expense test source count gaps. Missing original calculator capture bytes remain unrecoverable from the current evidence.
