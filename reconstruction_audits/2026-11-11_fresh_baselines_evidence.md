# Newly generated AEA baselines — historical evidence boundary (11 November 2026)

## Purpose

The original AEA v2.2.0 manifest lists 14 historical baseline artefacts under `baselines/`, all unavailable at their original paths. They cannot be recreated byte-for-byte without the original runs.

`baselines-new/` is a **separate modern output directory**, not an attempt to recover original baselines or inflate the 97/117 historical-path count. Future authenticated historical files may be copied to `baselines/` after privacy review.

## Generation contract

- Uses reconstructed offline Strands and LangGraph agents, one sample at a time.
- Calls AEA's native `check --update-baseline`, which enforces `--capture-content` exclusion and validates replacement paths.
- Stages all seven runs in a temporary workspace, refuses pre-existing output destinations, and moves generated runs to `baselines-new/` only when validated.
- Records UTC generation time, code commit, canonical dataset file SHA256, case count and log SHA256 in `manifest.json`.
- Uses neither paid providers nor model API credentials. Logs are default-redacted, not plaintext captured logs.
- On GitHub Actions, uploads the generated directory as a short-lived artifact instead of committing unknown log contents without human review.

## Original Orders contradiction discovered during first generation

The 11 November CI run generated all seven baseline logs but the **additional strict case audit failed on Orders `total_spend`**. AEA's overall `status=success` did not mean all checks passed: Orders was **10/11**.

This mismatch was already explicitly documented in `reconstruction_tools/check_orders_original_end_to_end.py`, and `verify_orders_original_sources.py` pins both independently recovered originals:

- Recorded source `examples/orders/rules.py` returns **\"Carol has spent 17.50 across 2 orders.\"**.
- Recorded screenshot dataset `examples/orders/dataset.jsonl` expects **\"Carol spent 17.50 across 2 orders.\"**.

**Historical source and dataset are preserved unchanged.** An initial attempt to normalise the source reply was reversed before the PR merge when the stronger video evidence was found.

The generator now allows **exactly this one pinned, documented mismatch**, labelled as `failed_case_ids: ["total_spend"]` and `known_historical_mismatch: true` in the generated manifest. **Every other dataset case in all seven runs must pass; any extra failed case aborts generation.**

This is a historical reconstruction defect to disclose in demos, not to conceal by editing an original test or rule.

## Project impact

A fully usable new baseline can include a recorded pre-existing failing case and still serve as a comparison reference. However, this should **not** be described as a 100% passing modern baseline. The original comparison baseline and the new generated artefact are separate datasets/revisions.

A release candidate may choose to add an explicitly modern, post-reconstruction *compatibility patch* for Orders in its own workstream, with its own tests. It must not replace video-pinned historical source without an explicit decision.

## Other missing historical files

Two original Markdown docs (semantically reviewed as provisional drafts), one original workflow, two calculator fixture JSON captures and the original `uv.lock` remain missing at historical paths. The user previously confirmed that exact original calculator captures and historical lockfile are unnecessary to continue current offline CI. The original baselines would be useful if ever found, but no more video files are currently required for this generator.
