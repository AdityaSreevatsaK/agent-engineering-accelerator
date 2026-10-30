# AEA calculator fixture evidence — 30 October 2026

Status: **Partial visual evidence only; original JSON bytes not reconstructed or committed.**

## Received
- Screenshot from Notepad++ of the trailing section of `calculator_broken_redacted.json`.
- Video supplied as `test_capture_content.py - video.webm`, but Notepad++ clearly shows the file is **`calculator_capture_content.json`**, not a Python test.
- The capture-content JSON is one physical line; Notepad++ displays **57,844 characters** and Windows CRLF. Video shows the beginning and ending regions.
- The original fixture test files refer to both JSON paths under `tests/fixtures/`.

## Visible structural facts
- `calculator_capture_content.json` contains 10 calculator case IDs shown at the end: `add`, `subtract`, `multiply`, `divide`, `negative_operand`, `decimal_operand`, `divide_by_zero`, `no_tool_for_chat`, `json_output`, `subtract_large`.
- The capture-content fixture's displayed reduction entries show values of `1.0` for these cases.
- The broken-redacted screenshot shows failure entries for `subtract` and `subtract_large`, with the latter showing `value: 0.0`, failing expected-output and tool-call checks. Other visible reductions show passing values.
- These observations are consistent with `tests/unit/test_compare.py`, which expects ten successful cases for the capture fixture and two failing cases in the broken fixture.

## Boundary / next action
- The screenshot provides the **end**, not the complete beginning, of the broken-redacted single-line JSON.
- The recording gives visual coverage of the capture JSON, but its 57,844 characters include IDs, timestamps, event data and escaped strings that cannot be safely inferred or claimed byte-for-byte from screenshots.
- **Request the two original .json files as direct attachments** (or a .zip containing them), after redaction/security review, rather than retranscribing long single-line JSON from a video.
- Do not fabricate the missing fields, substitute generated eval logs, or assert successful fixture-dependent pytest runs until those original file bytes are supplied.
- Neither fixture is committed on this evidence alone.

`master` remains unchanged. This note records what has been observed; it is not a fidelity approval.
