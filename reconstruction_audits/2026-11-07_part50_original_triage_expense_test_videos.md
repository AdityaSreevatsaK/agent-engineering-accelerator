# AEA source recording audit: original triage and expense tests (Part 50)

**Date:** 7 November 2026  
**Base:** `reconstruction/wip-checkpoint-2026-10-30`, commit `bc62b5fb`.  
**Evidence:** two newly uploaded Notepad++ scrolling WebM recordings, respectively `tests/unit/test_triage.py` and `tests/unit/test_expense.py`. Both source views extend through their final recorded code lines.

## Provisional source recovery

| Original historical test | Recorded editor dimensions | Video-transcribed candidate | Functions | Discrepancy |
| --- | --- | --- | ---: | --- |
| `tests/unit/test_triage.py` | 444 displayed lines, 19,847 characters (LF) | `reconstruction_drafts/test_triage_FULL_VIDEO_CANDIDATE.py`: 439 displayed lines, 19,400 characters (LF) | 16 | 5 displayed lines and 447 characters shorter |
| `tests/unit/test_expense.py` | 656 displayed lines, 29,737 characters (CRLF) | `reconstruction_drafts/test_expense_FULL_VIDEO_CANDIDATE.py`: 654 displayed lines, 29,653 reconstructed CRLF characters | 31 | 2 displayed lines and 84 characters shorter |

**Neither candidate is represented as byte-perfect original source.** Do not add guessed filler text to obtain a matching character count. Candidate contents preserve the recovered original tests, parameterisations and source comments to the extent visible. They parse under Python 3.11 AST and have pinned source hashes. Any source-draft changes require further frame review.

The recordings expose original tests of rule classification, specialist routing, model doubles, input/output mapping, prompt regressions, live-model construction without actually invoking AWS, per-diem, receipts, lodging, referrals, currency conversion, grounding scorers, golden reference expectations, and full dataset CLI regressions.

## Tests and missing dependencies

- `reconstruction_tools/replay_original_video_test_candidates.py` selects **14 triage and 24 expense original test functions** (38 distinct top-level functions) with their parameterisations and exercises their unchanged bodies using the actual reconstructed examples. A staged temporary copy is created inside `tests/unit` only so original `REPO = Path(__file__).parents[2]` resolves correctly.
- The original expense video imports `examples.expense.scorers:amounts_grounded` and `ungrounded`. This original `examples/expense/scorers.py` is **NOT YET RECOVERED**. For the 24 selected original expense policy tests only, one explicit original import line is suppressed in the **temporary replay copy**. The stored source draft remains unchanged. No scorer behaviour is guessed or mocked as historical source.
- The original triage and expense golden tests require `examples/triage/golden.jsonl` and `examples/expense/golden.jsonl`. User already supplied screenshots of those files in prior messages, but they are **not yet restored to GitHub**. Do **not** request the existing screenshots again.
- The source original includes `@pytest.mark.slow` CLI dataset tests that can be replayed separately after dependencies are restored. The currently selected 38 functions avoid these to keep a bounded, fast cross-platform gate.
- All historical source-draft test definitions remain preserved, even if not selected in the initial replay.
- No paid cloud providers, credentials, AWS calls, generated replacement golden files, or master-branch commits.

## Inventory impact

The prior original-path inventory was 61 of 117. The original `tests/unit/test_triage.py` and `tests/unit/test_expense.py` source candidates are retained under `reconstruction_drafts/` **rather than being promoted into original paths** before the 84/447-character transcription gaps and missing original dependencies have been resolved. **Original-path presence therefore remains 61 of 117** in this PR. The draft/test runner files are new verification artefacts, not claimed original historical paths.

## Gate

Four-platform Python 3.11 and 3.12 on Windows/Ubuntu, existing integrated offline/quality jobs, and test-candidate/source-drift audit. Merge into the reconstruction branch only if all CI checks are green. Source-byte fidelity, the original expense scorer and original golden references remain release acceptance gaps.
