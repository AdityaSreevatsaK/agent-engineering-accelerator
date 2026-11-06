# AEA reconstruction Part 40: capture-video evidence and false-slow regression coverage

**Date:** 6 November 2026  
**Scope:** Work possible without missing historical source-file bytes.  
**Integration target:** `reconstruction/wip-checkpoint-2026-10-30`. **Do not promote to `master` yet.**

## Newly available original Inspect capture recording

The user already uploaded `calculator_capture_content - video.webm`, a roughly 108-second scrolling recording of `calculator_capture_content.min.json` in Notepad++. It is not a directly uploaded JSON file.

Visually confirmed source facts from original video:
- Notepad++ identifies the file as **one minified JSON line**, **length 57,844 characters**, Windows line endings and UTF-8.
- Inspect log envelope begins `{"version":2,"status":"success",...}`.
- The run's `model` is `mockllm/model`; the agent reference is `examples.calculator.agent:build_agent` and the adapter is `strands`.
- `eval.metadata.capture_content` and top-level `metadata.capture_content` are **true**.
- Dataset is `examples/calculator/dataset.jsonl`, 10 samples, with the visible original `dataset_sha256` matching the source-recovered calculator dataset.
- The summary has **10 total/completed samples and case_checks accuracy 1.0** (all cases passing).
- The file includes concrete sample content, tool arguments, output completions, trace events and reductions. Its tail displays the reductions for all ten original dataset IDs with `value: 1.0`.
- The preceding broken/redacted screenshot candidate instead shows `capture_content:false`, an 0.8 accuracy, and two failures (`subtract` and `subtract_large`).

**Fidelity boundary:** The original JSON is about 57.8k characters of one-line text with detailed timestamps, trace IDs, scores and tool arguments. The recording is useful evidence but does not provide the byte-accurate original file; an attempted single text-recovery pass produced **no usable complete output**. It would be inaccurate to invent those trace IDs or substitute a synthetic Inspect log as a recovered original. We have therefore **not** created `tests/fixtures/calculator_capture_content.json` and have **not** re-enabled the original 58 capture-dependent parameterised assertions. The user can provide original JSON bytes later; inspect them for secrets/private data before committing.

## Additional source-backed offline verification recovered now

The historical `tests/conftest.py` marks cases using any fixture *name* from `{runs, price_runs, check_runs}` as `slow`, intending to isolate CLI subprocess runs. However the original `tests/unit/test_compare.py` contains `test_case_is_flaky_only_when_some_but_not_all_epochs_passed`, which directly parametrises an **integer named `runs`** across seven rows. It does not request the subprocess fixture and performs no external IO; pytest reports this parameter in its fixture-names list, leading to a false slow classification and silent omission under the standard `-m "not slow"` suite.

Instead of editing or overwriting the historical original conftest/tests, we added:
- `reconstruction_tools/verify_slow_parameter_collision.py`: AST fail-closed audit of the original seven direct numeric parameters and the source marking policy. Then it invokes exactly the corresponding original pytest node with `-m slow`, confirming **7 passed**.
- `tests/unit/test_slow_parameter_collision_audit.py`: self-test for the historical fixture collision audit, included in the normal integrated offline suite.
- An additional step in the four-platform `reconstruction-integrated-offline.yml` CI that executes the seven original cases independently from the existing `not slow` suite on Windows/Linux Python 3.11/3.12, without external model or original capture fixtures.

The original source remains intact; the seven-case lane is clearly labelled so users don't count them as subprocess integration tests. This restores meaningful coverage while maintaining transcription fidelity.

## Pending requirements

1. Original `examples/calculator/rules.py` for true offline calculator execution.
2. Original `tests/fixtures/calculator_capture_content.json` byte file to validate the capture log and reactivate its original tests. Screenshot/video only is inadequate for trace-level character accuracy.
3. Original `tests/fixtures/calculator_broken_redacted.json` byte file, when available, for replacement of provisional screenshot candidate after fidelity review.
4. Original triage and expense `agent.py` and `aea.toml` examples for two deferred configuration assertions.
5. Expanded real subprocess/slow tests and final historical source inventory/security sign-off before release.

**CI acceptance policy:** merge only after every matrix job passes on the PR head. Preserve the existing explicit 60 deferred parameter-expanded assertions and no paid model calls.
