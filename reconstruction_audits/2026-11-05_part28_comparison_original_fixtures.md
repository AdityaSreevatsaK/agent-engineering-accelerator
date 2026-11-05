# AEA reconstruction checkpoint — 5 November 2026, Part 28: fixture-independent comparison verification

**Repository:** `AdityaSreevatsaK/agent-engineering-accelerator`  
**Reconstruction target:** `reconstruction/wip-checkpoint-2026-10-30`  
**Master:** unchanged; this PR was **not** a whole-reconstruction release or fidelity sign-off.

## Substantive new validation

**PR #16:** https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/16  
**Merged to reconstruction:** `791bd75b3ce13cbeb4e44fa79355b988f98ab822`

Two original-path source suites were examined, **without modifying either original test file**:

- `tests/unit/test_compare.py`: 66 top-level test functions.
- `tests/unit/test_compare_statistics.py`: 17 top-level test functions.

The original fixture files `tests/fixtures/calculator_capture_content.json` and `tests/fixtures/calculator_broken_redacted.json` are still unrecovered. Their content-dependent tests cannot be justified by guessed synthetic replacements, since they assert precise case identities, counts and statistics.

Added `reconstruction_tools/run_compare_without_original_fixtures.py`: an explicit deferred-test manifest and AST preflight. It deliberately excludes **30 functions from `test_compare.py` and 2 functions from `test_compare_statistics.py`**, totalling **32 top-level functions**, which expand to **58 parameterised pytest cases**. The preflight validates that every deferred name exists and follows source-level `FIXTURES` references **transitively through intermediate helpers**. It fails rather than silently reclassifying newly fixture-dependent tests.

**CI outcome:** new `.github/workflows/reconstruction-compare-offline.yml` exercises the unchanged remaining original test assertions with actual `agent_accelerator.compare` and `stats` modules using Python 3.11/3.12 on Ubuntu and Windows. No cloud credentials or paid APIs.

### Confirmed comparison CI run `42050459658`

| Environment | Native pytest |
| --- | --- |
| Ubuntu Python 3.11 | **70 passed, 58 deselected** |
| Ubuntu Python 3.12 | **70 passed, 58 deselected** |
| Windows Python 3.11 | **70 passed, 58 deselected** |
| Windows Python 3.12 | **70 passed, 58 deselected** |

Four successful completed GitHub CI jobs; all four individual pytest logs inspected.

### Failure-driven improvement

First CI run `42050208618` showed **70 passed, 5 failed, 53 deselected** on Ubuntu. The five failures were not demonstrated compare-engine bugs; they attempted to load the absent original calculator capture file through `write_tool_count_log()`, which calls `write_epoch_log()`, which loads `FIXTURES`. The initial gate checked only direct helper names.

The runner now **computes transitive AST helper dependencies** rather than listing immediate helpers manually. The two additional top-level fixture-dependent functions are `test_case_tool_calls_are_the_mean_over_epochs_that_recorded_a_count` and `test_case_tool_calls_are_none_when_no_epoch_recorded_a_case_checks_count`. Their five parameter-expanded cases are explicitly deferred, not deleted or counted as passing. This restored all four green comparison jobs.

### Existing regression gates on final PR commit

Three other workflows ran alongside comparison verification, all four jobs in each confirmed successful:
- `42050459647`: core judge/readings/report/export/CLI/config/dataset/scorers/tool metrics — **811 passing** per environment, **2 unavailable-example-config cases deselected**.
- `42050459581`: build/run/scrub with **CI-only temporary synthetic data** — **46 passing** per environment.
- `42050459554`: native LangGraph/Strands framework adapters against **local model doubles** — **53 passing** per environment.

## Scope of verified coverage

| Separate workflow | Native pytest passes per environment | Deferred cases |
| --- | ---: | --- |
| Core regression | 811 | 2 example config cases |
| Synthetic calculator build/run/scrub | 46 | Original calculator fixtures not tested |
| Strands/LangGraph native adapters | 53 | Real cloud providers not tested |
| Fixture-independent comparison/statistics | 70 | 58 parameter-expanded fixture cases |
| **Distinct per-environment total across workflows** | **980** | **60 explicitly deselected parameter-expanded cases, plus other uncollected original files** |

**Important:** 980 is the arithmetic sum of different CI suites, **not** the result of a single complete-project pytest run and **not** evidence that the original source v2.2.0 is fully reconstructed. Deferred tests are *not passing*. Previous `test_init.py` and `test_stats_compare.py` master-only verification runs are not silently added to this 980 count.

## Remaining blockers

1. Restore the original **calculator example agent, dataset and captured/broken JSON fixtures**. Do not commit synthetic files as originals.
2. Restore **triage and expense example configuration files** to enable the two excluded `test_config.py` cases.
3. Finish the original source-video transcription of `test_cli.py` after editor line 364 and `test_judge_pairwise.py` after line 509.
4. Verify original fixture-based comparison regression and statistical reference assertions, release packaging, baseline files, docs and complete project CI.
5. Preserve original draft transcriptions, and do not merge the entire reconstruction review branch to `master` without fidelity and acceptance sign-off.
