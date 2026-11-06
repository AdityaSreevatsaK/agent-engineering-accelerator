# AEA reconstruction Part 45: Original calculator rules from new video

**Date:** 6 November 2026  
**Integration branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Source evidence:** The user's original `calc_rules.py - video.webm`, 1920×1080, Notepad++ source editor recording, showing full `examples/calculator/rules.py` from top to bottom.

## Original recovered source

The reconstructed source has **2,030 UTF-8 characters** with LF-only line endings, **56 physical lines ending in a newline**, and **57 displayed Notepad++ lines**, matching the editor's status bar (length 2,030, lines 57). Overlapping video frames cover every source line and show the original formatting and code. It has been restored to **`examples/calculator/rules.py`** as an original-video-derived candidate (not a new invented module).

Visible components:
- `SYSTEM_PROMPT`, `OPERATIONS`, `BROKEN_OPERATIONS` with subtraction intentionally mapped to addition.
- `_EXPRESSION` regex and arithmetic `calculate` including zero-division and unknown-operation responses.
- Frozen `ToolRequest` dataclass; `_number` integer/float normalisation.
- `decide` handling arithmetic tool requests versus direct non-arithmetic reply.
- `answer` handling failed tool execution, numeric output and JSON result.

**Fidelity:** Exact editor length and displayed line count are unusually strong evidence of complete transcription, but are not an independent original-source byte checksum. The restored module is text only, with no encoded credentials or model keys.

## New verification

- `reconstruction_tools/verify_calculator_video_sources.py` now requires the full agent, dataset and rules, checks the 2,030/57 count, AST syntax and exported classes/functions.
- `tests/unit/test_calculator_rules_video.py` adds pure unit tests of historical dataset arithmetic, broken subtraction, division by zero, response formatting and unchanged source counts.
- Existing CI workflows no longer generate the legacy temporary, non-executable `rules.py` import shim. The user-provided recovered source is now exercised unchanged.
- `reconstruction_tools/verify_original_calculator_e2e.py` exercises the **actual video-recovered calculator agent and rules** using Strands and a real AEA CLI in a disposable directory. It checks normal **10/10**, broken **8/10**, subtraction-only differences, and seeded flaky behaviour over two epochs. It then compares normal to broken and asserts a nonzero regression verdict.
- The four-platform offline E2E CI gate (Windows/Linux, Python 3.11/3.12) runs both the previously verified generic starter and restored real calculator.

## Capture video / historical log boundary

The user also uploaded `calculator_capture_content - video(1).webm`. This is a second recording of the full original **one-line minified Inspect JSON**, approximately **57,844 original editor characters**, with visible log envelope, 10 passing cases and `capture_content: true`. This video is not the original JSON byte file, and reproducing precise timestamps, trace IDs, event payloads and serialized ordering solely from footage is **not yet reliable**. Do not generate a fake historical `tests/fixtures/calculator_capture_content.json` from assumptions, and do not silently substitute the synthetic CI capture. Exact original log byte recovery and its 58 deferred parameter-expanded tests remain pending until reliable full-content recovery.

Also missing original `tests/fixtures/calculator_broken_redacted.json` (screenshot-derived candidate kept separately), original triage and expense configs (2 deferred), plus other historical samples and baseline files. The old 60 deferrals remain explicit and unchanged.

## Acceptance boundary

Merge only after all 10 GitHub PR workflows finish green (the usual 37 jobs), and after the review branch's 8 post-merge checks. Do not merge incomplete v2.2.0 reconstruction into `master`. Do not claim that a successful local deterministic run proves byte-level fidelity of the original historical Inspect capture.
