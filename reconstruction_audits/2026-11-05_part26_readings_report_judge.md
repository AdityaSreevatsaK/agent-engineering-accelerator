# AEA reconstruction continuation | 5 November 2026 | Part 26: readings, reports and core judge

**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Verified target:** `reconstruction/wip-checkpoint-2026-10-30`  
**Status:** three more video-recovered test suites runtime-verified and merged **to reconstruction branch only**. `master` was not modified in this continuation.

## Delivered: native-tested suites

| PR | Added active test | Source draft preserved | Reconstruction-branch merge |
| --- | --- | --- | --- |
| [#11](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/11) | `tests/unit/test_readings.py` (1,605 physical lines, 66 top-level tests) | `reconstruction_drafts/test_readings_FULL_DRAFT.py` | `11e2715c7a0212e80c611f0497b5e404ce570d09` |
| [#12](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/12) | `tests/unit/test_report.py` (815 physical lines, 45 top-level tests) | `reconstruction_drafts/test_report_FULL_DRAFT.py` | `69f99da4150a11dc54d573107a1c468f9ad8fa11` |
| [#13](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/13) | `tests/unit/test_judge.py` (1,559 physical lines, 86 top-level tests) | `reconstruction_drafts/test_judge_FULL_DRAFT.py` | `2f9510ff2afa89417690d21e665245fc125f34f7` |

Every active-test compatibility correction was isolated in the verification PR. **Original provisional video transcriptions remain unchanged**; neither byte-for-byte original fidelity nor historical behaviour is claimed without original footage reconciliation.

## Failure-driven fixes

### Readings PR #11

The first native pytest run produced **363 passed, 3 failed, 2 errors**.

- Corrected two active-test transcription contracts: `"tool use"` versus the registered note key `"tool_use"`, and a two-parameter `pytest.mark.parametrize` decorator that had only declared `epochs` instead of `epochs, count`.
- `src/agent_accelerator/readings.py`: deduplicated named cases in human/judge disagreement narratives across multiple epochs while retaining per-attempt metrics. This complements an earlier pairwise readings fix.
- `src/agent_accelerator/report.py`: empty Failure table cells now render `| |` rather than `|  |`, restoring the independently recorded pre-readings report snapshot. Non-empty failure text is unchanged.

**CI verification:** GitHub Actions run `42041221076`: **368 passed, 28 warnings** per environment (Ubuntu/Windows × Python 3.11/3.12). Synthetic build/run/scrub run `42041221151`: all four jobs successful and **46 passed** in three directly inspected logs; a fourth job's step and conclusion were successful but its downloaded log was briefly unavailable. All eight jobs were reported successful before merge.

### Report PR #12

First run: **430 passed, 2 failed**.

- Adapted the active recovered test's outdated empty-cell expectation to the verified one-space Markdown cell representation. The raw draft remains unchanged.
- Narrowed a test to exclude *calibration metrics* when no human labels exist, without incorrectly forbidding the judge section's general explanatory note (which mentions human labels conceptually).
- No production source modifications were needed in PR #12.

**CI verification:** run `42041982597`, **432 passed, 28 warnings** in each of four Windows/Linux Python matrix jobs. Synthetic fixture run `42041982364`, **46 passed** in each of four jobs. All eight pytest logs individually verified.

### Core judge PR #13

First run: **601 passed, 11 failed**; ten failures were due to a transcribed test-only fence matcher inconsistent with the current judge source, and one due to malformed fake-agent arguments.

- Fixed the active test's `FENCE_LINE` regex to match actual `<<<BEGIN NAME code>>>` / `<<<END NAME code>>>` blocks and underscore-containing block names.
- Removed an extra regex character from two `BEGIN NAME` marker extraction patterns.
- Changed fake agent fixture `fixed_answers(answers or {}, 0, {})` to `fixed_answers(answers or {}, (), {})`; the second argument is the tuple of case IDs that error. Its prior integer value caused native agent execution errors and missing judge scores.
- **No changes to production `judge.py` or marker semantics.**

**CI verification:** run `42043059879`, **612 passed, 61 warnings** on each of Ubuntu Python 3.11, Ubuntu Python 3.12, Windows Python 3.11 and Windows Python 3.12. All four complete job logs inspected. Independent build/run/scrub run `42043059712`: **46 passed** in all four environments; all logs inspected. All eight jobs confirmed successful before merge.

## Current integration coverage

Two separate CI workflows together validate **658 native pytest cases per environment** (612 judge/readings/report/export/CLI cases plus 46 build/run/scrub cases), with Windows and Ubuntu on Python 3.11 and 3.12. Counts are *pytest parameter-expanded cases*, not source function counts and not a claim of a complete project test suite. The build/run/scrub workflow uses explicitly labelled temporary **synthetic** calculator/example/log inputs; it does not recover original files.

The test cases use the deterministic/mock agent, Inspect AI, and no paid model APIs or cloud credentials. The 61 judge-workflow warnings are reported dependency deprecations, not test failures.

## Remaining fidelity blockers and promotion criteria

1. Original calculator example agent, dataset and JSON log fixtures remain unrecovered. Synthetic test data is not equivalent.
2. `test_cli.py` original editor lines 365 onwards and `test_judge_pairwise.py` lines 510 onwards remain untranscribed; original recordings are currently unavailable as raw frames.
3. Historical source byte fidelity and changed-implementation provenance must be reviewed before promoting the whole reconstruction. Remaining original example/docs/baseline files are not reconstructed.
4. Full repository pytest, packaging lint/type-checking and release-quality CI are not yet verified. More recovered tests can be promoted in *isolated review PRs*, preserving the source-video drafts separately.
5. **Do not merge entire review branch into `master`** until source fidelity, fixtures, native full-suite execution and final acceptance are verified.

This checkpoint documents verified work in the current turn, not background execution or a completed v2.2.0 release.
