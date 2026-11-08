"""Verify original test_trace_summary.py source video and all original tests.

User-supplied complete scrolling WebM, recorded on 8 November 2026.
Notepad++ status: UTF-8, Unix (LF), 257 displayed lines, 7,697 characters.
The candidate matches those exact visible editor dimensions. No claim is
made about historical byte-for-byte identity without the original source.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "unit" / "test_trace_summary.py"
RECORDED_EDITOR_LINES = 257
RECORDED_EDITOR_CHARS = 7697
NORMALIZED_SHA256 = "c979c3b39039932209b0290a3ab98ab3386852fd98941145b90a118eaef617de"
EXPECTED_TESTS = (
    "test_strands_trace_counts_chat_spans_as_model_calls_and_execute_tool_spans_as_tool_calls",
    "test_langgraph_trace_counts_llm_spans_as_model_calls_and_tool_spans_as_tool_calls",
    "test_tool_name_falls_back_to_span_name_when_no_tool_name_attribute",
    "test_equivalent_strands_and_langgraph_traces_give_equal_counts_and_tool_lists",
    "test_nested_non_model_non_tool_spans_count_as_neither",
    "test_tool_calls_follow_start_time_not_file_order",
    "test_tool_errors_count_only_error_status_on_tool_spans",
    "test_model_and_tool_times_are_sums_of_durations_and_total_is_root_duration",
    "test_epoch_is_read_from_root_and_defaults_to_one",
    "test_numeric_sample_id_is_returned_as_a_string",
    "test_traces_without_an_eval_case_root_are_ignored",
    "test_blank_lines_are_skipped",
    "test_multiple_traces_are_sorted_by_sample_id_then_epoch",
)


def validate() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != NORMALIZED_SHA256:
        raise AssertionError("The video-transcribed trace summary test source changed")
    if not text.endswith("\n") or len(text) != RECORDED_EDITOR_CHARS:
        raise AssertionError("Original recorded 7,697 LF editor characters changed")
    if text.count("\n") + 1 != RECORDED_EDITOR_LINES:
        raise AssertionError("Original recorded 257 displayed editor lines changed")
    tree = ast.parse(text, filename=str(SOURCE), feature_version=(3, 11))
    functions = tuple(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    if functions != EXPECTED_TESTS:
        raise AssertionError(f"Original recorded trace summary test inventory changed: {functions}")
    print(
        "PASS: original trace summary video candidate, 257 editor lines, "
        "7,697 LF chars, 13 tests, SHA-256 pinned, AST valid. "
        "Historical original-byte identity not asserted."
    )


if __name__ == "__main__":
    validate()
