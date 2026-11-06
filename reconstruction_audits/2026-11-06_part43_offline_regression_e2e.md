# AEA Reconstruction Part 43: Offline regression-detection end-to-end contract

**Date:** 6 November 2026  
**Target:** `reconstruction/wip-checkpoint-2026-10-30`; `master` must remain untouched.  
**Change classification:** New verification coverage, not restored byte-for-byte historical source.

## Why this test matters

Previous end-to-end CI proved the recovered CLI can initialise a starter project, run five deterministic cases, freeze a redacted baseline, repeat a successful check, compare and render/export reports. It did **not** prove that the user-facing CLI returns a nonzero regression exit code, correctly identifies a newly failing case, or honours explicitly relaxed quality thresholds.

Those are core AEA behaviours used by client teams in regression gates.

## New offline check

After verifying the existing 5/5 positive controls in a disposable temporary folder:

1. SHA-256 fingerprint all saved baseline files.
2. Change only the **local offline starter's deterministic London office hours mapping** from `09:00-17:30` to `08:00-17:30`. Do **not** change the five-case dataset or contact a provider.
3. Invoke `aea check` with the same saved baseline and assert **exit code 1**, `passed=4/5` and `REGRESSION`.
4. Verify the generated `comparison.md` identifies `exact_answer` as newly failing and reports `1 case(s) newly failing`.
5. Run standalone `aea compare` against the regressed run and assert **exit code 1**, a persisted Markdown report and a matching printed verdict.
6. Relax the two relevant thresholds (`--max-new-failures 1` and `--max-pass-rate-drop 0.2`) and assert the same comparison returns **exit code 0** with `OK` while still documenting the failing case.
7. Compare the frozen baseline file hashes and ensure no accidental edits occurred.

The environment disables AWS instance metadata and clears AWS access/token variables. All agent execution uses the existing deterministic Strands `OfflineModel` and remains purely local.

## Trust and historical fidelity limits

This is a **synthetic verification scenario** using the reconstructed offline starter. It does not replace or simulate the original historical calculator capture JSON. It changes only the disposable starter copy, never a source file in GitHub. The true original calculator rules and saved logs remain unavailable, and the existing 60 fixture/config-dependent historic tests remain deferred. No original recorded tests are modified.

The test runs as part of the existing four-platform `reconstruction-offline-template-e2e.yml` workflow. A successful matrix validates the two exit-code paths, baseline persistence and threshold semantics on Windows and Ubuntu with Python 3.11 and 3.12.

**Acceptance:** merge only after all ten PR-head workflows and 37 jobs succeed, followed by the eight post-merge reconstruction integrity checks.
