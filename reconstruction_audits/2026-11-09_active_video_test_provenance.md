# Active recovered-test source provenance — 9 November 2026

## Scope and confidence

This is a new preservation guard, **not a claim of byte-accurate reconstruction**. All five historical test-file paths were already restored in the reconstruction branch. This PR adds no new historical paths and does not change source tests, stored video fragments or master.

Original Notepad++ recordings established test lengths, screenshots and editor line counts. We can compare saved intermediate transcriptions with active tests without replaying the original videos. The guard pins reviewed source blobs and reports editor-length discrepancies. Green native tests do not settle missing or uncertain source characters.

## What can be verified exactly

- **LangGraph adapter**: 12 saved fragments cover editor lines 1–1006 with no gap, overlap or missing text. Concatenating them reproduces the complete active tests/unit/test_langgraph_adapter.py **exactly**. The active candidate has 1,006 physical lines and 48 top-level tests, and remains **25 Windows-CRLF-equivalent characters shorter** than the recorded editor's 39,027. Do not pad or invent those 25 characters.
- **Triage**: active tests/unit/test_triage.py equals reconstruction_drafts/test_triage_FULL_VIDEO_CANDIDATE.py. The candidate has 16 tests, 438 physical lines (439 displayed), 19,400 LF characters, and is **5 displayed lines and 447 characters shorter** than the recorded source.
- **Expense**: active tests/unit/test_expense.py equals reconstruction_drafts/test_expense_FULL_VIDEO_CANDIDATE.py. The candidate has 31 tests, 653 physical lines (654 displayed), 29,000 LF characters, and is **2 displayed lines and 84 CRLF-equivalent characters shorter** than the original.
- **Helpdesk**: original-path candidate has 19 tests, 413 physical lines and 16,799 characters; original editor had 454 lines and 20,015 characters. The saved initial source fragment is **not** an exact prefix of the active test. Do not call these identical.
- **Policy RAG**: original-path candidate has 25 tests, 367 physical lines and 14,525 characters; original editor had 416 lines and 18,377 characters. Its initial source fragment also differs from the active test.

Every active test source is anchored to a reviewed Git blob identity, checked by a dependency-free Python audit. The two direct copies and all LangGraph fragments are additionally checked for equality. Seven regression tests demonstrate that altered source, modified or missing fragments, mismatched archives and invalid line-ending metadata are rejected.

## How to run

~~~sh
python -m reconstruction_tools.verify_active_video_test_provenance
python -m unittest reconstruction_tools.test_active_video_test_provenance -v
~~~

CI uses Python 3.11 and 3.12 on Windows and Ubuntu. No agent framework or provider dependencies are installed for these checks.

## Interpretation for release

The five executable files may pass behavioural tests while remaining non-identical to historical original source. Any later candidate edit must be backed by a review of actual source evidence and an explicit update of the audited pinned manifest.

Do **not** present 97/117 historical-path presence as 97 certified originals. The 20 missing historical files and outstanding transcription differences still block a full source-fidelity claim. Keep master unchanged.
