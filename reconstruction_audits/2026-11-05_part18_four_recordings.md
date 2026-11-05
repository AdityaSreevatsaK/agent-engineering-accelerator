# AEA reconstruction checkpoint | 5 November 2026 | Part 18

**Status:** Four newly supplied, original 1920x1080 WebM recordings processed. Full provisional transcriptions are committed to the review branch. No merge to `master`; original full-suite fixtures and native Inspect AI runtime checks remain incomplete.

## Newly recovered files

| Original test | GitHub provisional draft | Physical source lines | Original editor lines | Original editor characters | Draft comparable characters | Static tests |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `test_build_task.py` | `reconstruction_drafts/test_build_task_FULL_DRAFT.py` | 166 | 166 | 7,389 (Windows CRLF) | 7,394 | 8 |
| `test_run_task.py` | `reconstruction_drafts/test_run_task_FULL_DRAFT.py` | 137 | 138 | 4,476 (Unix LF) | 4,476 | 8 |
| `test_scrub.py` | `reconstruction_drafts/test_scrub_FULL_DRAFT.py` | 377 | 378 | 13,764 (Windows CRLF) | 13,764 | 20 |
| `test_cli_pairwise.py` | `reconstruction_drafts/test_cli_pairwise_FULL_DRAFT.py` | 200 | 201 | 8,620 (Windows CRLF) | 8,620 | 6 |
| **Newly recovered** | **4 drafts** | **880** | | | | **42** |

The editor's displayed line count can include its empty final line; physical Python source lines use `splitlines()`. These transcripts are reconstructed from overlapping recorded editor frames, not byte-identical extracts of the original files.

### Character-count caveat for test_build_task.py

The first three original editor lines were not visible in the uploaded recording (first stable frame starts at line 4). The `json` and `Path` imports were inferred from actual usage. The resulting draft is five characters longer than the Windows editor counter. The original final editor line also contains code rather than a visibly blank extra line, so there may be an EOF-newline discrepancy. **Do not artificially pad, delete or claim source-byte identity.** Further fidelity review is pending.

## Commit evidence

- `test_run_task_FULL_DRAFT.py`: `b6fe9e3bd5c1a318d68887ba35474aaa71b986c3` (the original trailing newline retained).
- `test_build_task_FULL_DRAFT.py`: `1be94ec2de247335403f4a0d312ee34507e6c738`.
- `test_cli_pairwise_FULL_DRAFT.py`: `53515b7c33a6233f20d303329e4c0cf8d1486567`.
- `test_scrub_FULL_DRAFT.py`: `35983ec262e31f928eab55c705f1c902415b5f60`.
- Updated static audit inventory for all four files: `935f5b8bfa26cb71c51d5338c190ad254bc3c497`.

All four draft files were fetched back from the review branch; their line counts, lengths and presence were checked.

## Validation actually performed

- All four individual drafts parse under the **Python 3.11 grammar**, with 42 distinct top-level `test_*` function names; no duplicate top-level names.
- Added all four to the existing six-draft reconstruction audit inventory. **Ten drafts** pass local Python 3.11 AST checks and saved-prefix integrity: **6,480 physical transcribed lines, 343 top-level tests** (not parameter-expanded pytest cases).
- The five standard-library audit regression tests passed locally.
- No native Inspect AI or other framework-dependent pytest was run. The working container has no `inspect_ai`, `langgraph`, `strands` modules, and original calculator examples/fixtures are absent at the expected paths.
- GitHub's available status and PR workflow lookup had not returned positive CI results on the latest audit commit at check time. The Windows/Linux matrix cannot be claimed green.

## Missing test prerequisites

- `examples/calculator/agent.py` and `examples/calculator/dataset.jsonl` are absent; these block `test_build_task.py` and `test_run_task.py`.
- `tests/fixtures/calculator_capture_content.json` is absent; it blocks `test_run_task.py` and `test_scrub.py`.
- `test_cli_pairwise.py` uses an in-process fake agent, but still requires the real Inspect AI runtime and working AEA CLI, baseline capture and judge-double integration.
- No cloud credentials or paid model APIs were used to reconstruct or statically verify the files.

## Next priorities

1. Recover the original calculator dataset, agent and captured JSON fixture. If a replacement fixture is generated, label it as a substitute and do not assert original fidelity.
2. Check `test_build_task.py` first-three-line inference and five-character discrepancy using an additional top-of-file frame or source copy.
3. Continue earlier unfinished `test_judge_pairwise.py` at original editor line 510 and `test_cli.py` at line 365 when those recordings' raw bytes are accessible.
4. Run offline native pytest with the correct Python, Inspect AI and optional agent frameworks; resolve any failures with evidence and explicitly verify CI before promoting tests.
5. Preserve the draft branch and keep `master` unchanged pending integration and fidelity sign-off.
