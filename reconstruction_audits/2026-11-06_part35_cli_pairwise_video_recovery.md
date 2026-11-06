# AEA reconstruction checkpoint, Part 35: recovered CLI and pairwise recordings

**Date:** 6 November 2026  
**Review PR:** [#23](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/23)  
**Branch:** `reconstruction/restore-original-pairwise-cli-2026-11-06`  
**Merge policy:** Do not merge into the reconstruction checkpoint until the complete PR-head CI matrix is green. Never promote this provisional reconstruction wholesale into `master`.

## Files received and recovered

The user reuploaded two original Notepad++ screen recordings, now available as actual WebM bytes. Earlier reconstruction continuations had only partial source and could not read the Library-backed videos.

| Original historical module | New complete video-derived candidate | Physical lines | Top-level test functions | Previously recovered prefix |
| --- | --- | ---: | ---: | --- |
| `tests/unit/test_judge_pairwise.py` | `reconstruction_drafts/test_judge_pairwise_FULL_VIDEO_CANDIDATE.py` | **724** | **32** | First **509** lines preserved exactly |
| `tests/unit/test_cli.py` | `reconstruction_drafts/test_cli_FULL_VIDEO_CANDIDATE.py` | **1,133** | **59** | First **364** lines preserved exactly |

Both candidate sources passed Python 3.11 AST parsing. The full candidates start with exactly the complete byte contents of the corresponding previous partial draft files, not merely matching line counts. No filler was inserted to match an editor's character counter. They are **provisional visual transcriptions**, not certified byte-for-byte original source files.

Local UTF-8 source SHA-256 checksums:
- Pairwise candidate: `0549a438954a5666d8599f53e78f0ac8a8101095ebcb8a74bda9e8778583c6c7`.
- CLI candidate: `3483b4c44b31224179df78a5778ee36fe45e305c9ebb6aa68bfed21d8038c58f`.

## Runtime-covered functionality

The previously activated pairwise judge prefix suite was extended to include the recorded suffix, preserving the *existing, explicitly documented* `_adapter_solver` runtime compatibility adaptation. The active filename still ends in `_recovered_prefix.py` for historical CI continuity; its content now covers the full recorded pairwise file.

A separate `tests/unit/test_cli_recovered_controls.py` module exercises **self-contained**, fixture-independent recorded CLI scenarios: option defaults, config precedence and validation, parser errors, agent-adapter choices, invalid UTF-8 config, early baseline validation, unsafe content retention and threshold defaults. This test module is **supplemental reconstructed behaviour coverage**, **not** the exact original `tests/unit/test_cli.py`, which is preserved in `reconstruction_drafts/`.

`reconstruction_tools/run_integrated_offline.py` now requires this additional CLI test module. The draft integrity auditor checks the complete 724/1,133-line candidates, Python AST and both exact prefix transitions. The critical-static CI workflow was updated to execute that audit.

## Verified GitHub Actions evidence

An earlier PR-head commit, `31b4b33c77d2d0c81233a75650971d5b5eed5173`, completed the integrated offline test workflow successfully on **all four platforms** (Windows and Ubuntu, Python 3.11 and 3.12). All four job logs explicitly reported:

**1,183 passed, 60 deselected, 69 warnings per platform.**

Previous reconstruction coverage was 1,120 passing tests before the newly restored pairwise and CLI coverage. The 1,183 active tests are not 4,732 independent tests; the same suite was repeated in four environments.

## Current GitHub Actions blocker

On the subsequent PR-head commit `f8fcfed4a359e4fda6ea73588d4f96757c727e1c`, multiple GitHub Actions workflows returned **failure before any job steps ran**. Failed jobs reported `steps: null`, and the job-log endpoints returned `BlobNotFound`. A separate failed-job rerun was accepted but failed the same way with zero executed steps. This is a **runner/Actions execution problem** based on observed evidence; there is **no successful new-head validation**, and the exact account/platform cause is not established. Do not label these as test assertion failures, but do not mark the CI matrix green either.

The new draft-audit CI step was configured, but it has **not** yet run successfully on the final PR head. Repository PR #23 intentionally remains **draft/unmerged** until CI execution becomes available and all checks complete.

## Remaining missing source artefacts

- The original calculator agent, JSONL dataset, capture and broken/redacted JSON fixtures, and historical baseline files. Synthetic fixtures used for other tests must not be presented as originals.
- Triage and expense example configurations; broader historical examples and scripts.
- The **60 explicitly deselected parameter-expanded tests**: 58 fixture-dependent comparison cases and two example-config cases.
- Slow/subprocess tests excluded by `-m 'not slow'`, original-provider integrations, complete 117-path inventory and final video character-level fidelity sign-off.

## Next steps

1. Restore GitHub Actions runner access or address the account-level/hosting blocker. Re-run all PR #23 checks against the latest head. Do **not** relax the quality gates to force merge.
2. If all jobs pass, merge PR #23 **only** into `reconstruction/wip-checkpoint-2026-10-30`, not `master`.
3. Obtain missing original calculator fixtures and example configurations, activate deferred tests and validate slow/subprocess scenarios.
4. Complete the original-source fidelity and security review before any eventual promotion of the full reconstructed project into `master`.

**Evidence boundary:** passing reconstructed-source tests demonstrates useful behaviour, not byte-level fidelity to the historical AEA repository.
