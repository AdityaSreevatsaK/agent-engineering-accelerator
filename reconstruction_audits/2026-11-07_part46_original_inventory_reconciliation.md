# AEA v2.2.0 reconstruction: original-path inventory reconciliation

**Checkpoint:** 7 November 2026  
**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Reviewed branch SHA:** `reconstruction/wip-checkpoint-2026-10-30` at `3a78632072907e1edf9be4534862ad21e1847d41`  
**Source of expected paths:** the historical 117-path inventory captured from folder screenshots in `AEA_reconstruction_manifest.md` (25 October 2026).  
**Method:** exact original-path comparison against the recursive Git tree at `860c0f9e81f825ca9eb522d088ed0a16767bdf73`. This is a **presence audit only**, not a source-byte fidelity check.

## Exact historical-path results

| Original inventory category | Expected | Present at original path | Absent |
| --- | ---: | ---: | ---: |
| CI workflow | 1 | 0 | 1 |
| Baselines | 14 | 0 | 14 |
| Original documentation | 2 | 0 | 2 |
| Examples | 31 | 3 | 28 |
| Scripts | 1 | 0 | 1 |
| Source modules and markers | 23 | 23 | 0 |
| Tests, including conformance and fixtures | 39 | 23 | 16 |
| Root files | 6 | 4 | 2 |
| **Total** | **117** | **53** | **64** |

The three original-path examples now present are `examples/calculator/agent.py`, `examples/calculator/dataset.jsonl`, and `examples/calculator/rules.py`. All 23 source paths exist, but some are provisional or compatibility-adjusted and none is certified byte-identical to the historical repository. The branch also contains extra tests, reconstruction drafts, offline verification tools and workflows; they are **not** counted as original-path restorations.

## Key remaining original-path gaps

**Blocking historical fixtures:**
- `tests/fixtures/calculator_capture_content.json`: original minified Inspect JSON (57,844 displayed characters in user video). Video inspection verifies high-level facts but cannot reliably reconstruct every historical event ID, timestamp and field byte. The original 58 parameter-expanded assertions remain deferred.
- `tests/fixtures/calculator_broken_redacted.json`: original source bytes missing. A screenshot-derived candidate exists separately under `reconstruction_drafts/`, explicitly not masquerading as an original.
- `examples/triage/aea.toml` and `examples/expense/aea.toml`: missing original configurations, accounting for two more deferred test cases.

**Reconstructed but not restored at exact original test paths:** `tests/unit/test_cli.py` and `tests/unit/test_judge_pairwise.py` have complete 1,133-line and 724-line video-derived provisional candidates under `reconstruction_drafts/`. Dedicated supplementary/compatible tests exercise recovered contracts, but the historical originals have not been promoted as exact source files. `tests/unit/test_langgraph_adapter.py` also remains absent from its historical path.

**Other missing original inventory:** the original `.github/workflows/ci.yml`, all 14 historical baselines, `docs/acceptance.md`, `docs/review.md`, `scripts/ci.sh`, `CHANGELOG.md`, `uv.lock`, 28 example files, and the remaining conformance, fixture and unit-test paths. Baseline traces must be reviewed for private or client content before any commit. Do not substitute regenerated lockfiles or synthetic traces while claiming historical identity.

## Runtime validation is separate from fidelity

At the reviewed SHA, the latest GitHub Actions run `42265228869` completed successfully: eight jobs across Windows/Ubuntu and Python 3.11/3.12 for native offline tests and static integrity. Prior review-branch audits also report a working local deterministic AEA/Strands smoke flow, real offline calculator 10/10 and broken 8/10, and installed-dependency checks. These results support reconstructed application behaviour. They **do not** prove the absent originals, byte equality, cloud-provider behaviour, or unexecuted slow/subprocess coverage. The original 60 fixture/config-dependent test cases remain explicitly deferred.

## Evidence-first next actions

1. Request the **actual original JSON files** `tests/fixtures/calculator_capture_content.json` and `tests/fixtures/calculator_broken_redacted.json` if available. A screen video of a long minified log is not equivalent to original JSON bytes. Review contents for private data before uploading/committing.
2. Request complete text or recordings of `examples/triage/aea.toml` and `examples/expense/aea.toml`; these are small, high-value files that unlock two historical test cases.
3. Review the full `test_cli.py` and `test_judge_pairwise.py` candidates line by line against source video before promoting them. Assess the already received `test_langgraph_adapter.py` video/draft and the original tests/conformance inventory.
4. Recover the remaining original examples, scripts, CI, docs and optional baselines based on evidence. Preserve a clear distinction between original, provisional recovered, and newly written validation files.
5. Execute fixture-dependent tests and slow/integration lanes once the original inputs become available. Retain Windows/Linux Python 3.11/3.12 gates, security reviews and `master` separation until final acceptance.

**Release boundary:** This is a newly authored inventory checkpoint, not a historical AEA v2.2.0 file. `master` remains separate and the reconstruction must not be represented as fully restored or approved for release.
