# AEA helpdesk original-source reconstruction (Part 57)

Date: 7 November 2026.
Integration: reconstruction/wip-checkpoint-2026-10-30; no changes to master.

## New original evidence recovered

| File | Evidence | Original measurements | Candidate measurements | Caveat |
| --- | --- | --- | --- | --- |
| examples/helpdesk/rules.py | user-uploaded complete scrolling WebM | 225 displayed lines, 9,963 Windows CRLF characters | 225 lines, 9,965 CRLF-equivalent chars | 2 extra candidate chars remain unresolved |
| examples/helpdesk/agent.py | user-uploaded complete scrolling WebM | 225 displayed lines, 9,818 Unix LF characters | 225 lines, 9,818 LF chars | matching editor counts, not byte certification |
| examples/helpdesk/dataset.jsonl | 2 screenshot views covering all records | 10 JSONL entries, blank line 11 | 10 records, blank line 11 | screenshot-derived candidate |
| examples/helpdesk/golden.jsonl | 1 screenshot of full file | 6 JSONL entries, blank line 7 | 6 records, blank line 7 | screenshot-derived candidate |

The screenshot records are in the original order, include all visible required/forbidden tool checks, expected tool arguments, admin approval interruption expectations, references, human labels and notes. No original files were previously committed at these paths.

## What helpdesk illustrates

- LangGraph multi-agent supervisor with actions and diagnostics worker graphs, tool-call handoffs and offline deterministic simulated chat model.
- Tool-level checks for device status, password reset, absent user/device, requests unrelated to IT, tool-order and maximum call constraints.
- Two admin access requests pass only when the actions worker interrupts at an approval gate before any grant_admin_access call.
- build_ungated_agent deliberately removes that gate to demonstrate detecting a security-sensitive regression.
- Optional lazy import of AWS Bedrock ChatBedrockConverse in build_live_agent; CI does not instantiate it or make remote LLM calls.

## Validation

- Standard-library video/screenshot verification script checks SHA-256 hashes, editor dimensions, Python 3.11 AST and every dataset/golden JSON record.
- New supplementary test runs original 10-case dataset through actual AEA CLI and native LangGraph in gated and ungated modes and requires exactly two expected approval failures in ungated variant, with six golden output texts matching.
- Four CI combinations: Windows/Linux and Python 3.11/3.12, no credentials or paid models.
- This supplementary check is NOT the historical tests/unit/test_helpdesk.py. That original file remains pending a user recording.

## Fidelity and status

The 2-character discrepancy in rules.py has NOT been hidden or corrected without source evidence. Matching line/character counts for agent.py and valid JSON for screenshots do not prove exact historical bytes.

Four historical paths restored from available evidence, with expected presence increased from 66/117 to 70/117 AFTER successful PR merge. No remaining original baseline/fixture files claimed. Master remains untouched.
