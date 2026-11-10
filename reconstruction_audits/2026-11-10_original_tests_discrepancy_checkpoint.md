# AEA source fidelity checkpoint — 10 November 2026

## Correct branch and provenance

The active reconstructed historical tests live in `reconstruction/wip-checkpoint-2026-10-30`, **not** `master`. The following source SHA-1 blob identifiers were inspected directly through the GitHub contents API before this audit branch was created:

| Historical path | Blob SHA |
|---|---|
| `tests/unit/test_helpdesk.py` | `b29b47234cd8c9949d0f0ddd3edda60fe3f77e2f` |
| `tests/unit/test_policy_rag.py` | `95fae55413af53737e18cb5193c7701886b57786` |
| `tests/unit/test_triage.py` | `6928d1154705166b425ab3333491bb9e4e9ca2ea` |
| `tests/unit/test_expense.py` | `98912aeefbbaf5f7599fce9343c982268663e038` |

Earlier reports describing helpdesk as 413 lines and policy RAG as 367 lines are **superseded** by the integrated 450-line / 402-line source files. Those historical reports are retained for provenance, not used as current status.

## Count reconciliation against original video status bars

Recorded original source measurements from `reconstruction_audits/2026-11-08_four_original_example_test_videos.md` are compared with the live integration source, translating LF to CRLF-equivalent counts for the two Windows-editor recordings.

| File | Original displayed lines | Current displayed lines | Lines short | Original editor chars | Current editor-equivalent chars | Characters short |
|---|---:|---:|---:|---:|---:|---:|
| Helpdesk | 454 | 450 | 4 | 20,015 (LF) | 19,940 | 75 |
| Policy RAG | 416 | 402 | 14 | 18,377 (LF) | 18,195 | 182 |
| Triage | 444 | 439 | 5 | 19,847 (CRLF) | 19,838 | 9 |
| Expense | 656 | 654 | 2 | 29,737 (CRLF) | 29,653 | 84 |

**Caution:** A count mismatch is not itself evidence of where text is missing. Matching counts likewise cannot prove original-byte fidelity. In particular, the source's trailing empty line and Notepad++ displayed line conventions may affect apparent line differences. All four cases remain **open** pending screenshot/frame-specific textual verification, even when functional tests pass. Later duplicate recordings must be compared to the correct original version before treating different reported counts as interchangeable.

## Documentation status

`docs/acceptance.md` and `docs/review.md` are still **not restored** as historical originals. The available semantically reconstructed documentation drafts and November 9 audit should be reviewed against both original videos and never renamed to original paths with a claim of source identity. The full historical unit-test coverage matrix remains unverified. Retention/security bullets have been recovered semantically, not byte-certified.

## Source access in this session

All latest relevant recordings were located in the MathCo Project Library. However, direct materialisation of their raw video bytes into the analysis container was rejected as unavailable for each of five latest recordings. Therefore no frame-based content changes can be justified from these videos in this session; the code has **not** been padded or modified to match counts.

## Historical inconsistency requiring separate decision

The original `examples/expense/scorers.py` string `a referral approves nothing` conflicts with original `test_expense.py` parameterisation expecting `a referral approves something`. Do **not** rewrite either historical string under the guise of transcription or hide the contradiction. Keep any targeted CI handling labelled as a known historical incompatibility.

## Next evidence-based work

1. Recover readable frame evidence for exact missing/differing ranges in helpdesk and policy RAG, then triage/expense.
2. Transcribe only confirmed text differences; preserve source assertion intent and test case parameters.
3. Compare documentation coverage rows and security/retention sections against the recorded frames.
4. Run Python AST, native offline tests, Windows/Linux CI and compare results on the integration branch.
5. Only after those checks, consider promoting verified reconstruction commits; leave `master` untouched meanwhile.

Diagnostic helper: `python reconstruction_tools/audit_original_example_test_counts.py`. This reports counts and exits successfully even when gaps are found; it is **not** a release gate.
