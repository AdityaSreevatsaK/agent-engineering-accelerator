# AEA reconstruction checkpoint: public Actions recovery and verified CLI contract

**Date:** 6 November 2026  
**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Current integration branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Release decision:** reconstruction is progressing; historical v2.2.0 fidelity is NOT yet certified and `master` is NOT to receive the entire reconstruction.

## GitHub Actions recovered

The user made the AEA repository public. GitHub repository metadata was independently checked and reported `visibility: public`. Previously failed hosted Actions jobs had returned `steps: null` and no downloadable job logs, indicating no check steps executed. Re-running failed jobs on the public repository restored actual runner execution.

The final head of [PR #23](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/23), `96cc29cbde6d28805bd3983606ba0e935a81467c`, had **10 completed successful workflows and all 37/37 jobs green** after rerun. Each of the four integrated offline unit jobs reported **1,183 passed, 60 deselected, 69 warnings**. The source audit compiled and verified the 724-line and 1,133-line video-derived candidates and both exact previous partial prefixes. PR #23 was merged into this review branch using squash commit `db89457d8da6d5b2911e5868f98dc48c691d8caa`.

## Original CLI behaviour correction

The recovered historical `test_cli.py` lines 1019-1042 require invalid/unreadable TOML config to result in **`main(argv) == 2`**, a filename-bearing `error:` message, no created run directory, and evaluation not started. The reconstructed `_apply_config` previously used `parser.error` for `ConfigError`, which raised `SystemExit(2)` rather than returning 2.

[PR #24](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/24) corrected that behavioural mismatch without changing the preserved historical video candidate:
- `_apply_config` now lets `ConfigError` propagate.
- `cli.main` catches that error **before a run starts**, prints `error: <file>: <reason>` and returns `EXIT_ERROR == 2`.
- Existing argparse usage exceptions for missing required agent and invalid flags remain unchanged.
- Supplementary offline tests now check the historical return-code semantics and config-error precedence over both unsafe and nonexistent check baselines.

The PR #24 final head, `f01dafbac04401f8309c4493adf09a0d2b0ee876`, completed **10 successful workflows, 37/37 jobs green**, verified on Windows and Ubuntu with Python 3.11/3.12. All four integrated suite logs reported **1,185 passed, 60 deselected, 69 warnings** (per OS/Python configuration, not 4,740 unique tests). Full configured Ruff and Pyright checks for production sources, adapter tests, wheel/CLI smoke and offline E2E smoke also passed.

PR #24 was merged into this review branch using squash commit `6a520cd8b378955f5fb16666a859a75e708ad88e`.

## Preserved original evidence and remaining deferrals

Full provisional video-derived files:
- `reconstruction_drafts/test_judge_pairwise_FULL_VIDEO_CANDIDATE.py`: 724 physical lines.
- `reconstruction_drafts/test_cli_FULL_VIDEO_CANDIDATE.py`: 1,133 physical lines.

Both start with the exact previous draft prefixes (509 and 364 lines). They remain **provisional reconstructions**, not certified byte-for-byte originals. The active recovered pairwise test file uses a documented runtime-only compatibility adaptation; supplementary recovered CLI controls test a safe, fixture-independent subset rather than pretending to run the complete original CLI suite.

Still missing original calculator agent/dataset, `calculator_capture_content.json`, `calculator_broken_redacted.json`, original triage/expense configs, other example/baseline assets, and final character-level review. **60 parameter-expanded original assertions remain explicitly deferred**: 58 because of original calculator captures and 2 because of absent triage/expense configs. Slow/subprocess tests excluded by standard `-m 'not slow'` are a separate coverage boundary. No production cloud integrations have been verified.

The source fidelity audit must not convert synthetic calculator fixtures into purported original files. No cloud models, paid provider calls, user credentials or secrets were required by these verification runs.

## Next acceptance gate

1. Wait for the user's original calculator source, dataset and capture/broken-log fixtures; restore and verify original contents.
2. Restore original triage/expense configuration files and rerun all 60 deferred test cases.
3. Explicitly assess slow/subprocess tests, dependency compatibility, video character-level discrepancies, missing historical assets and release security.
4. Only then consider a fully reviewed merge of the reconstructed application into `master`.

**This file is a newly created reconstruction checkpoint, not a recovered original AEA v2.2.0 document.**
