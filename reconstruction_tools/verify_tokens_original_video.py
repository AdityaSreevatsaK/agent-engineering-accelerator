"""Audit original test_tokens.py user video: complete source, 8 November 2026.

Notepad++ recorded Windows CRLF, 384 displayed lines, 14,000 characters.
The reconstructed source matches those two editor dimensions exactly,
contains all 27 recorded test functions, and parses with Python 3.11.
Byte-for-byte equality to the unavailable original file is not claimed.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "unit" / "test_tokens.py"
LF_SHA256 = "09a1a21768426df21a87a5be7d821639ecf954a41459b48372f16d454a313e50"
LF_CHARS = 13617
EDITOR_LINES = 384
EDITOR_CRLF_CHARS = 14000
ORIGINAL_TEST_NAMES = (
    "test_case_tokens_are_the_mean_over_epochs_rounded_to_int",
    "test_epochs_that_did_not_report_usage_are_skipped_not_counted_as_zero",
    "test_a_missing_key_skips_that_epoch_for_that_field_only",
    "test_case_tokens_are_none_when_no_epoch_reported",
    "test_run_tokens_sum_over_cases_that_reported",
    "test_run_tokens_are_none_when_no_case_reported",
    "test_run_tokens_from_constructed_cases_ignore_cases_without_tokens",
    "test_validate_prices_accepts_both_or_neither_and_zero",
    "test_validate_prices_rejects_one_alone_negative_or_nan",
    "test_render_run_rejects_a_single_price",
    "test_case_table_has_tokens_column_between_latency_and_failure",
    "test_case_row_shows_tokens_with_thousands_separators_in_their_column",
    "test_case_row_shows_na_when_the_case_has_no_tokens",
    "test_summary_tokens_line_with_thousands_separators",
    "test_summary_tokens_line_is_na_without_tokens",
    "test_estimated_cost_line_with_both_prices_and_tokens",
    "test_estimated_cost_uses_input_and_output_prices_separately_and_rounds_to_four_decimals",
    "test_estimated_cost_with_zero_prices_is_shown_as_zero",
    "test_no_estimated_cost_without_prices",
    "test_no_estimated_cost_without_tokens_even_with_prices",
    "test_comparison_has_tokens_per_run_row",
    "test_comparison_tokens_row_is_na_for_a_side_without_tokens",
    "test_large_token_rise_is_not_a_regression",
    "test_run_with_bad_price_exits_two_with_error_and_creates_no_run_dir",
    "test_run_with_prices_and_reported_usage_writes_estimated_cost_to_report",
    "test_report_with_bad_price_exits_two_with_error",
    "test_report_with_prices_prints_estimated_cost",
)


def check() -> None:
    s = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(s.encode("utf-8")).hexdigest() != LF_SHA256:
        raise AssertionError("Video candidate source digest changed")
    if len(s) != LF_CHARS or not s.endswith("\n"):
        raise AssertionError("Video LF source size or final LF disagrees")
    if s.count("\n") + 1 != EDITOR_LINES:
        raise AssertionError("Original video displayed editor line count disagrees")
    if len(s) + s.count("\n") != EDITOR_CRLF_CHARS:
        raise AssertionError("Original Windows CRLF character count disagrees")
    t = ast.parse(s, filename=str(SOURCE), feature_version=(3, 11))
    names = tuple(
        n.name for n in t.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name.startswith("test_")
    )
    if names != ORIGINAL_TEST_NAMES:
        raise AssertionError("Original 27 top-level source test names/order changed")
    print(
        "PASS: test_tokens.py original video 384 editor lines, "
        "14,000 CRLF characters, 27 original test functions, "
        "SHA and Python AST valid. Original-byte identity not asserted."
    )


if __name__ == "__main__":
    check()
