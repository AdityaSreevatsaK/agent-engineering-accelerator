# AEA v2.2.0 reconstruction: full inventory presence audit
Date: 5 November 2026
Branch: `reconstruction/wip-checkpoint-2026-10-30`
Scope: file-presence verification only against the 117-path original screenshot inventory.
Status: PROVISIONAL; do not merge to `master`.

## Verified repository presence

Every inventory path below was checked against GitHub's contents API for this review branch. This is **presence**, not source-fidelity certification or test success.

| Inventory category | In original inventory | Present at original path | Absent | Notes |
| --- | ---: | ---: | ---: | --- |
| CI | 1 | 0 | 1 | Original workflow missing |
| Baselines | 14 | 0 | 14 | Preserve/review originals before commit, especially sensitive traces |
| Docs | 2 | 0 | 2 | Original acceptance and review docs missing |
| Examples | 31 | 0 | 31 | Calculator/expense/helpdesk/orders/policy_rag/triage examples absent |
| Scripts | 1 | 0 | 1 | Original `scripts/ci.sh` missing |
| Source | 23 | 23 | 0 | Includes **newly reconstructed inferred** zero-byte `py.typed` marker |
| Tests | 39 | 9 | 30 | Eight unit tests and `tests/conftest.py` present; others missing from their original paths |
| Root | 6 | 4 | 2 | Missing `CHANGELOG.md` and `uv.lock` |
| **Total** | **117** | **36** | **81** | Does not count supplemental `reconstruction_drafts/` and audit tooling |

### Source code caution

The source count covers 23 *existing paths*, NOT 23 fidelity-certified restorations.
The zero-byte `src/agent_accelerator/py.typed` marker was restored on this branch in commit `ec8261842fece67cfd4dab991f53e03a09a1bcc5`, read back from GitHub, and **explicitly labelled inferred**. A PEP 561 marker is ordinarily empty, but original-byte equality is not established.

Existing source-level issues remain, including mismatched public/private helper names in `judge.py` versus recovered judge tests (`data_marker`, `tool_results_text`).

### Nine present test entries

- `tests/conftest.py`
- `tests/unit/test_adapters.py`
- `tests/unit/test_compare.py`
- `tests/unit/test_compare_statistics.py`
- `tests/unit/test_config.py`
- `tests/unit/test_dataset.py`
- `tests/unit/test_readings_pairwise.py`
- `tests/unit/test_scorers.py`
- `tests/unit/test_tool_metrics.py`

The listed active unit tests may still have unverified import, fixture, dependency and runtime requirements. Their presence is not a full-suite pass.

### Selected absent tests with existing provisional drafts

| Original active test path | Current review-branch provisional draft |
| --- | --- |
| `tests/unit/test_judge.py` | `reconstruction_drafts/test_judge_FULL_DRAFT.py` |
| `tests/unit/test_readings.py` | `reconstruction_drafts/test_readings_FULL_DRAFT.py` |
| `tests/unit/test_export.py` | `reconstruction_drafts/test_export_FULL_DRAFT.py` |
| `tests/unit/test_report.py` | `reconstruction_drafts/test_report_FULL_DRAFT.py` |
| `tests/unit/test_judge_pairwise.py` | `reconstruction_drafts/test_judge_pairwise_PARTIAL_lines_1_509.py` |
| `tests/unit/test_cli.py` | `reconstruction_drafts/test_cli_PARTIAL_lines_1_364.py` |

Drafts have Python syntax/integrity checks but have NOT passed source-byte-fidelity or native runtime verification. They are deliberately excluded from ordinary pytest collection.

## Prioritised next recovery sequence

1. Complete original video transcription of `test_judge_pairwise.py`, source editor lines **510–724**; `test_cli.py`, lines **365–1133**. Both video entries are indexed in the user Library but raw video access is unavailable in this runtime.
2. Restore original **calculator example and fixture files**, especially `examples/calculator/agent.py`, `examples/calculator/dataset.jsonl`, `tests/fixtures/calculator_broken_redacted.json`, and `tests/fixtures/calculator_capture_content.json`. Without them, full test coverage cannot be established. A recreated fixture must be labelled as a substitute unless exact original evidence exists.
3. Cross-check `test_judge.py` against the original judge module and resolve `data_marker` / `tool_results_text` using source evidence before modifying historical semantics.
4. Restore original `scripts/ci.sh`, CI workflow, missing test modules, examples and docs as evidence becomes available; recover `uv.lock` from original if possible rather than misrepresent a freshly generated lockfile.
5. Perform dependency-installed offline pytest, type checks and CI on the review branch, including optional framework integration where available, without credentials, external model calls or paid APIs.
6. Only after fidelity and actual runtime verification, consider promoting reviewed drafts into `tests/unit/` and merging into `master`.

## Explicit limitations

This audit does not claim 36 files faithfully reconstructed, 81 definitively lost from all sources, or a usable end-to-end AEA release. It only proves absence or presence **at the 117 original inventory paths on this branch** at audit time. Additional partial content may be retained elsewhere in draft paths, earlier branches, saved files or recordings.

Do not commit historical evaluation traces blindly; review for personal data, client information, secrets and private payloads.
