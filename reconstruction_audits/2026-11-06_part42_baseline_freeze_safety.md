# Part 42: Baseline freeze preflight safety hardening

**Date:** 6 November 2026  
**Classification:** New security/reliability hardening. This change is NOT a byte-for-byte transcription of historical AEA v2.2.0.  
**Target branch:** `reconstruction/wip-checkpoint-2026-10-30`. Never merge incomplete reconstruction into `master`.

## Finding

The historical `aea check --update-baseline` command deletes any existing baseline directory after a successful agent run, then copies the new run into its place. The old preflight regarded any directory with exactly one `*.json` file as an existing run without parsing its contents or checking for other data.

Consequently, a user could point `--baseline` at an unrelated folder containing a single arbitrary JSON document and additional private documents. That folder would pass preflight and could then be **recursively deleted** once the evaluation completed. Symbolic-link paths and linked artefacts also require fail-closed handling.

## Narrow mitigation

Before any run begins, `_validate_baseline_target` now:

1. Rejects a baseline path (including parents) that traverses any symlink.
2. Preserves the historical prohibition against putting `--runs-dir` inside the baseline.
3. Still permits a missing target or existing *empty* directory.
4. For a nonempty target, requires exactly one `*.json` run log and permits only the known generated companion files `report.md`, `comparison.md`, `traces.jsonl`.
5. Rejects any other file, nested directory or symlinked artefact before running an agent.
6. Uses native Inspect AI `read_eval_log` to confirm the JSON file is structurally a valid evaluation log, rather than assuming any `*.json` is safe to delete.

The existing normal baseline replacement behaviour is preserved for an ordinary old AEA run directory containing a valid Inspect log and generated companions. Unexpected user-added files are protected, although their presence now prevents automatic replacement until the user chooses a dedicated baseline directory.

## New offline tests

`tests/unit/test_baseline_replacement_safety.py` uses temporary directories and the existing **screenshot-derived** valid broken/redacted Inspect candidate as controlled input. It covers:

- Normal baseline with valid Inspect log and known companion files; new or empty baselines.
- A single arbitrary, empty or malformed JSON falsely resembling a log.
- A valid Inspect log accompanied by unrelated notes, an HTML export or nested folder.
- Symlinked log, baseline directory and parent directory.
- Existing recursive-runs and capture-content refusal semantics.

Only tests that require creating symlinks may skip on Windows runners without permission. No originals are invented or labelled as recovered. This new test file is required by the four-platform integrated test inventory.

## Residual risks and fidelity boundary

This protects against accidental replacement of unrelated directories; it does **not** make filesystem operations atomic. Concurrent edits or symlink swaps during the evaluation can still create a time-of-check/time-of-use race. Replacing an existing run remains a delete-and-copy operation rather than an atomic directory swap. More substantial transactional filesystem design should be a separately reviewed future improvement.

The 60 parameter-expanded original-fixture/config tests remain deferred. Missing original calculator rules and Inspect capture bytes remain historical recovery blockers.

Merge only with 37/37 green PR-head jobs and successful post-merge reconstruction checks. Do not describe this security patch as recovered historical source.
