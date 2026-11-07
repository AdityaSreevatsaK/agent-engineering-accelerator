# AEA original example JSONL source recovery: triage and expense (Part 49)

**Date:** 7 November 2026  
**Base:** `reconstruction/wip-checkpoint-2026-10-30` at `8a46c658`  
**Source:** TWO original uploaded Notepad++ WebM recordings, `examples-triage-dataset.jsonl - video.webm` and `examples-expense-dataset.jsonl - video.webm`. Both were already provided in the conversation and should not be requested again.

| Original file | Records | Editor lines | Recorded editor length (Windows CRLF) | Reconstructed normalised LF characters | Reconstructed CRLF length | Assessment |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `examples/triage/dataset.jsonl` | 12 | 13 | 6,218 | 6,206 | 6,218 | Count-matched video-derived candidate |
| `examples/expense/dataset.jsonl` | 12 | 13 | 10,974 | 10,962 | 10,974 | Count-matched video-derived candidate |

Full 12-record JSONL sources were transcribed with original record ordering, schema assertions, input strings, expected/forbidden tool requests, argument contracts, maximum tool counts and expected output constraints. JSON parsers and the **actual original AEA `Case` Pydantic model** check every line. Source hashes are pinned in `reconstruction_tools/verify_triage_expense_datasets_video.py`, failing closed if files change.

## Discrepancies investigated with original video evidence

- Triage first candidate was 38 CRLF characters too short. A close reading of `invoice_paid_status` showed `"output_not_contains": ["escalated"]` that had initially been missed. Restoring that exact visible field reconciled the original **6,218** editor count, rather than adding arbitrary filler.
- Expense first candidate was four CRLF characters too short. A zoom of the `approve_clean` record revealed the original uses `"output_not_contains": ["reason"]` rather than the initially misread `output_contains`. The correct screenshot-derived key adds exactly four characters, reconciling **10,974**.
- Editor count agreement strengthens the source evidence but is **not proof of byte-for-byte fidelity**. Each candidate remains explicitly video-derived until reviewed against original file bytes.

## Verification and preserved boundaries

- 12 original triage cases and 12 original expense cases, all unique IDs, valid JSONL, validated against the actual AEA dataset schema.
- A dedicated offline verification script runs both LangGraph example agents using their recovered `aea.toml` configurations, simulated deterministic models and real AEA CLI, checking full 12-case runs and ensuring no data-capture mode. The new CI workflow tests Linux/Windows × Python 3.11/3.12.
- No AWS/provider credentials, paid model calls, generated historical fixture substitutes, or commits to `master`.
- Historical original-path presence increases from **59 of 117 to 61 of 117** once the PR is merged (presence only).
- Historical `examples/triage/golden.jsonl` and `examples/expense/golden.jsonl` appear in separate user screenshots already supplied, and are distinct from these dataset recordings.
- Original `tests/unit/test_triage.py` and `tests/unit/test_expense.py` are still needed; original calculator captured Inspect JSON fixtures and 58 cases deferred in the normal suite remain missing.

**Release boundary:** Not byte-certified original source and not an acceptance for `master`.
