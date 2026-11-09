# AEA reconstruction: functional baseline replay, 9 November 2026

## Purpose and provenance

The historical AEA v2.2.0 baseline files are still missing. This verification creates **new, disposable** baseline logs by running the recovered calculator, triage and expense agents through the actual AEA `check` CLI, using deterministic local model doubles.

**Do not** count generated captures as recovered original files, rename them to historical paths, or regard matching pass counts as historical byte fidelity. The original baseline inventory remains incomplete.

## New cross-example regression contract

`python -m reconstruction_tools.verify_recovered_example_baselines --scenario all` executes three `check` commands per example in distinct evaluation subprocesses:

1. `--update-baseline` on the healthy agent. Requires 100% case passes, a valid Inspect log, all expected case IDs, the expected dataset hash and default redacted sample fields.
2. `check` with the unchanged agent. Requires the `OK` verdict.
3. `check` with the deliberately changed agent. Requires exit 1, `REGRESSION`, an exact known set of failing case IDs, a stored comparison document and an unchanged baseline directory.

All runs, reports and traces are under `TemporaryDirectory`; no output is added to `baselines/`, `tests/fixtures/` or any recorded historical location. AWS credentials are cleared and only offline simulated models are invoked.

| Example | Healthy passing | Deliberately failing case IDs |
| --- | ---: | --- |
| Calculator (Strands) | 10/10 | `subtract`, `subtract_large` |
| Triage (LangGraph, custom state mapping) | 12/12 | `charged_twice_furious`, `angry_invoice_dispute` |
| Expense (LangGraph, custom grounding scorer) | 12/12 | `receipt_missing_over_75`, `receipt_missing_after_conversion`, `reject_no_receipt` |

A matrix workflow runs the new replay across Windows and Ubuntu, Python 3.11 and 3.12. These are new functional checks **in addition to** earlier example `run` tests, original recorded test replay and generic starter CLI tests.

## Readiness boundary

- This verifies reconstructed behaviour and generated baseline safety, **not** original historical baselines, original run IDs, timestamps or stored trace content.
- Previously recorded baseline screenshots only prove path inventory unless complete source contents are available.
- The original 14 baseline artefacts, two calculator capture fixtures, `uv.lock`, two original docs and original CI path are not substituted here.
- Keep the full reconstruction off `master` pending original evidence and release sign-off.
