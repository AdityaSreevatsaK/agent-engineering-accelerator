# AEA reconstruction checkpoint — 4 November 2026 (Part 6)

**Status: provisional transcriptions; do not merge to master.**

| Module | Previous coverage | Current coverage | Unique tests |
| --- | ---: | ---: | ---: |
| `tests/unit/test_readings.py` | 1,256 | **1,605 / 1,605 displayed lines** | 66 |
| `tests/unit/test_judge.py` | 904 | **1,098 / 1,560 displayed lines** | 64 |

**543 additional source lines reconstructed** in this continuation. The two drafts are stored in `reconstruction_drafts/`, not the active `tests/unit/` tree. Python 3.11 AST parsing and compilation passed, and no duplicate top-level test names were found. Both GitHub source blobs were checked after upload and matched the saved drafts.

Latest paths:

- `reconstruction_drafts/test_readings_FULL_DRAFT.py`, commit `3bcf11b`
- `reconstruction_drafts/test_judge_PARTIAL_lines_1_1098.py`, commit `200c8e7`

## Unresolved fidelity and integration matters

1. The original `test_readings.py` editor reported **67,194 characters** (Windows/CRLF); the new full draft's CRLF-equivalent length is **67,175 characters**, a **19-character shortfall**. Complete visible coverage is not byte-for-byte fidelity. Do not pad arbitrary characters.
2. `test_judge.py` still needs original lines **1,099–1,560**.
3. The original judge tests import `data_marker` and `tool_results_text`, but provisional `judge.py` defines only `_data_marker` and `_tool_results_text`. No speculative alias was committed.
4. The full readings draft references 21 `readings.py` names; all exist in the checkpoint implementation. This is only a static source-contract check.
5. Native pytest, original JSON-fixture validation, Windows/Linux CI, and final fidelity review have **not** passed. The local environment lacks Inspect AI, LangGraph, Strands and LangChain Core.
6. `master` remains unchanged.

**Next priorities:** finish judge tests from line 1,099; reconcile readings 19-character difference; reconstruct `test_cli.py`, `test_report.py`, and `test_judge_pairwise.py`; then run original offline tests and CI before merging.