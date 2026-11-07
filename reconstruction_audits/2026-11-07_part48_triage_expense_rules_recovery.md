# AEA original source recovery: triage and expense rules (Part 48)

**Date:** 7 November 2026  
**Base:** `reconstruction/wip-checkpoint-2026-10-30` at `d8485b65`  
**Evidence:** user-provided original Notepad++ scroll recordings of `examples/triage/rules.py` and `examples/expense/rules.py`.

## File-level provenance

| Historical original path | Candidate LF character count | LF-terminated lines | Video editor displayed lines | Expected Windows CRLF characters | Reconstructed CRLF characters | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `examples/triage/rules.py` | 6,467 | 161 | 162 | 6,628 | 6,628 | Visually transcribed and count-matched candidate |
| `examples/expense/rules.py` | 9,685 | 219 | 220 | 9,906 | 9,904 | **Provisional**, two characters shorter than screenshot |

Do not silently add filler characters merely to force length matching. Count agreement is corroborating evidence, not original-byte-fidelity certification. Both files were checked against overlapping video frames and parsed successfully by Python. The original code's business rules were copied rather than re-authored.

### Source behaviour and integration validation

- Triage: `classify` applies source-defined prompt-dependent routing, while `lookup_invoice`, `search_known_issues`, and `escalate_to_human` use deterministic local data. The prompt-rewording regression is intentional and testable.
- Expense: original prompt-dependent `active_rules`, `plan`, `next_step`, `review`, policy lookup, currency conversions and per-diem calculations are available, including intentionally removed receipt rule in `PROMPT_CONDENSED`.
- Added a stdlib source-count, SHA-256 and deterministic business-rules audit; also a real LangGraph offline smoke lane with recorded `SimulatedTriageModel` and `SimulatedReviewModel`.
- The two original configuration cases for triage and expense are re-enabled in the integrated suite. The recovered `test_cli.py` candidate's original configuration parameterisations are also included in the separate fast replay.
- **Never** invoke triage `build_live_agent()` in CI; it uses the optional AWS Bedrock provider.
- Original `examples/triage/dataset.jsonl`, `examples/expense/dataset.jsonl`, original test modules, and the two original calculator Inspect JSON fixtures are still missing. Synthetic smoke inputs never become historical originals.

## Historical inventory and deferrals

The prior checkpoint had 57 of 117 historical original paths present. These **two** restored `rules.py` paths, if merged, bring original-path presence to **59/117** (58 still absent). Original active-suite deferrals fall from **60 parameter-expanded cases** to **58**, provided both previously missing example-config cases pass on all four CI platforms. Thirty-two historical compare/statistics test functions can also be exercised on separately generated Inspect logs, but the original 58 fixture-dependent cases remain deferred in the normal integrated suite.

**Release boundary:** candidate source recovery and offline execution do **not** constitute exact historical source restoration, original cloud-model acceptance, or readiness to merge into `master`. The expense rules editor-count discrepancy and the previously recorded triage agent two-character discrepancy remain open source-fidelity issues.
