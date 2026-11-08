# AEA reconstruction: original trace-summary test recording

**Date:** 8 November 2026.
**Original path:** `tests/unit/test_trace_summary.py`.
**Video evidence:** user-uploaded `test-unit-test_trace_summary.py.webm` (complete scrolling Notepad++ editor recording).
**Integration branch:** `reconstruction/wip-checkpoint-2026-10-30`; master is untouched.

## Original source fidelity

| Measurement | Original editor | Reconstructed video candidate |
| --- | ---: | ---: |
| Displayed editor lines | 257 | 257 |
| Unix LF characters | 7,697 | 7,697 |
| Original top-level test functions | 13 | 13 |

The recovered source is present at the exact original path and parses under Python 3.11 AST. Candidate SHA-256 (normalised LF): `c979c3b39039932209b0290a3ab98ab3386852fd98941145b90a118eaef617de`. `reconstruction_tools/verify_trace_summary_original_video.py` pins those counts, the hash and all original test names.

The video includes source lines 1 through 256 and the final blank Notepad++ line 257, without gaps. The video counts and passing runtime tests support a high-fidelity candidate but do **not** prove lost original source bytes were identical.

## Original test coverage

- Strands `gen_ai` chat/tool spans vs LangGraph OpenInference `LLM`/`TOOL` spans.
- Equivalent model/tool call counts and call ordering, including missing tool-name attributes.
- Nested non-model/non-tool spans; only tool status ERROR is counted as a tool failure.
- Per-model and per-tool elapsed time summation vs root total duration.
- Root epoch extraction/default, numeric case IDs returned as strings.
- Ignoring spans with no `eval_case` root, skipping blank JSONL lines and sorting by case ID then epoch.

## Verification

A dedicated GitHub Actions matrix runs actual original recovered test source on Windows/Linux and Python 3.11/3.12, with normal installed AEA dependencies. It uses temporary trace JSONL data constructed by the original test source; no cloud credentials, LLMs or historical calculator captures are needed.

Restores one original historical path. After merge, historical path presence increases **76/117 → 77/117**, with 40 remaining. This does not resolve the existing source fidelity gaps in other files. Other recordings can be reconstructed independently.
