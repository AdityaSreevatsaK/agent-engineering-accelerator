# AEA reconstruction | 5 November 2026 | Part 27: original core tests and framework adapters

Repository: `AdityaSreevatsaK/agent-engineering-accelerator`  
Verification branch: `reconstruction/wip-checkpoint-2026-10-30`  
Master: **not modified** in this continuation.  
Status: still a partial reconstruction of historical AEA v2.2.0; no release or historical-byte-fidelity sign-off.

## Verified native tests and merged pull requests

### PR #14: expand the recovered core regression gates

Pull request: https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/14  
Merged to reconstruction: `418d74a5383588da4391f8a5f23845728589e4a2`.

Extended the existing judge/report/CLI/export/readings workflow to run four previously present original-path suites, **without editing their source**:
- `tests/unit/test_config.py`
- `tests/unit/test_dataset.py`
- `tests/unit/test_scorers.py`
- `tests/unit/test_tool_metrics.py`

First Ubuntu Python 3.12 run: **811 passed, 2 failed**. The two failures were due solely to missing original example configuration files `examples/triage/aea.toml` and `examples/expense/aea.toml`, not to a demonstrated implementation error.

The CI configuration now explicitly **deselects exactly these two original-example tests** until the real files are recovered:
- `test_example_config_loads_and_every_reference_it_names_resolves_to_a_callable[triage]`
- `test_example_config_loads_and_every_reference_it_names_resolves_to_a_callable[expense]`

No original files were invented and the tests themselves were not changed. These are known **coverage gaps**, not passing tests.

**Verified GitHub Actions runs**:
- `42047614510`: **811 passed, 2 deselected, 61 warnings** on each of Ubuntu Python 3.11, Ubuntu Python 3.12, Windows Python 3.11, Windows Python 3.12. Four completed successful jobs, four individual pytest logs inspected.
- `42047614496`: separate synthetic build/run/scrub workflow, **46 passed per environment** on the same four configurations. Four completed successful jobs, four logs inspected.

### PR #15: native framework integration of LangGraph and AWS Strands

Pull request: https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/15  
Merged to reconstruction: `061c68c8454e1e824ca4b59587413a21ead21ba7`.

Added `.github/workflows/reconstruction-adapters-offline.yml` to test the existing, **unchanged**, 803-line `tests/unit/test_adapters.py` suite. This suite had been excluded from prior CI because it imports framework SDKs directly.

The new workflow installs the AEA package with **real, declared optional `[langgraph,strands]` dependencies** and pytest. It executes deterministic in-process models and framework agent doubles and does **not** require provider API keys, Bedrock, paid models, network model requests or deployment.

**Verified GitHub Actions run `42047985243`**:
- Ubuntu / Python 3.11: **53 passed**
- Ubuntu / Python 3.12: **53 passed**
- Windows / Python 3.11: **53 passed**
- Windows / Python 3.12: **53 passed**

All four jobs completed successfully; four individual test logs inspected.

The PR's inherited existing judge/report and synthetic build/run/scrub workflows also completed successfully (runs `42047985331` and `42047985097`, respectively).

## Coverage interpretation

Across the three **distinct** test groups, the latest verified counts are:

| Test group | Cases verified in each four-platform matrix |
|---|---:|
| Core judge/report/CLI/export/readings/config/dataset/scorers/tool metrics | 811 |
| Build/run/scrub contracts using temporary synthetic calculator inputs | 46 |
| Native LangGraph/Strands framework adapter suite | 53 |
| **Total separately verified pytest cases** | **910** |

**910 is not a count from one complete-suite pytest run**, and not the original AEA test total. It is a sum of non-overlapping suites validated in independent workflows on Ubuntu/Windows with Python 3.11 and 3.12. Synthetic inputs are test-only stand-ins and **not restored original source or fixtures**. The framework adapter tests use real installed frameworks but fake agent/model behaviour.

## Remaining blockers

1. Original example configs and package files for `examples/triage/` and `examples/expense/` are absent. The two original config reference-resolution tests are **deferred**, not passed.
2. Original `tests/fixtures/calculator_capture_content.json` and `calculator_broken_redacted.json`, along with the calculator agent/dataset, are absent. `tests/unit/test_compare.py` and `test_compare_statistics.py` contain fixture-dependent tests and are **not included** in this expanded CI gate; these still require source-backed verification.
3. Original `test_cli.py` recording remains partial after line 364; `test_judge_pairwise.py` remains partial after line 509.
4. Remaining original examples, docs, CI/scripts, baselines and historical source correctness need recovery or explicit decisions.
5. A complete active `pytest tests/unit` run, release packaging and end-to-end original-fixture evidence are still **not verified**. Do not merge the whole reconstruction branch into `master` until those gaps are resolved and the code is reviewed.

## Recommended next work

Recover original user recordings and fixtures as they become available, then run fixture-dependent compare tests and full repository CI. Independently, the next safe verification task is to run **only fixture-independent compare/statistics assertions** with an explicit list of excluded original-fixture cases, preserving their source tests and recording every deferral. Continue incremental PRs into the reconstruction branch, not blanket promotion.
