# AEA reconstruction checkpoint: synthetic Inspect capture, run_task and scrub (5 November 2026, Part 24)

**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Review branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Scope:** Native execution of two video-recovered suites against temporary synthetic fixture data.  
**Important:** This is **not** a recovery of the original fixture or a certification of source-video byte fidelity.

## Recovered tests verified

The user-recorded files (retained as the original provisional transcriptions in `reconstruction_drafts`) have now been staged in the review branch:

- `tests/unit/test_run_task.py` from `reconstruction_drafts/test_run_task_FULL_DRAFT.py`.
- `tests/unit/test_scrub.py` from `reconstruction_drafts/test_scrub_FULL_DRAFT.py`.

The `test_build_task.py` suite was previously verified using explicitly synthetic calculator inputs.

### Temporary synthetic capture generator

`reconstruction_tools/make_synthetic_capture.py` creates a native Inspect AI evaluation from **ten synthetic cases**, with a deterministic in-process solver, `case_checks` scores and scorer reductions. It generates `tests/fixtures/calculator_capture_content.json` **at CI runtime only**, with no user/client source data or paid model calls.

The generator refuses to overwrite an existing fixture. The generated log is **never** committed as the original AEA capture fixture. The existing `make_synthetic_calculator.py` similarly generates a temporary calculator agent/dataset stub.

This synthetic data exercises AEA's actual code, including `run_task`, `scrub`, Inspect log encoding, memory-backed log cleanup, case-scoring metadata and output/argument redaction. It does **not** validate the specific content or byte fidelity of the missing original captured log.

## GitHub-hosted native CI evidence

**PR:** https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/9  
**Merge destination:** reconstruction branch (NOT `master`)  
**Squash merge:** `431c447fee0ed136c9900404ad333731f2ff7be5`

### Synthetic calculator build/run/scrub workflow

GitHub Actions run `42034963558`, four jobs independently verified successful. Actual pytest log conclusions:

| Runner | Result |
| --- | --- |
| Ubuntu, Python 3.11 | **46 passed** |
| Ubuntu, Python 3.12 | **46 passed** |
| Windows, Python 3.11 | **46 passed** |
| Windows, Python 3.12 | **46 passed** |

The 46 parameter-expanded cases include **build_task, run_task and scrub** tests.

### Existing judge/report/CLI regression workflow

GitHub Actions run `42034963723`, four jobs independently verified successful. Actual pytest logs:

| Runner | Result |
| --- | --- |
| Ubuntu, Python 3.11 | **55 passed, 28 warnings** |
| Ubuntu, Python 3.12 | **55 passed, 28 warnings** |
| Windows, Python 3.11 | **55 passed, 28 warnings** |
| Windows, Python 3.12 | **55 passed, 28 warnings** |

Warnings are dependency deprecation warnings; no test failures were reported.

**Total verified in each environment across both workflows: 101 native pytest cases**. This is not the total AEA suite. It does not include all archived or partial test drafts.

## Fidelity and completion limitations

- `examples/calculator/agent.py` and `examples/calculator/dataset.jsonl`: **original content still unrecovered**, only CI-only synthetic substitutes used.
- `tests/fixtures/calculator_capture_content.json` and `tests/fixtures/calculator_broken_redacted.json`: **original fixture bytes unrecovered**. Do not commit generated substitutes as originals.
- `test_cli.py` remains partial from original editor line 365; `test_judge_pairwise.py` remains partial from editor line 510.
- The synthetic fixture generation and automatic checks are not a replacement for side-by-side video/source fidelity review.
- The entire reconstruction branch is **not** ready for merging into `master`; source modules and remaining tests need broad integration validation.

## Next source material to record/upload

1. Original `examples/calculator/agent.py` and `examples/calculator/dataset.jsonl` (prefer raw files over video).
2. Original `tests/fixtures/calculator_capture_content.json`, then `calculator_broken_redacted.json` (review for sensitive payloads first).
3. Remainder of `tests/unit/test_cli.py` and `tests/unit/test_judge_pairwise.py` videos.
4. Other missing original examples, test suites and docs from the 117-path inventory.

Until those originals are available, continue independent offline verification of source/tests without representing any synthetic stand-in as recovered historical content.
