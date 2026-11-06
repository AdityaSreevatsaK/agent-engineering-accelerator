# AEA Reconstruction: filesystem safety hardening in `aea init`

**Date:** 6 November 2026  
**Classification:** New security hardening, **not** a transcription of historical v2.2.0 source.  
**Target:** `reconstruction/wip-checkpoint-2026-10-30`; leave `master` unchanged.

## Finding

The recovered original `src/agent_accelerator/cli.py` implements `aea init TARGET --force` by writing `TARGET/agent.py` followed by `TARGET/dataset.jsonl` with `Path.write_text`. If either path is a symlink to a file outside the target directory, `write_text` follows the link and truncates that external file. A linked target directory or linked parent directory can also redirect output outside the requested tree.

This is a genuine file-safety concern in a reusable developer tool. The original recovered tests cover normal `--force` overwrite but not linked paths. We must **not** describe this correction as faithful recovered source.

## Change

Before creating or writing anything, `_init` refuses:

- Target directory paths whose own path or any ancestor is a symbolic link.
- Existing target directories containing a symbolic link at either generated template filename, even if only the *second* filename is linked.

If a linked second template is present, both original template files are left untouched. Regular existing template files remain overwritable under the documented `--force` flag, while unrelated files in the directory are retained.

The original `tests/unit/test_init.py` is not altered. A separately named `tests/unit/test_init_symlink_safety.py` asserts this new safety contract using disposable temporary directories and external sentinel files; on Windows runners lacking permission to create symlinks, only the affected symlink test is skipped, rather than altering system settings.

The normal Windows/Linux Python 3.11/3.12 integrated suite must execute this test module. Any source modification to the reconstructed historical `cli.py` must remain explicitly recorded as a hardening deviation in the audit.

## Threat model and caveats

This guard addresses inadvertent overwrites through existing symbolic links, not adversarial races where another process swaps the filesystem entry after the preflight check. It does not claim race-free or atomic writes. Filesystem hard links are not covered by the symlink guard. Later production hardening could use atomic replacement and platform-specific no-follow flags, but that is separate from historical recovery.

Other original-file gaps remain: `examples/calculator/rules.py`, original Inspect capture JSON fixture(s), original triage and expense examples, and the 60 explicitly deferred tests. No original fixtures are fabricated here.

## Acceptance

Merge the reviewed change **only** when all ten PR-head GitHub Actions workflows pass: 37/37 matrix and diagnostic jobs, including the new integrated safety regressions. Run the post-merge eight-job reconstruction branch gate. Do not merge into `master` or announce complete original v2.2.0 fidelity.
