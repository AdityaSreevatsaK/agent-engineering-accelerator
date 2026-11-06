# Part 39: Screenshot-derived calculator broken/redacted log

**Date:** 6 November 2026
**Status:** provisional reconstruction under review, not source-byte-certified
**Source:** Three Notepad++ screenshots of the minified `calculator_broken_redacted.min.json`, supplied by the user; each successive image shares approximately two wrapped display lines with the preceding one.

## File recovered

`reconstruction_drafts/calculator_broken_redacted_SCREENSHOT_CANDIDATE.json` is a machine-parseable, single-line JSON candidate covering the visible run identity and metadata, dataset hash, result summary, 10 redacted samples, and scorer reductions. It is intentionally stored in `reconstruction_drafts/`, **not** `tests/fixtures/`. The direct user screenshots support the material facts below but are not a guarantee of all byte-level original fields.

- Schema version `2`, Inspect evaluation `status: success`, dataset `samples: 10`, `capture_content: false`.
- Original recovered calculator dataset hash is asserted against the `dataset_sha256` displayed in the broken log.
- Summary `results.scores[0].metrics.accuracy.value == 0.8`, 10 completed samples.
- Two failing cases: `subtract` (exact tool match missing) and `subtract_large` (subset tool match missing), with `C` for the other eight cases.
- Original screenshots show redacted case input/target, cleared output completion and empty message arrays.
- Sample order in the log differs from the original dataset's source order. Preserve the screenshot log sample order; summary reductions show dataset order.
- User specified two wrapped display lines overlap between successive screenshots. Deduplicate overlap by text continuity and never count it as a second JSON fragment.

## Verification

`reconstruction_tools/verify_broken_redacted_screenshot.py` checks the candidate without dependencies or cloud credentials: correct parse, ten unique cases, source hash match, redaction fields, accuracy, score values, failure explanations, source order and reductions.

`tests/unit/test_calculator_broken_redacted_screenshot.py` additionally loads the candidate through Inspect AI and the real recovered AEA comparison engine. This is **new evidence-backed regression coverage**, not a reconstructed historical original test file. The tests are included in the integrated offline regression gate, and the static verifier is run within the four-platform critical-static gate.

## Fidelity boundaries

- The screenshot is of a minified file, not a direct upload of the bytes. This candidate is a **verified semantic reconstruction**, not an original `calculator_broken_redacted.json` file.
- Do not overwrite or create `tests/fixtures/calculator_broken_redacted.json` with the provisional candidate.
- Do not remove the manifest deferrals for tests requiring original logs, even when the candidate happens to satisfy a subset of expectations.
- The original `calculator_capture_content.json` remains unavailable, as do `examples/calculator/rules.py` and original triage/expense configurations.
- Synthetic CI captures remain explicitly synthetic. There is no cloud-model execution.

## Requested next original files

1. `examples/calculator/rules.py`, ideally source file or complete scrolling video.
2. `tests/fixtures/calculator_capture_content.json`, preferably original bytes rather than screenshots because Inspect logs are long JSON lines.
3. Original broken/redacted fixture bytes if available in the future, solely for a final byte-level source-fidelity comparison.
4. Original `examples/triage/aea.toml` and `examples/expense/aea.toml` to release two config-case deferrals.

No changes are permitted into `master` before the complete historical reconstruction and review.
