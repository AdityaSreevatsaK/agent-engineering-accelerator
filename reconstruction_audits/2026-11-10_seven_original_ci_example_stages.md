# Replay of all seven historical CI example stages — 10 November 2026

## Purpose and boundary

The original video-recovered scripts/ci.sh has seven named application regression stages, but cannot safely run in its historical form: uv.lock and original baselines are missing. Its original GitHub Actions workflow also remains archived and inactive. Previous generated-baseline testing covered only three of the seven example workflows.

This new, independent reconstruction-only CI lane exercises all seven original application stages by **running real reconstructed AEA on local deterministic offline model doubles**, creating **temporary fresh baseline logs**, rerunning the same agent, and introducing a known seeded regression. It never claims that its generated logs are original historical baselines, or that it reproduces historical version-pinned dependency resolution.

Original scripts/ci.sh, source files, datasets, baseline paths and master are unchanged. The verifier reads the original script and will refuse to run if its seven recorded lane names, baseline paths, dataset paths, adapter selections, factory names, scorer or mapping flags drift.

## Exact example-stage coverage

| Historical stage | Original dataset cases | Expected good-source failures | Additional mutant failures |
| --- | ---: | ---: | ---: |
| calculator-strands | 10 | 0 | 2 subtraction cases |
| calculator-langgraph | 10 | 0 | 2 subtraction cases |
| orders-strands | 11 | **1 original source conflict** | 2 invalid-refund cases |
| expense-langgraph | 12 | 0 | 3 missing-receipt cases |
| triage-langgraph | 12 | 0 | 2 urgent-billing cases |
| policy_rag-langgraph | 11 | 0 | 2 hallucinated hotel-policy cases |
| helpdesk-langgraph | 10 | 0 | 2 administrative approval-gate cases |
| **Total** | **76 across seven stage runs** | **1 known original mismatch** | **15 new seeded regressions** |

Each stage generates three independent native AEA run directories (first good, repeat good, seeded mutant) and two real CLI comparisons (good-to-good should be OK, good-to-mutant should be REGRESSION). Totals for the full one-platform test: **21 AEA CLI runs; 14 baseline comparisons; 228 case evaluations** (76 each phase). Every scenario checks the dataset IDs and source SHA256, original and newly failing case IDs, scrubbed Inspect logs and trace/report presence, correct CLI pass totals, comparison output, and immutability of the temporary baseline.

The known orders inconsistency is genuine recorded evidence. Its video-recovered rules return the phrase "Carol has spent", while the screenshot-derived dataset expects "Carol spent". This is preserved as an existing failing case in both *good* runs and in the mutant. The comparison should not call an unchanged historical failure a new regression. Do not modify the original source or assertion solely to make good-source Orders 11/11.

## How to run

From the reconstructed integration branch, with Python 3.11 or 3.12:

~~~sh
python -m pip install -e ".[strands,langgraph]"
python -m unittest reconstruction_tools.test_original_ci_example_matrix -v
python -m reconstruction_tools.replay_original_ci_example_matrix --scenario all
~~~

To isolate one original stage:

~~~sh
python -m reconstruction_tools.replay_original_ci_example_matrix --scenario orders-strands
~~~

All generated output lives in TemporaryDirectory. The tool disables common AWS, OpenAI, Anthropic, Azure OpenAI and Google API credential environment variables before every subprocess, and references only explicit offline model factories. No original baseline file is read, modified, reconstructed or copied to the repository.

The new CI workflow uses both Windows and Ubuntu and Python 3.11 and 3.12. Its pass/fail evidence is a replacement **example-stage** validation, not the original CI workflow.

## What this does not resolve

- The original uv.lock and locked historical dependency resolution.
- The original .github/workflows/ci.yml path and historical reference-baseline bytes.
- Fourteen historical baselines or the two unavailable calculator captured-log fixtures.
- Full historical video-transcription byte accuracy or documented source contradictions.
- Human-approved retention, privacy and production-security review.
- Historical scripts/ci.sh Ruff, format, Pyright, unit and conformance phases; those are covered separately by reconstruction CI workflows, not by this seven-stage replay.

This adds **zero** historical files to the 97/117 recovered-path inventory and must not be used to approve master automatically.

Cross-references: reconstruction_audits/2026-11-09_release_evidence_readiness.md; reconstruction_audits/2026-11-09_disposable_baseline_replay.md; reconstruction_audits/2026-11-09_ci_activation_readiness.md.
