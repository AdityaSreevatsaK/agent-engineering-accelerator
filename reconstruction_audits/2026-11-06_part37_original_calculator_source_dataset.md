# Part 37: calculator agent and dataset visual reconstruction

**Source:** New user-uploaded 6 November 2026 WebM footage of `examples/calculator/agent.py` and one original Notepad++ screenshot of `examples/calculator/dataset.jsonl`.

**Integration target:** `reconstruction/wip-checkpoint-2026-10-30`. No full-project promotion to `master` until historical fidelity, fixtures and runtime behaviour are verified.

## Evidence and provenance

- `examples/calculator/agent.py` was transcribed line-by-line from the original user recording, not fabricated from a model-based example. It contains `RuleBasedModel`, `FlakyModel`, a Strands calculator tool and the original three agent factory functions.
- The screen recorder shows Notepad++ **102 editor lines** (101 physical source lines followed by the empty last editor line) and **length: 4,070** under Windows CRLF. The stored GitHub candidate has 101 physical LF lines, **3,969 LF characters**, and exactly **4,070** reconstructed CRLF characters. This is unusually strong corroborating evidence of transcription completeness, but still does not independently certify every byte of the historical original.
- Candidate agent source UTF-8 SHA256: `0ba3c6c135c38197765083b2293d2e4df84d3e5b4384fca3675a7fd898e16d76` (generated from our transcription, NOT a historical original checksum).
- `examples/calculator/dataset.jsonl` was transcribed from the supplied full-screen screenshot as **ten individual JSONL records**, in the same order: add, subtract, multiply, divide, negative_operand, decimal_operand, divide_by_zero, no_tool_for_chat, json_output and subtract_large.
- The dataset covers exact calculator tool arguments, divide-by-zero text, no-tool expectation, JSON schema and subset tool-call matching. Candidate dataset UTF-8 SHA256: `9e2fee82d278bdf408cc890b644a2712752ca639f8c8e85a327d19e53ed5ca0c` (candidate, not original checksum).
- `reconstruction_tools/verify_calculator_video_sources.py` is a dependency-free verification step that parses the agent as Python 3.11, checks all factory/model names, validates imported rules identifiers and checks the ten JSONL cases against screenshot structure. No cloud calls, network access or secrets.
- `tests/unit/test_calculator_recovered_dataset.py` additionally tests the restored data using AEA's actual Pydantic loader, expected tool calls, schema and output fields.

## CI boundary and safe handling

The original `examples/calculator/agent.py` and `dataset.jsonl` have replaced the temporary source stand-ins in the review branch. Both build-task and integrated test CI workflows now run the **source verifier instead of generating synthetic source files**. The legacy synthetic source generator remains guarded against overwriting any existing originals and is no longer invoked by those workflows.

**Important:** The original `examples/calculator/rules.py` file is missing, so constructing/running the real original Strands calculator agent cannot yet be verified. The CI still generates a disposable **synthetic Inspect capture log** because the original `tests/fixtures/calculator_capture_content.json` is missing. The original `calculator_broken_redacted.json`, original triage/expense example configs and other historical assets are also missing. No generated log is committed or labelled as original.

The same **60 parameter-expanded deferred tests** remain unverified: 58 historical calculator-log fixture cases and 2 missing-example-config cases. Restoring the agent and JSONL does not justify enabling those assertions without the recorded captured logs.

## Follow-up

1. Obtain the original `examples/calculator/rules.py`, and run the fully recovered offline Strands calculator (normal, broken and flaky modes).
2. Obtain original `tests/fixtures/calculator_capture_content.json` and `calculator_broken_redacted.json`. Review contents for sensitive data before committing.
3. Restore original triage and expense TOML configurations.
4. Run 60 deferred cases and separate slow CLI/subprocess suite, then finish the full original-source inventory and final historical fidelity audit.

**This audit is a new reconstruction document, not a historical AEA file.**
