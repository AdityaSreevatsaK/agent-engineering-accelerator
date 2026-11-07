"""Audit the 7 November 2026 original test_stats.py Notepad++ recording.

The user-provided full WebM recording shows every original source line, from
1 through the final blank editor line 225. The status bar reports 9,782
Windows CRLF characters. This transcribed candidate has exactly 224 physical
lines with a final LF, matching both recorded source dimensions.

Counts and executable tests are evidence, but do not certify that the
unavailable historical original source bytes are identical.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "unit" / "test_stats.py"
ORIGINAL_RECORDED_EDITOR_LINES = 225
ORIGINAL_RECORDED_CRLF_CHARS = 9782
TRANSCRIBED_LF_CHARS = 9558
TRANSCRIBED_SHA256 = "1e4fc1a63febefd2e1930706cd609586d73179905ed32ea8e4f7b0eb35f7e852"
EXPECTED_TEST_FUNCTIONS = (
    "test_wilson_interval_matches_published_95_percent_bounds",
    "test_wilson_interval_bounds_are_the_roots_of_the_score_equation",
    "test_wilson_interval_is_exactly_zero_below_at_none_and_exactly_one_above_at_all",
    "test_wilson_interval_with_no_runs_is_the_whole_unit_interval",
    "test_wilson_interval_narrows_with_a_smaller_z_and_collapses_to_the_rate_at_z_zero",
    "test_wilson_interval_rejects_impossible_counts",
    "test_pass_at_k_known_values",
    "test_pass_at_k_is_the_share_of_k_subsets_with_at_least_one_pass",
    "test_pass_hat_k_known_values",
    "test_pass_hat_k_is_the_share_of_k_subsets_that_all_pass",
    "test_k_estimators_reject_impossible_counts_and_k",
    "test_fisher_worse_p_known_values",
    "test_fisher_worse_p_matches_an_enumeration_of_every_placement_of_the_passes",
    "test_fisher_worse_p_never_rises_as_current_passes_fall",
    "test_fisher_worse_p_with_no_current_runs_is_one",
    "test_fisher_worse_p_rejects_impossible_counts_on_either_side",
)


def validate() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != TRANSCRIBED_SHA256:
        raise AssertionError("Original stats video candidate changed")
    if len(source) != TRANSCRIBED_LF_CHARS or not source.endswith("\n"):
        raise AssertionError("Original stats source size or EOF newline changed")
    if source.count("\n") + 1 != ORIGINAL_RECORDED_EDITOR_LINES:
        raise AssertionError("Original video displayed line count disagrees")
    editor_chars = len(source) + source.count("\n")
    if editor_chars != ORIGINAL_RECORDED_CRLF_CHARS:
        raise AssertionError("Original video CRLF editor character count disagrees")
    tree = ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))
    funcs = tuple(
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    )
    if funcs != EXPECTED_TEST_FUNCTIONS:
        raise AssertionError("The 16 recorded original test functions have changed")
    print(
        "PASS: test_stats.py, 225 recorded editor lines, 9,782 CRLF chars, "
        "16 original test functions, AST valid, video transcription SHA pinned. "
        "Historical byte equality NOT asserted."
    )


if __name__ == "__main__":
    validate()
