"""Audit original 8 Nov 2026 test_tracing.py Notepad++ recording.

Recording showed full file, editor length 3,010 Windows CRLF
characters and 89 displayed lines. Reconstructed original test source
matches both editor dimensions, with 5 original unit test functions.
This is not original-byte historical identity certification.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "unit" / "test_tracing.py"
RECORDED_LINES = 89
RECORDED_CRLF_CHARACTERS = 3010
SHA256_LF = "57908bd277e07bfea782137439d12005d155e30412c5157e57f6e43af05714c1"
EXPECTED_TESTS = (
    "test_jsonl_span_exporter_writes_json_lines_with_span_names",
    "test_jsonl_span_exporter_redacts_exception_and_status_messages",
    "test_jsonl_span_exporter_keeps_error_messages_when_redaction_is_disabled",
    "test_jsonl_span_exporter_leaves_spans_without_errors_unchanged",
    "test_jsonl_span_exporter_appends_spans_from_multiple_instances",
)


def validate() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SHA256_LF:
        raise AssertionError("Tracing video candidate changed")
    if not source.endswith("\n") or source.count("\n") + 1 != RECORDED_LINES:
        raise AssertionError("Original editor line count changed")
    editor_chars = len(source) + source.count("\n")
    if editor_chars != RECORDED_CRLF_CHARACTERS:
        raise AssertionError("Original Windows CRLF editor character count changed")
    tree = ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))
    tests = tuple(
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    )
    if tests != EXPECTED_TESTS:
        raise AssertionError("Original five tracing test functions changed")
    print(
        "PASS: original tracing source recording; 89 editor lines, 3,010 CRLF "
        "characters, 5 tests, SHA pinned and AST valid. Original-byte identity not asserted."
    )


if __name__ == "__main__":
    validate()
