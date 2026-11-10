# Post-PR #84 AEA reconstruction: source evidence and release boundary

**Date:** 10 November 2026  
**Baseline:** merged PR #84, Git commit `227009ad456c2a3e23d53a6b26b4ddb499e35e58`  
**Scope:** the reconstruction integration branch only; historical source authenticity must not be conflated with functional tests.

## Completed and independently observed

- GitHub Actions: **16 of 16 PR #84 workflows successful** at head `f084d08d60db33b0a95615293c49de4f16af5daa`. The Windows/Linux and Python 3.11/3.12 offline suites passed. The integrated branch has the subsequent merged commit above.
- Original video-derived tests are present at their historical paths. All four video-editor line totals now match after direct recording review.
- Historical source candidate blob hashes and preliminary draft evidence remain protected by a regression guard. The expense source uses real CRLF in Git while the other three use LF.
- The original `uv.lock` is **not needed** for the new, explicitly nonhistorical cross-platform dependency workflow; a regenerated lock is **not** a reconstruction of the historic file.
- A dedicated count audit intentionally reports differences without passing them off as byte identity. This PR separately reports actual checked-out newline bytes because Git working trees can translate them.

## Residual source discrepancies

| Historical file | Original recorded lines | Active displayed lines | Original characters | Candidate editor-equivalent characters | Original minus candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tests/unit/test_triage.py` | 444 | 444 | 19,847 LF | 19,839 LF | +8 |
| `tests/unit/test_expense.py` | 656 | 656 | 29,737 CRLF | 29,739 CRLF | −2 |
| `tests/unit/test_helpdesk.py` | 454 | 454 | 20,015 LF | 19,960 LF | +55 |
| `tests/unit/test_policy_rag.py` | 416 | 416 | 18,377 LF | 18,310 LF | +67 |

These totals are **signals, not proof of identical text**; offsetting substitutions could leave counts unchanged. The underlying user recordings remain the source of truth. No arbitrary whitespace or rewritten historical assertions should be added to close numerical differences.

The original `examples/expense/scorers.py` string `a referral approves nothing` contradicts one recorded expense test's expected `a referral approves something`. This is historical evidence, **not** a justification for silently altering either side.

## Documentation fidelity

`reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md` and `reconstruction_drafts/docs_review_video_PROVISIONAL.md` contain useful **semantic** video-derived reconstruction, including historical D1–D22 acceptance status, outstanding scope, data-retention table, trusted-code boundaries and residual risks.

They are **not byte-identical originals**, and the historical paths `docs/acceptance.md` and `docs/review.md` are intentionally not populated with invented text. The exact unit-test coverage matrix, full table wording, precise original formatting and some sections remain unverified against readable full videos. These documents should continue to be linked explicitly as provisional.

## Missing historical artefacts and release requirements

The latest recorded historical inventory was **97 of 117 paths**. The twenty missing are:

- 14 original baseline artefacts;
- 2 historical calculator capture fixtures, confirmed unavailable;
- 2 original acceptance/security Markdown documents;
- 1 historical CI workflow at its original path;
- 1 original root lockfile (`uv.lock`).

Passing synthetic-fixture CI does not reconstruct those files. Do not manufacture originals or count any modern replacement as a historic recovery.

Production acceptance is **not granted** by source counts or 16/16 offline CI. A release to `master` still needs an explicit policy decision on missing originals, real integration/security and data-retention review, authenticated baseline policy, contemporary dependency pinning and a formal owner sign-off. Evidence of adoption by multiple delivery teams is separate from code readiness.

## Recommended next verification passes

1. Compare the four remaining character differences **against original frames** and record only literal, legible replacements with original line/timestamp anchors. If exact bytes remain unprovable, keep the candidate designation.
2. When readable recordings can be accessed, finish the two provisional documents' missing tables/sections; otherwise stop at documented semantic fidelity rather than fabricating exact originals.
3. Continue the existing release-evidence and acceptance/security audits and collect approval for an explicitly *reconstructed* modern release. Do not modify the historical `master` merely to close the reconstruction work.

This report describes current verified results, not a claim of 100% historical source recovery.
