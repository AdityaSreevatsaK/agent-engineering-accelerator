# Four historical AEA unit-test recordings: evidence review

Date: 8 November 2026. This file was newly authored for reconstruction and was not part of AEA v2.2.0.

## User-supplied original source evidence

| Historical source path | Recording | Original Notepad++ status | Transcription status |
| --- | --- | --- | --- |
| `tests/unit/test_expense.py` | `tests-unit-test_expense.py - video(1).webm` | 656 lines; 29,737 characters; CRLF; UTF-8 | Provisional 653-line historical-path candidate, 29,653 CRLF-equivalent characters; 3 lines/84 characters short |
| `tests/unit/test_triage.py` | `tests-unit-test_triage.py - video(1).webm` | 444 lines; 19,847 characters; CRLF; UTF-8 | Provisional 438-line historical-path candidate, 19,838 CRLF-equivalent characters; 6 lines/9 characters short |
| `tests/unit/test_helpdesk.py` | `test-unit-test_helpdesk.py - video(1).webm` | 454 lines; 20,015 characters; LF; UTF-8 | Initial source fragment under `reconstruction_drafts/`; full file still missing |
| `tests/unit/test_policy_rag.py` | `test-unit-test_policy_rag.py - video(1).webm` | 416 lines; 18,377 characters; LF; UTF-8 | Initial source fragment under `reconstruction_drafts/`; full file still missing |

Video SHA-256 digests, for source evidence traceability:
- Expense: `f0cf8fed4efaaa80c8dcdfd4710f3c905506377fafbee73662bc018d73e9f7f3`.
- Triage: `48ea1e0940146b10562f21a5021ae88c8c06c8de840c07608f98c920d0352121`.
- Helpdesk: `1baa9d1f65a01b56519fb41258b58ccf9ed0751dc9c564d820ae66bd2cc94c83`.
- Policy RAG: `5c1d4b6d18c90a7e07759c3bbb3cba31472c0e44201ddcba3788d8fc734f31d2`.

## Original-source disagreement, not a regression to be patched out

The recorded source for `examples/expense/scorers.py` has `return "a referral approves nothing"`, while the recorded `test_expense.py` contains a parameterised test ID `referral_approves_something` that expects `"a referral approves something"`. The discrepancy was already established in the previous scorer-video audit `2026-11-07_part52_original_expense_scorers_video.md`; the new integrated CI triggered this single mismatch: **2,388 passed, 121 deselected, 1 failed** on the first branch head.

Neither historical text should be silently edited just to satisfy the other. The integrated gate now contains a **fail-closed exclusion of precisely the conflicting parameterisation** only when both expected original strings remain present. A separate historical contradiction remains unresolved even if CI is green.

## Scope and fidelity

The two historical paths staged in this PR are **reconstruction candidates**, not original-file byte identities. The initial helpdesk and policy RAG drafts preserve video-visible source and helper contracts, not complete runnable tests, and must not count as historical files until full transcription is verified.

Four-platform native offline CI invokes selected original expense/triage functions directly from the active historical test paths. No paid providers, synthetic original fixture claims, or confidential baseline captures are required.

This evidence permits historical-path presence accounting only; it does not establish production or original-release readiness. `master` remains unchanged.
