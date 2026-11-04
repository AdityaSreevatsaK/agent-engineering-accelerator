# AEA reconstruction checkpoint: Part 12 (4 November 2026)

Status: provisional source drafts only. Do not merge to master.

| Source test file | Before | After | Displayed original lines |
| --- | ---: | ---: | ---: |
| tests/unit/test_judge_pairwise.py | 365 | 509 | 724 |
| tests/unit/test_cli.py | 241 | 364 | 1,133 |

**267 additional physical source lines** recovered from the original videos.

## GitHub source snapshots

- `reconstruction_drafts/test_judge_pairwise_PARTIAL_lines_1_509.py`, commit `8f3b3e5`
- `reconstruction_drafts/test_cli_PARTIAL_lines_1_364.py`, commit `3586483`

Both commits were read back from GitHub and their text matched the newly saved sources. The previously checkpointed source prefixes remain byte-for-byte unchanged.

## Validation

- Both drafts pass AST parsing with Python 3.11 grammar compatibility (using `ast.parse(feature_version=(3,11))`) and Python 3.13 compilation. Python 3.11 itself is not installed in this execution runtime.
- Each partial contains 20 distinct top-level test functions and no duplicates.
- The embedded CLI doubles code also parsed successfully.
- Neither file was promoted into `tests/unit/`, as source fidelity and original native tests remain incomplete.
- Full Inspect AI pytest execution and Windows/Linux CI have **not** passed.

## Known blockers

- `src/agent_accelerator/judge.py` provisional draft exposes `_data_marker` while the original pairwise test imports `data_marker`; this contract mismatch still needs evidence-based reconciliation.
- Original calculator example and two large calculator JSON fixtures remain absent; do not fabricate or commit placeholders as originals.
- Line-number matching and syntax validity do not demonstrate byte-for-byte transcription accuracy.

## Next work

Continue `test_judge_pairwise.py` from original line 510 and `test_cli.py` from original line 365. The two original recordings are already available. Keep the reconstruction checkpoint separate from master.
