# AEA reconstruction: test_stats.py original recording (Part 59)

Evidence: user-uploaded `test-unit-test_stats.py - video.webm`, 7 November 2026.
Integration target: `reconstruction/wip-checkpoint-2026-10-30`; master stays untouched.

## Original editor dimensions

- Video shows all source lines 1 through 224 and a final blank editor line 225.
- Notepad++ status bar: length 9,782; lines 225; Windows (CR LF); UTF-8.
- Reconstructed candidate: 224 physical LF-terminated source lines; 225 editor lines, 9,558 normalised LF chars and 9,782 CRLF-equivalent chars.
- SHA-256 of normalised candidate: `1e4fc1a63febefd2e1930706cd609586d73179905ed32ea8e4f7b0eb35f7e852`.

## Original behavioural coverage

The recovered recording includes 16 original parametrised test functions, with exhaustive enumerated cases, not synthetic replacement assertions:

- Wilson score 95% confidence intervals: numeric reference cases, score-equation roots, exact endpoints, zero runs, z=0 degeneracy, impossible input counts.
- Unbiased pass@k and pass^k: exact small-sample fractions, exhaustive k-subset enumeration and input validation.
- One-sided Fisher tail for a lower current pass rate: hand-computed fractions, exhaustive placement enumeration, monotonicity, zero current runs and invalid counts.

These tests include mutation-witness comments from the source and are executed directly against the actual recovered `agent_accelerator.stats` module with no paid model calls.

Dedicated CI runs on Ubuntu and Windows, Python 3.11 and 3.12. The video-source verifier pins source digest, editor counts, AST syntax and all test names. Tests are the recovered source itself, not rewritten into test substitutes.

## Fidelity boundary

Matching Notepad++ editor dimensions, AST and test outcomes gives strong corroboration, **not proof of lost source byte equality**. The full source video remains original evidence. Any future byte-identical source comparison must be documented separately.

Restores one historical original path once merged; original-file presence 74/117 to 75/117. `test_run_metrics.py` is a separately uploaded 507-line video and remains pending full transcription; do not misclassify this PR as restoring it.
