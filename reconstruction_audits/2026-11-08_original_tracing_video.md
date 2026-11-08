# AEA original OpenTelemetry tracing tests: complete video reconstruction

Date: 8 November 2026. Source: uploaded `test-unit-test_tracing.py.webm`.
Target branch: reconstruction/wip-checkpoint-2026-10-30; `master` unchanged.

## Source evidence

Full original Notepad++ editor recording shows source lines 1 through 88 plus blank editor line 89, Windows CRLF, UTF-8, and status bar **length: 3,010; lines: 89**.

Recovered `tests/unit/test_tracing.py`: 88 physical LF-terminated lines, **89 displayed lines and exactly 3,010 CRLF-equivalent characters**. SHA-256 normalised candidate `57908bd277e07bfea782137439d12005d155e30412c5157e57f6e43af05714c1`. Python 3.11 AST validates the five original function names.

## Original test cases

- JsonlSpanExporter serialises named OpenTelemetry spans to JSONL.
- When enabled, error redaction strips exception messages and tracebacks and replaces status descriptions with `[REDACTED]`, preserving exception type and ERROR status.
- When redaction is disabled, original status and error messages remain visible.
- Ordinary spans without errors keep empty event lists and UNSET status unchanged.
- Multiple exporter instances append records to the same JSONL file in order.

All test bodies and exporter helper code are video-transcribed and replayed on four matrix combinations (Windows/Linux x Python 3.11/3.12) with real AEA and OpenTelemetry dependencies, no paid models or external credentials.

Recorded editor-count fidelity supports the source candidate; it does not certify original-byte identity without original source hashes. This restores one original historical source path after passing CI; baseline should increase from 77/117 to 78/117, or from 80/117 to 81/117 if the separate Orders PR #56 is merged first.
