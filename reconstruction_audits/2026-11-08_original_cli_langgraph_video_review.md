# AEA original CLI and LangGraph adapter video review (8 November 2026)

## Evidence
Two new user-supplied WebM screen recordings (Notepad++ on Windows):
- `test_cli.py - video(2).webm`: editor status at 00:58 shows **1,133 lines; 47,911 characters; Windows CRLF**. This is source evidence, not original file bytes.
- `test_langgraph_adapters.py - video(2).webm`: editor title is **`tests/unit/test_langgraph_adapter.py` (singular adapter)**; editor status at 00:45 shows **1,006 lines; 39,027 characters; Windows CRLF**.
- The videos are not committed to GitHub. Original user-provided video stays in conversation evidence.

## CLI candidate comparison
Existing `reconstruction_drafts/test_cli_FULL_VIDEO_CANDIDATE.py` has **1,133 logical lines; 47,850 CRLF-equivalent characters; 59 top-level test definitions**.
- Exact line-count match, but **61 characters short**, so original source fidelity is **not** certified.
- Visible anchors in video at source lines **877** (`def flags`), **881** (`def recorded`), and **886** (`test_config_fills_every_run_setting_left_off_the_command_line`) match the candidate line numbers and text.
- This branch stages a **candidate**, not a verified original, at `tests/unit/test_cli.py` to expose real fixture/runtime discrepancies.
- Source contains `FAILING_DATASET = "<failing dataset>"`; this placeholder must be reconciled rather than treated as proven historical code.
- The original fixture paths `tests/fixtures/calculator_capture_content.json` and `tests/fixtures/calculator_broken_redacted.json` are unavailable. Do **not** fabricate or label synthetic substitutes as originals.
- Existing `reconstruction_tools/run_original_cli_fast_replay.py` already executes selected fixture-independent tests from the provisional candidate. Its separate test coverage is meaningful but not full-file certification.

## LangGraph adapter original test
- New video covers source sections from the initial imports through the lower test cases. Recording status confirms **1,006 lines, 39,027 characters**.
- The historical file `tests/unit/test_langgraph_adapter.py` is still absent on the integration branch; there is no complete existing video transcription to compare.
- Do **not** add an inferred 1,006-line file as if it were recovered source. Independently reconstruct visible source and verify collection and Windows/Linux behaviour before promotion.

## Merge rules
1. Diagnose real failures from the staged original CLI candidate without suppressing missing fixture errors.
2. Preserve original source evidence; do not pad file lengths or silently rewrite recorded assertions.
3. Only merge when CI is green on the final commit and fidelity limitations are accurately documented.
4. Target reconstruction integration branch only; `master` stays unchanged.

This audit is newly authored reconstruction documentation, not a historical AEA file.
