# Part 38: calculator visual reconstruction, CI evidence and overlap handling

**Date:** 6 November 2026  
**Review branch:** `reconstruction/wip-checkpoint-2026-10-30`  
**Pull request:** [#25](https://github.com/AdityaSreevatsaK/agent-engineering-accelerator/pull/25)  
**Merged SHA:** `7d098780feb5101a43857eda88c59e26bfaa0d3b`  
**Verified PR-head SHA:** `34c277ac86e3667a16d0aa66dec6cffd1dc090de`

## Original calculator sources added

- `examples/calculator/agent.py` was reconstructed from the screen recording and committed with 101 physical Python lines. The recorded Notepad++ character count was **4,070** with Windows CRLF; the recovered text is **3,969 LF characters**, exactly **4,070 CRLF-equivalent characters**. It defines the calculator tool, RuleBasedModel, FlakyModel and three agent factory functions. Reconstructed-source SHA256: `0ba3c6c135c38197765083b2293d2e4df84d3e5b4384fca3675a7fd898e16d76`.
- `examples/calculator/dataset.jsonl` was transcribed from the screenshot. It has **10 valid single-line JSON records**: add, subtract, multiply, divide, negative_operand, decimal_operand, divide_by_zero, no_tool_for_chat, json_output, subtract_large. Reconstructed-source SHA256: `9e2fee82d278bdf408cc890b644a2712752ca639f8c8e85a327d19e53ed5ca0c`.
- `reconstruction_tools/verify_calculator_video_sources.py` statically checks the recovered source/video constraints. `tests/unit/test_calculator_recovered_dataset.py` exercises the actual AEA dataset reader and recorded case expectations.

## Image overlap policy

The user clarified that each successive screenshot has **two overlapping lines** with the preceding screenshot. These are **continuity anchors**, not additional code lines. All future screenshot transcriptions must:
1. Match overlapping source lines by displayed editor line numbers and text.
2. Include the shared two lines **exactly once** at the corresponding positions.
3. Flag differing overlapping text for visual re-review rather than guessing or concatenating duplicates.
4. Validate sequential line numbering, file syntax and any final editor line/character count evidence when available.

Line overlap must never be mistaken for added source code. Where images are only visual evidence, character-level historical fidelity remains provisional until independently checked.

## CI correction

Initial build-task CI exposed `ModuleNotFoundError: No module named 'strands'`: previous synthetic calculator stub had never imported the actual Strands dependency. The workflow now installs `strands-agents` for metadata tests and adds a temporary, **non-executable** CI import shim at `examples/calculator/rules.py` because that original module is still missing.

The shim deliberately raises on all rule operations, is generated only within the CI working tree and is not committed or represented as historical source. It cannot validate actual calculator execution. The integrated workflow uses the full native dependency installation and the same disposable import shim. Both workflows now verify the recovered original agent/dataset files instead of generating synthetic agent/dataset placeholders.

## Final CI results

The final PR-head GitHub Actions checks completed with **all 10 workflows successful, 37/37 jobs green**, across Windows and Ubuntu on Python 3.11 and 3.12. All four integrated offline test jobs reported **1,189 passed, 60 deselected, 69 warnings per environment**. The calculator build-task gate reported **46 passed** in the Ubuntu 3.11 job; its other three OS/Python jobs also passed.

The 60 deselected parameter-expanded cases remain 58 original captured-log fixture cases and two triage/expense configuration cases. They were **not** re-enabled by adding the source calculator agent and dataset. Existing CI synthetic capture logs remain explicitly temporary and must not be mistaken for originals.

## Outstanding historical recovery

- `examples/calculator/rules.py` must be recovered before executing the original calculator in deterministic normal/broken/flaky modes.
- `tests/fixtures/calculator_capture_content.json` and `calculator_broken_redacted.json` remain missing. These unlock 58 parameter-expanded original fixture-dependent cases.
- Original `examples/triage/aea.toml` and `examples/expense/aea.toml` still needed to unlock two more config cases.
- Remaining original examples, baselines, security/fidelity audit and optional slow subprocess tests require separate verification.
- No full reconstructed release was merged to `master`.

**Evidence boundary:** source-reconstruction tests and end-to-end *generic offline template* checks are not proof that the restored calculator example runs without its missing original `rules.py`.
