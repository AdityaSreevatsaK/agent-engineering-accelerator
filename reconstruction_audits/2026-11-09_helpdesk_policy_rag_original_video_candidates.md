# AEA historical helpdesk and policy RAG test video review

Date: 9 November 2026

## Source evidence
The user uploaded complete Notepad++ scrolling videos of:
- `tests/unit/test_helpdesk.py`: original editor **454 lines, 20,015 characters, Unix LF**.
- `tests/unit/test_policy_rag.py`: original editor **416 lines, 18,377 characters, Unix LF**.

## Recovery
This PR stages runnable, source-video-derived candidates at their historical paths:
- Helpdesk: **413 lines**, 16,799 LF characters, **19 top-level tests**.
- Policy RAG: **367 lines**, 14,525 LF characters, **25 top-level tests**.

Tests and parameterisations were reconstructed from line-numbered frames, supported by source excerpts already retained in `reconstruction_drafts/`. Source comments and some whitespace are still not fully recovered. The staged files **are not byte-for-byte faithful originals**. Path presence is separate from source-fidelity certification. In particular, missing 41/49 lines must not be silently filled with fabricated content merely to reach the editor line totals.

## Verification
A new offline four-platform workflow directly runs both historical-path candidates with native LangGraph/Inspect AI dependencies. The integrated unit regression also collects both files. Use actual CI errors and the recorded screenshots to correct verified transcription mistakes. Do not alter recorded assertion intent simply to obtain green tests. No cloud provider calls or secrets in CI.

## Remaining original evidence gaps
The two original calculator capture JSON fixtures remain unavailable by user confirmation. This PR does not attempt to fabricate them. Source review, evidence collection and release-readiness remain separate from successful test execution.

Target `reconstruction/wip-checkpoint-2026-10-30` only; do not change `master`.
