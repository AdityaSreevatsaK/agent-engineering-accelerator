# AEA reconstruction: remove historical test import suppression (Part 53)

**Date:** 7 November 2026  
**Scope:** Reuse original expense scorer restored in Part 52; `master` remains untouched.

Before restoring `examples/expense/scorers.py`, the 24 selected original expense unit-test bodies could only run when one original scorer import line was suppressed in a temporary replay copy. That was a clearly documented temporary limitation.

With the video-derived scorer now present at its original path and its separate 30-case native scorer verification passing across Windows/Linux and Python 3.11/3.12, the suppression is obsolete.

## Implementation

- `reconstruction_tools/replay_original_video_test_candidates.py` stages BOTH original video-derived test source drafts **without changing even the import line**.
- The runner asserts the original scorer import is still present once and the recovered module exists. This fails closed if source evidence drifts.
- The original 14 triage and 24 expense test function selections, parameterisations, and historical video drafts are unchanged.
- The workflow wording now reflects actual recovered dependencies and scopes its deferred tests only to still-absent golden references or separately reviewed slow cases.
- Original test/source disagreement about the one `referral_approves_something` phrase remains documented in Part 52; this selected policy suite does not silently modify that disagreement.

## Validation

The existing four-platform original video-test replay workflow and other PR-head checks must be green before integrating. This is a **fidelity-preserving replay correction**, not an additional historically recovered file: original-path presence remains **62/117**. No paid model calls, historical fixture fabrication or changes to master.
