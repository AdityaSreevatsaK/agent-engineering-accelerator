# Final eight reconstruction review branches: disposition audit

**Date:** 12 November 2026  
**Scope:** Branch housekeeping only, not historical-source certification or release approval.  
**Protected:** `master`, `reconstruction/wip-checkpoint-2026-10-30`. Neither is a deletion target.

## Open PR reconciliation

PR [#33](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/33) was **closed without merge**, because its former replay runner staged and cleaned up the unprovided historical calculator capture fixture paths inside the checkout. The already-merged `reconstruction_tools/run_original_compare_with_generated_fixtures.py` uses isolated generated fixtures, copies of source-backed historical tests, and derived legacy schema, without writing original historical fixture paths. Four-platform CI exists at `.github/workflows/reconstruction-original-compare-fixture-replay.yml`. Combining the older and safer runners adds duplication and increases accidental fixture-loss risk. No historical fixture is claimed recovered.

## Review branches

| Old review branch | Single recovered file | Comparison with integration | Decision |
|---|---|---|---|
| `compare-review` | `src/agent_accelerator/compare.py` | Exact Git blob match | Remove |
| `judge-review` | `src/agent_accelerator/judge.py` | Integrated version adds compatibility aliases and an isolated format-only fix | Remove obsolete version |
| `readings-review` | `src/agent_accelerator/readings.py` | Integrated version contains four small fixes, including duplicate-case handling and message formatting | Remove obsolete version |
| `report-review` | `src/agent_accelerator/report.py` | Integrated version fixes empty Markdown table cells and pairwise label handling | Remove obsolete version |
| `test-adapters-review` | `tests/unit/test_adapters.py` | Exact Git blob match | Remove |
| `test-compare-review` | `tests/unit/test_compare.py` | Exact Git blob match | Remove |
| `test-compare-statistics-review` | `tests/unit/test_compare_statistics.py` | Integrated version has two newer expectations using ASCII arrows rather than Unicode arrows | Remove obsolete version |

All branch heads, original Git blobs and current integration Git blobs are recorded in [the final cleanup manifest](../reconstruction_manifest/branch_cleanup_2026-11-12_final.json). Distinct old SHA references and reasons for the four newer revisions are retained here, but deleted unmerged branch commits are not guaranteed to remain retrievable from GitHub indefinitely. The authoritative reconstructed source files remain in the integration branch. The historical 97/117 path inventory is unchanged.

## Deletion protections

- No branch is deleted in pull-request validation. It performs unit tests and live read-only API checks.
- An integration-branch push workflow repeats validation with GitHub API before deleting each target.
- Ref identity, branch protection, open PRs, Git blobs and the closure/non-merger status of PR #33 are checked; any unexpected change skips or blocks deletion.
- All deletions use a short-lived CI token scoped to repository contents and produce a downloadable audit.
- GitHub automatically deletes the temporary cleanup PR head after merge.
- **No change to `master`.** This is not authorisation to release AEA into production.

Expected final branches: `master` and `reconstruction/wip-checkpoint-2026-10-30` only.
