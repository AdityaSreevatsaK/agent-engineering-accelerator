# AEA historical-video recovery: six new recordings — 10 November 2026

**Branch:** reconstruction/wip-checkpoint-2026-10-30
**Status:** Partial source fidelity, runnable video-derived candidates, not historical byte-certified release.
**Original-path recovery:** 97/117 unchanged; not the same as source content certification.

## Evidence supplied

The user supplied six additional original-source scrolling recordings. Their raw media are intentionally **not checked into Git**, and any generated screenshot stills remain private to the evidence review session. SHA256 hashes identify the particular source footage used here; they are not hashes of recovered source bytes.

| Original path | Video SHA256 |
| --- | --- |
| tests/unit/test_helpdesk.py | 9a05b158a4235685a8a23f5d25fafe03cd0f8dd35dde4c5621517b29cceb3d77 |
| tests/unit/test_policy_rag.py | 5c1d4b6d18c90a7e07759c3bbb3cba31472c0e44201ddcba3788d8fc734f31d2 |
| docs/acceptance.md | 190ec0d3db88358bdc133704231e203134658527a6fd5185fd4f6c982916842e |
| docs/review.md | 076a0d4abf69e2b51e73a28ee4214491700e03a0333c3e3f3ae0b08b07d03e6b |
| tests/unit/test_triage.py | 48ea1e0940146b10562f21a5021ae88c8c06c8de840c07608f98c920d0352121 |
| tests/unit/test_expense.py | f0cf8fed4efaaa80c8dcdfd4710f3c905506377fafbee73662bc018d73e9f7f3 |

## Source reconciliation from readable video frames

| Active reconstructed test | Before this batch | After this batch | Editor source reference | What was recovered |
| --- | --- | --- | --- | --- |
| test_helpdesk.py | 413 lines, 16,799 LF characters | **450 lines, 19,940 LF characters** | **454 lines, 20,015 LF characters** | Multiline TaskState fixture, explicit approval gate and tool-call mutation witnesses, original golden-case membership assertions and structured JSON tool-payload assertion |
| test_policy_rag.py | 367 lines, 14,525 LF characters | **402 lines, 18,195 LF characters** | **416 lines, 18,377 LF characters** | Search ranking, grader, rewrite, decision, parser, model, graph routing, live-model and golden-reference mutation witness notes |
| test_triage.py | 439 displayed lines, 19,400 LF characters | **unchanged** | **444 lines, 19,847 LF characters** | Recording rechecked; extant candidate retains its 16 tests and unresolved 5-line/447-character gap |
| test_expense.py | 654 displayed lines, 29,000 LF characters | **unchanged** | **656 lines, 29,737 Windows CRLF-equivalent characters** | Recording rechecked; extant candidate retains its 31 tests and unresolved 2-line/84-CRLF-character gap |

The two changed test candidates contain their original set of **19 helpdesk** and **25 policy RAG** top-level tests. In the helpdesk test, source-visible assertions about golden dataset membership and structured tool messages were restored. Exact text of all additional comments remains **unverified** until every recorded line has been compared side by side, so neither matching dimensions nor green pytest would certify historical identity.

The updated pinned Git blobs, dimensions and retained gaps are checked by reconstruction_tools/verify_active_video_test_provenance.py and its negative tests. Unreviewed later changes fail closed.

## Documentation recovery

- **docs/acceptance.md:** the newly supplied video shows the original section 6 test-coverage table in full (18 module rows). Its module names, "Met" statuses, evidence paths, example set and test-run command guidance are now included in the existing reconstruction_drafts/docs_acceptance_video_PROVISIONAL.md. The *current* acceptance D11 source audit remains partly verified: a config path and accelerator version do not constitute config SHA256, source Git revision or dependency inventory.
- **docs/review.md:** the new recording clarifies section 6 residual risks (short-lived scorer hashes, output digest comparison, names leaking identifiers, prices, --force overwrite, and file:// headless-browser export boundary). These details are recovered in reconstruction_drafts/docs_review_video_PROVISIONAL.md. Historic statements about fsspec-based dataset hashing or price handling must not automatically be treated as current implementation properties.
- Both original docs/ paths remain **missing**. Video-derived drafts intentionally contain provenance warnings and contemporary notes, so copying them into historical paths would falsely certify them as the recorded originals.

## Outstanding work and user input

The current branch can validate many original behaviours offline without any additional recording. The remaining gaps are **specific line/character-level source fidelity**, two provisional historical documents, missing original uv.lock and 14 historical baseline files, original CI activation and two unavailable calculator captured fixtures. The original fixture absence is already confirmed by the user; do not request them again.

Continue native CI on Windows and Ubuntu with Python 3.11/3.12, preserve all historical assertions, avoid provider charges, do not write synthetic baseline logs into original paths, and keep master unchanged.

**Release conclusion:** Verified functional progress and closer source candidates, but **not** a complete 117/117 reconstruction and **not** an approved production release.
