# PR #87: fresh offline baseline artifact integrity and provenance review — 11 November 2026

**Nature:** New reconstruction verification evidence, *not* a recovered historical document or baseline.

**Source PR:** https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/87  
**PR source head reviewed:** `70ed5098a360cd88f8486ec0fc78e082da4d293f`  
**Successful fresh-baseline workflow:** https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/actions/runs/43068173167  
**Artifact:** `aea-baselines-new-offline-scrubbed` (GitHub artifact ID `13877397857`, retention 14 days).  
**Manifest `git_revision`:** `0f03bcf5c465002cd1a15ad2220a43a2330adebd` — GitHub Actions' *pull-request synthetic merge checkout*, not the PR source-head commit; record both to avoid a false provenance equivalence.

## Independent artifact examination

The downloaded ZIP contained exactly 23 entries: a README, a manifest, and an Inspect evaluation JSON, Markdown report, and JSONL trace file for each of seven agent configurations. No duplicate archive names or path traversal segments were found.

| Reconstructed agent | Cases passing | Trace spans | Expected historical mismatch |
| --- | ---: | ---: | --- |
| Calculator / Strands | 10/10 | 67 | none |
| Calculator / LangGraph | 10/10 | 95 | none |
| Orders / Strands | 10/11 | 89 | `total_spend` |
| Expense / LangGraph | 12/12 | 245 | none |
| Triage / LangGraph | 12/12 | 80 | none |
| Policy RAG / LangGraph | 11/11 | 131 | none |
| Helpdesk / LangGraph | 10/10 | 115 | none |
| **Total** | **75/76** | **822** | **one recorded, unchanged original conflict** |

Verification of the *downloaded bytes*, not just the CI workflow definition, confirmed:

- The manifest has schema `aea-fresh-baselines-v1`, seven unique expected names, the explicit "NOT a historical baseline" provenance string and `capture_content=false`.
- All seven Inspect JSON log SHA256 digests match the manifest; individual case counts and unique case IDs match the documented datasets.
- The generated Inspect logs carry `status=success` and `capture_content=false`. That overall success value is **not** mistaken for a 100% passing case score.
- Score-level failures comprise exactly `orders/total_spend`. Manifest `passed_cases`, `failed_case_ids` and `known_historical_mismatch` agree with actual samples.
- For every sample, the inspected `input` and `target` fields are `[REDACTED]`, message collections are empty, and generated model output content/choices are empty.
- In the JSONL trace spans, inspected sensitive fields `input.value`, `output.value`, `gen_ai.tool.call.arguments` and `gen_ai.tool.call.result` use documented redaction markers. The seven trace files are readable JSONL.
- The artifact was generated from synthetic offline example agents; neither historical `baselines/` nor the source-pinned Orders rules/dataset was rewritten.

**Limit:** These checks establish the inspected offline synthetic artifact's recorded redaction properties, not universal privacy safety for arbitrary user-supplied agents or a complete security review. Case names, tool names, timestamps, metadata and hashes remain available. Inspect any future captured baseline before distribution.

## Disposition and release boundary

Prefer the short-lived downloadable GitHub Actions artifact for current evaluation evidence. Do **not** routinely check generated `baselines-new/manifest.json` or run directories into Git. The adjacent modern `baselines-new/.gitignore` is a safety control against accidental commits; a deliberate `git add -f` may follow specific human content and provenance approval. The existing `baselines-new/README.md` remains tracked.

No newly generated artifact is one of the 14 unavailable historical `baselines/` originals. The **historical inventory remains 97 present of 117 original paths**. The 20 missing original paths comprise 14 old baseline artefacts, two original documentation files, one original workflow, two calculator capture fixtures and the original `uv.lock`.

The two documentation drafts have been checked against their videos for semantic structure, but their source bytes cannot be authenticated; the historical CI candidate is archived and cannot replace the old locked, baseline-dependent workflow without mislabelling. Four original unit-test candidates match video-editor line totals while retaining small, explicitly documented character discrepancies. Do not invent missing bytes to inflate fidelity counts.

**Next gate:** Confirm *all* required CI jobs for PR #87 at the actual source head succeed before merging into `reconstruction/wip-checkpoint-2026-10-30`. The manifest checkout SHA identifies GitHub's test merge ref; it does not imply `master` approval.
