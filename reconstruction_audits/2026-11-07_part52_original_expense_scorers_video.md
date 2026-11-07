# AEA expense scorer source: original recorded video recovery (Part 52)

**Date:** 7 November 2026  
**Recording:** `example-expense-scorer.py - video.webm`, previously uploaded by the user.  
**Original file:** `examples/expense/scorers.py`  
**Target:** `reconstruction/wip-checkpoint-2026-10-30`, not `master`.

## Full video evidence

The recording contains the original Notepad++ editor view from source line 1 through final displayed line 87, with overlapping scrolling frames. Its status bar explicitly shows **length: 4,136; lines: 87; Windows (CR LF); UTF-8**.

The recovered 86 LF-terminated physical code lines, plus the final blank editor line, have:

- **4,050 LF characters**
- **4,136 equivalent Windows CRLF editor characters**
- SHA-256 (normalised LF): `8165bd6785469ed057a44994d0cf16710bc9df58d1dd0982036520e0fc985e71`
- Python 3.11+ valid syntax and the four video-visible top-level functions `_to_usd`, `_same`, `ungrounded`, `amounts_grounded`.

The source is restored directly at its historical path. Matching editor counts and syntactic checks are strong **candidate** evidence, **not proof of byte-for-byte original identity**.

## Original test-video contradiction

The previously recovered `reconstruction_drafts/test_expense_FULL_VIDEO_CANDIDATE.py` has this parametrised assertion:

- ID `referral_approves_something`, expected explanation `"a referral approves something"`.

But the **newly inspected original scorer recording explicitly shows**:

- Source line 41: `return "a referral approves nothing"`.

The reconstructed scorer preserves what the original source recording shows. Neither original text was silently changed to force agreement. The replay selects all other original scorer assertions (30 parameter-expanded cases across dataset grounding, grounding errors, boolean rejection, and native Inspect AI scorer behaviour) and explicitly excludes **only** this known-conflicting case. That case remains unresolved as a cross-source fidelity conflict. A separate investigation or original file bytes would be needed to certify the historical expectation.

## Offline verification

New checks:

- `python -m reconstruction_tools.verify_expense_scorers_video`
- `python -m reconstruction_tools.replay_original_expense_scorers`
- Four GitHub-hosted Windows/Ubuntu × Python 3.11/3.12 CI jobs with real `inspect-ai` and `langgraph` packages. No AWS credentials, paid model calls or synthetic golden fixtures.

The scorer's numerical audit checks actual claim line conversions, claimed totals, adjustments, approved totals, unsupported currencies, booleans, and referral returns, without duplicating the underlying policy engine.

## Scope and accounting

Restores **one** original historical path, increasing original-path presence from **61/117 to 62/117** once the PR merges. Does not repair unrelated unrecovered golden references, calculator fixture bytes, baseline traces, or original test source fidelity. `master` remains unchanged.

No additional original recordings need to be re-requested for this specific file.
