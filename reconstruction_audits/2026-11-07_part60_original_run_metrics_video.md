# AEA original metrics video reconstruction (Part 60)

Date: 7 November 2026. Source: `tests-unit-test_run_metrics.py - video.webm` uploaded by the user. Integration branch: `reconstruction/wip-checkpoint-2026-10-30`. Master is not changed.

## Original video evidence

Complete scrolling Notepad++ recording shows original `tests/unit/test_run_metrics.py` from first through last physical code line, plus a final editor blank line. Source status bar records `length: 20,657`, `lines: 507`, Windows CRLF, UTF-8.

Reconstructed original-path candidate has **507 editor lines, 506 physical LF lines, 20,145 LF characters / 20,651 CRLF-equivalent characters**. The video count is **6 characters larger**. These six missing/changed characters are an explicit unresolved fidelity gap. Candidate SHA-256: `64cbe5024e9e19377ce6ce54fbc2995dbb6e5d99c4807cee8e99e87148bbee9f`. No source bytes are fabricated or inserted just to force the recorded editor count.

The video shows **32 top-level original test functions** and several helpers (`sample`, `checks_score`, `epoch`, `case_of`, `run_of`, `section`, `bullets`, `demo_run`), all captured in a Python-3.11-valid transcript.

## Test coverage

- Nearest-rank percentiles and input-preserving order, including invalid inputs.
- Per-epoch latency, token usage, output digest, and named failed checks from native Inspect AI samples.
- Estimated USD cost using per-epoch-averaged usage and both token prices; zero/absent values and cost-per-passing-case edge cases.
- Conditional report sections for performance, failures and consistency.
- Failure check counting by unique case-epoch, check naming, sort, unique cases and Markdown pipe escaping.
- Output consistency by most frequent content digest, missing digest rules, least-consistent sorting, five-entry cap, all-consistent formatting and section order.

## Verification and boundaries

Dedicated audit pins all 32 original test names, source checksum, exact editor line count, CRLF-equivalent count and six-character deviation. Four-platform Windows/Linux Python 3.11/3.12 CI executes the recovered test body directly against real `agent_accelerator.run_metrics` and Inspect AI. No cloud credentials, paid model calls or fabricated historical fixtures.

The video-derived source is a **provisional historical candidate**, not an original-byte certificate. The six-character gap remains visible until resolved by direct source evidence. The file is restored at its original path for runtime verification; count of *historical path presence* rises 75/117 to 76/117 after merge, but fidelity remains separately qualified. `master` remains unchanged.
