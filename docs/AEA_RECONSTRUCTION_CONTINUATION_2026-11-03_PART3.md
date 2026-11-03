# AEA reconstruction continuation — 3 November 2026 (Part 3)

**Status:** Work in progress. No master merge. These are provisional video transcriptions, not verified source files.

## Source drafts committed this continuation

| Original test | Reconstructed source lines | Original displayed lines | Unique top-level tests | GitHub draft path |
| --- | ---: | ---: | ---: | --- |
| `test_readings.py` | 873 | 1,605 | 37 | `reconstruction_drafts/test_readings_PARTIAL_lines_1_873.py` |
| `test_export.py` | 206 | 749 | 15 | `reconstruction_drafts/test_export_PARTIAL_lines_1_206.py` |
| `test_judge.py` | 208 | 1,560 | 10 | `reconstruction_drafts/test_judge_PARTIAL_lines_1_208.py` |

The original `test_readings_pairwise.py` full provisional 156-line draft remains in `tests/unit/`, but its original editor reports 157 displayed lines and a one-character discrepancy remains.

### What was checked

- Each new draft passes Python AST parsing using the 3.11 grammar and Python compilation.
- All 37, 15, and 10 top-level test names are unique within their partial files.
- Original editor line-number positions were preserved in the sections reviewed.
- GitHub blobs were read back and matched the local drafts byte-for-byte.
- Partial tests were saved in `reconstruction_drafts/` instead of the active test suite.

### Outstanding source questions

1. The original `test_judge.py` recording imports `data_marker` and `tool_results_text`, while the current provisional `judge.py` defines `_data_marker` and `_tool_results_text`. This import contract is unresolved. No speculative implementation edit was made.
2. `test_readings_pairwise.py` expects sorted, deduplicated case names. Current provisional `readings.py` may repeat names when several epochs share a case ID. Reconcile against original sources before modifying.
3. Remaining old source transcription character-count discrepancies are unresolved; no arbitrary padding was introduced.
4. The large `calculator_capture_content.json` and partially visible `calculator_broken_redacted.json` cannot be reconstructed byte-for-byte from the current evidence.
5. The original native pytest run has **not** passed. Relevant dependencies (Inspect AI / LangGraph / Strands / LangChain) are unavailable in the current interpreter.

### Next steps

Continue `test_readings.py` from line 874, `test_export.py` from line 207, and `test_judge.py` from line 209. Prioritise completing shorter remaining test modules, resolving import contracts against original screenshots, then native offline pytest/CI without paid model calls.

**Do not represent these drafts as complete original tests or merge them into master until fidelity and execution are established.**
