# AEA historical-path inventory: automated checkpoint (Part 51)

**Date:** 7 November 2026  
**Target branch:** reconstruction/wip-checkpoint-2026-10-30. **Master is unchanged.**

## Evidence and method

The 117 historical file paths were extracted directly from the inventory
recorded from seven user-supplied folder screenshots on 25 October 2026,
preserved in the conversation as AEA_reconstruction_manifest_2026-10-28.md.
The exact recorded paths, including long timestamped baseline names, are
preserved in reconstruction_manifest/original_paths.txt.

The standard-library-only offline audit uses tracked Git paths and intersects
them with those 117 historical paths. Files under reconstruction_drafts/,
new verification tools, supplementary tests, and newly written CI workflows
are excluded unless their path exactly matches an original. This measures
presence, not content, source-byte fidelity, or readiness.

**Confirmed on live reconstruction integration branch, 7 Nov 2026: 61 of 117
historical paths present; 56 missing.**

| Historical group | Expected | Present | Missing |
| --- | ---: | ---: | ---: |
| CI | 1 | 0 | 1 |
| Baselines | 14 | 0 | 14 |
| Documentation | 2 | 0 | 2 |
| Examples | 31 | 11 | 20 |
| Scripts | 1 | 0 | 1 |
| Source | 23 | 23 | 0 |
| Tests | 39 | 23 | 16 |
| Root | 6 | 4 | 2 |
| **Total** | **117** | **61** | **56** |

## Local commands

    python -m reconstruction_tools.audit_original_paths --show-missing
    python -m reconstruction_tools.audit_original_paths --json
    python -m unittest reconstruction_tools.test_original_path_inventory -v

The four-platform CI job covers Windows/Ubuntu and Python 3.11/3.12. Its
lower-bound regression gate is 61 present historical paths. The gate is not
an exact-byte certification and does not require new missing files to run.

## Unavailable original calculator fixture bytes

The user confirmed original file uploads are not possible for
tests/fixtures/calculator_capture_content.json and
tests/fixtures/calculator_broken_redacted.json. Do not request these exact
files again. Existing video/screenshot evidence may support provisional
recovery of selected facts, and synthetic/derivative fixtures may be used
ONLY as explicitly labelled functional test substitutes at non-original
paths. They may not certify historical bytes or satisfy historical
original-fixture replay requirements.

## Follow-up boundaries

The existing triage/expense golden.jsonl screenshots should be reviewed
without requesting duplicates. The original expense scorers.py source
remains pending. Neither is fabricated in this change.

No historical original file is claimed as recovered by this PR. Original
source fidelity and release-readiness remain unverified, and baseline
captures may contain confidential or personal data, so do not copy raw
traces into the repository without review.
