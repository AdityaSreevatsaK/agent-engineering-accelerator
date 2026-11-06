# AEA reconstruction Part 46: Source-replayed fixtures for original comparison tests

**Date:** 6 November 2026  
**Classification:** New, separately labelled test compatibility lane, NOT recovered historical fixture bytes.  
**Branch:** `reconstruction/wip-checkpoint-2026-10-30`; do not promote partial historical reconstruction to `master`.

## Rationale

The original calculator agent, shared rules and ten-case dataset are now recovered from user footage. Real Strands/AEA end-to-end verification already confirms a normal 10/10 run, an 8/10 broken-subtraction run and the expected flaky behaviours. The historical October 12 JSON logs themselves are still unavailable as byte-exact files; 51 original parameter-expanded comparison/statistics cases are fixture-dependent. A separate seven-case fixture-independent lane was previously misclassified as slow; together with two missing-example-config cases, these account for the 60 historically deferred/filtered cases seen in the regular integrated suite.

The new **source-replay lane** generates temporary Inspect v2 logs using the real restored calculator agent instead of guessing original timestamps or pasting synthetic JSON stubs.

## Execution

A new script `reconstruction_tools/verify_original_calculator_fixture_replay.py`:

1. Fail-closed checks the original 32-function deferred manifest using its existing AST preflight, and **refuses to overwrite any existing original fixture path**.
2. Runs `examples.calculator.agent:build_agent` with `--capture-content` using the real local Strands model double and real AEA CLI. Checks 10/10 successes.
3. Runs `build_broken_agent` with the ordinary redacted default. Checks 8/10 successes and recorded capture mode.
4. Temporarily stages the generated logs under the two original filenames **only inside the isolated GitHub Actions checkout**, not in the repository or a GitHub artifact.
5. Runs the explicit original fixture-dependent pytest node names, including their parameter expansions. Uses `-o addopts=` to avoid silent skips caused by the historical false slow marker.
   For faithful test compatibility, the **temporary captured replay** removes the modern `case_checks.metadata.tool_call_count` convenience field, because the October 12 original capture (as seen in the video) predates it and the original `test_logs_from_before_tool_call_counts_load_with_none` explicitly asserts this older schema. The current production scorer remains unchanged and is still validated separately.
6. Removes both staged log files **in a finally clause even if pytest fails**. The temporary evaluation directories are destroyed when their context manager exits.

This lane runs after the original calculator E2E in the four-platform starter workflow (Windows/Linux, Python 3.11/3.12). No cloud model API, AWS credentials or personal data are required.

## Crucial fidelity warning: original dataset SHA differs

The October 12 original capture-video screenshot displays a dataset checksum:

`9e2fee82d278bdf408cc890b644a2712752ca639f8c8e85a327d19e53ed5ca0c`

The repository's visually transcribed ten-case dataset currently hashes to:

`b58b684b2a6a702c941278f32d0917a5e7fe4b29af21a144768761e40573cb9a`

Although all ten **behaviours** are reproduced and matched by runtime tests, these SHA-256 values **are not equal**. The dataset's exact historical byte content is therefore **not verified**; differences could be formatting, final newline or content changes. Do not claim that byte-for-byte October 12 original dataset or captured logs have been restored. The source-generated new logs necessarily carry the candidate dataset hash, not the historic one.

## Interpretation of results

Passing the source-replay lane establishes the original test logic works with freshly emitted source-backed logs. It does NOT substitute for tests using the exact captured JSON bytes or prove 57,844 original characters were faithfully transcribed. The explicitly deferred original historical tests in the regular integrated suite remain deferred, preserving honest fidelity accounting. The separate lane gives additional executable coverage while historical files are missing.

Tests not yet covered include exact original JSON byte-level comparison, all original triage/expense configs (2 deferred parameters), and any original provider/cloud integrations or full historical release acceptance. No capture-content log is ever committed to the public repository.

Merge only after all PR-head CI jobs pass, then verify review-branch integrity on Windows/Linux. 
