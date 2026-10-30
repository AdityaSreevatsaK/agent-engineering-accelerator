# AEA source-fidelity worklist — 30 October 2026

**Branch:** `reconstruction/wip-checkpoint-2026-10-30`
**Status:** Provisional drafts only; no source-fidelity sign-off and no master merge.

This worklist continues the reconstruction after the 30 October checkpoint.
Reported editor-character discrepancies are evidence to investigate, **not**
instructions to pad or invent source. Each candidate needs the original footage
at the exact uncertain line, not just a matching total character count.

## First: re-verify earlier transcriptions

| Priority | Original path | Current status | Recorded Windows chars minus draft Windows chars | Next verification |
| --- | --- | --- | ---: | --- |
| 1 | `tests/unit/test_compare_statistics.py` | Saved draft on checkpoint | +2 | Compare original video line-by-line and check sources of length discrepancy |
| 2 | `tests/unit/test_adapters.py` | Saved draft on checkpoint | -3 | Recheck embedded `DOUBLES_SOURCE`, quoted fixtures and tool-message assertions |
| 3 | `tests/unit/test_langgraph_adapter.py` | Full Library draft only, **not on GitHub** | +10 | Recheck all 1,006 displayed lines; do not bypass earlier blocked GitHub write |
| 4 | `src/agent_accelerator/compare.py` | Saved draft on checkpoint | +32 | Recheck long branches, stats and regression decisions |
| 5 | `tests/unit/test_compare.py` | Saved draft on checkpoint | +47 | Reconcile 1,104 lines and assertions; check fixture references |
| 6 | `src/agent_accelerator/judge.py` | Saved draft on checkpoint | -14 | Recheck rubric, baseline, pairwise paths |
| 7 | `src/agent_accelerator/report.py` | Saved draft on checkpoint | approx. 20-char gap | Recheck previously clipped line 218, Markdown branches |
| 8 | `src/agent_accelerator/readings.py` | Saved draft on checkpoint | -20 | Recheck explanatory text and statistical branches |

Minus means the draft is **longer** than the recorded editor length.
Exact video evidence is needed to identify real errors; static syntax and
matching line counts alone are insufficient.

## Checked in this continuation

- The saved LangGraph 444-line partial is an exact prefix of the Library's
  full 1,005-source-line candidate (the video displays line 1,006 blank).
- The saved adapter 26-line partial is an exact prefix of its full candidate.
- Both current provisional adapter drafts contain the valid
  `from inspect_ai.model import ChatMessageTool, ModelName` import, addressing
  the specific *previously identified OCR misreading*; source fidelity is still open.
- The checkpoint's `tests/unit/test_adapters.py` matches the provisional
  Library draft in the checked initial import region.
- The comparison tests explicitly depend on missing original fixtures:
  `tests/fixtures/calculator_capture_content.json` and
  `tests/fixtures/calculator_broken_redacted.json`.
- `tests/unit/test_compare_statistics.py` comments that `tests/conftest.py`
  controls a slow-test mark for tests with a `runs` argument.

**Source limitation:** The recordings are visible by filename in the Project
Library, but this session's attempt to retrieve their raw video frames failed
with an unavailable authorised raw-file materialisation path. No claimed
character-by-character video retranscription or footage-dependent edit has
been made in this continuation.

## New source recordings to request next

1. `tests/conftest.py`
2. `tests/fixtures/calculator_capture_content.json`
3. `tests/fixtures/calculator_broken_redacted.json`
4. `tests/unit/test_judge.py`
5. `tests/unit/test_readings.py`
6. `tests/unit/test_report.py`

Then prioritise `tests/unit/test_cli.py`, `tests/unit/test_export.py`,
`tests/unit/test_judge_pairwise.py`, and
`tests/unit/test_langgraph_adapter.py` verification (not re-transcription).

## Quality gates before master

- Video/recording fidelity review and unresolved-line log
- Python 3.11 syntax and actual installed-dependency execution
- Reconstructed fixtures and original offline unit tests
- Linux and Windows CI, with actionable job logs
- No cloud charges, guessed source code or credentials in CI
- Approval to merge only after trustworthy validation
