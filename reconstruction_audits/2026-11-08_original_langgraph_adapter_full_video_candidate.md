# Original LangGraph adapter test video reconstruction review

Date: 8 November 2026
Original historical path: `tests/unit/test_langgraph_adapter.py`
Recording: `test_langgraph_adapters.py - video(2).webm` uploaded in conversation, showing editor title `test_langgraph_adapter.py`.

## Evidence and completeness
- Original Notepad++ status bar: **1,006 lines; 39,027 characters; Windows CRLF; UTF-8**.
- Staged source candidate: **1,006 logical lines; 39,002 CRLF-equivalent characters** (difference: **25 characters shorter**).
- Candidate includes **48 top-level test definitions**, with parameterised cases, original graph factories, fixture source, tool trajectory tests, interruption and log privacy tests, input/output maps, checkpointers, case configuration, and dataset/CLI checks.
- A complete 1,006-line **candidate** is present under the original path for direct native framework verification, but **byte/text fidelity has not been certified**. The exact unmatched 25 characters are not recovered by padding or invention.
- Recoverable content is preserved as separate `reconstruction_drafts/test_langgraph_adapter_PARTIAL_lines_*` fragments to permit per-screen line comparison. Filled line-number alignment is a transcription aid, not evidence of byte identity.
- This audit is new reconstruction documentation, not historical v2.2.0 content.

## Verification policy
- The framework adapter CI workflow now executes `tests/unit/test_langgraph_adapter.py` alongside `test_adapters.py` with actual offline LangGraph/Inspect dependencies, on Windows and Linux, Python 3.11/3.12.
- The integrated offline test workflow also collects active original-path unit files. No paid model calls or credentials are required.
- Preserve original assertion intent and fixtures; only change recorded source when video evidence proves transcription errors, and document any compatibility divergences.
- Do not count a historical file path as present in the integration branch until the PR merges and CI is verified.
- Keep `master` untouched.

## Follow-up
Resolve the 25-character mismatch if screenshots or recording give enough evidence. This is nontrivial fidelity work even if tests pass. Full validation and final release signoff remain separate from historical file-presence counting.
