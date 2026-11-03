# AEA reconstruction continuation - 3 November 2026

**Branch:** `reconstruction/wip-checkpoint-2026-10-30`. **Do not merge into `master` yet.**

## New source work

| File | Source coverage | Validation | GitHub |
|---|---|---|---|
| `tests/unit/test_readings_pairwise.py` | 156 physical lines, final blank editor line 157 | Python 3.11 AST syntax; 10 test functions | Saved as provisional complete video reconstruction |
| `tests/unit/test_readings.py` | Lines 1–677 of 1,605 displayed | Python 3.11 AST syntax; 28 top-level test functions | Saved under `reconstruction_drafts/`, outside pytest collection |
| `tests/unit/test_judge.py` | Lines 1–163 of 1,560 displayed | Python 3.11 AST syntax; 8 top-level test functions | Saved under `reconstruction_drafts/`, outside pytest collection |

`test_readings_pairwise.py` has a **one-character** difference from the original Notepad++ CRLF count (reconstructed 6,825, recorded 6,826). This is a fidelity review gap, not evidence of a substantive defect. Do not add arbitrary padding.

## New test-supported implementation mismatch

The reconstructed original pairwise readings test asserts that case IDs are listed **once**, even if the same case has multiple judged epochs.

The checkpoint version of `readings.py` currently contains these constructions in `_pairwise_readings`:

- `worse = sorted((e.case_id for e in epochs if e.pairwise == "worse"))`
- `_names(sorted((e.case_id for e in disagreed)))`

Neither expression deduplicates case IDs. With judged outcomes `c worse, a better, b worse, c worse`, the first constructs `['b', 'c', 'c']`, while the original test expects `b and c`. With two order disagreements for `a` and one for `b`, the second produces `a, a and b`, while the test expects `a and b`.

**Status:** Static cross-file contradiction established. The original `readings.py` source recording still needs a direct check of these two lines before modifying the reconstructed implementation; the test's original footage is directly readable. No speculative code changes made.

The previously identified `test_judge.py` import mismatch (`data_marker` and `tool_results_text` versus private `_data_marker` and `_tool_results_text` in the saved implementation) remains unresolved.

## Other videos

The five videos `test_report.py`, `test_cli.py`, `test_export.py`, `test_judge_pairwise.py`, `test_readings_pairwise.py` all contain readable Notepad++ source frames. The recordings are accessible locally. The first four still require their full source transcriptions; the fifth is provisionally reconstructed here.

## Validation limits

- Python 3.11 syntax parsing was performed using `ast.parse(feature_version=(3, 11))` and compilation.
- No original native pytest suite has passed. `inspect_ai`, `langgraph`, `strands` and `langchain_core` are not installed in this local environment.
- The full project still lacks original fixtures and a functioning CI test verdict.
- No paid-model API calls or cloud services used, and `master` remains unchanged.
