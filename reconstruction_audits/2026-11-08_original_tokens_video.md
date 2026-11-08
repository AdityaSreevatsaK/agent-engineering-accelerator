# AEA original tokens accounting video reconstruction

Date: 8 November 2026. Source: user-uploaded `test-unit-test_tokens.py.webm` complete Notepad++ recording. Target: `reconstruction/wip-checkpoint-2026-10-30`, not `master`.

## Original source measurements

| Measure | Video original | Reconstructed candidate |
| --- | ---: | ---: |
| Windows CRLF editor characters | 14,000 | 14,000 |
| Displayed Notepad++ lines | 384 | 384 |
| Top-level test functions | 27 | 27 |

Recovered 383 LF-terminated physical code lines plus the final blank editor line. Normalised LF chars: 13,617. SHA256 of recovered candidate: `09a1a21768426df21a87a5be7d821639ecf954a41459b48372f16d454a313e50`. AST parses on Python 3.11+. Text was recovered by visual transcription of the user's overlapping scrolling frames; **matching video counts do not prove historical original-byte equality**.

## Original behaviour under test

- Case input/output token arithmetic over repeated epochs, missing and malformed usage metadata.
- Run-level token summaries, non-reporting case exclusion and thousand separators.
- Input/output pricing pairs, invalid negative/missing/NaN prices and four-decimal estimated cost formatting.
- HTML/Markdown-like run and compare report token rows, missing token text and regression independence from token increases.
- CLI pricing rejection, paid-token usage calculation and a local-only Strands simulated token model defined in the original test source.

## Explicit unavailable fixture limitation

The user previously confirmed that original `tests/fixtures/calculator_capture_content.json` bytes cannot be provided. The original file is a large minified capture; no faithful original reconstructed JSON is available. The original video test file references this fixture in seven functions. These seven tests are **BLOCKED**, not silently skipped as passing or supplied with fabricated original data.

`reconstruction_tools/replay_tokens_without_original_capture.py` checks the full video source digest and AST and replays **17 fixture-independent original unit test functions plus 3 original offline CLI test functions** directly from the unmodified recovered test source, with original parametrisations preserved. This is not an original-source replacement.

Dedicated GitHub Actions CI: Windows/Linux x Python 3.11/3.12, real Inspect AI, AEA and Strands dependencies, no AWS credentials, no external model calls. Any future functional simulation for the seven blocked cases must remain labelled **synthetic, not original**.

## Status

One new original-path source candidate `tests/unit/test_tokens.py` restored if merged. Historical original path presence increases from 81/117 to **82/117** upon merge. Source authenticity and test execution coverage are separate measures. Pairwise judge video was also uploaded and remains pending separate full transcription. `master` unchanged.
