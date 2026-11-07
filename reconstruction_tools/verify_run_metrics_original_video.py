"""Audit the 7 November 2026 original test_run_metrics.py video candidate.

The user-supplied complete scrolling Notepad++ video shows 507 displayed
source lines and a Windows CRLF character count of 20,657. The reconstructed
candidate has all 507 displayed lines, 20,651 CRLF-equivalent characters:
**six characters short**. Do NOT hide, fill or invent the missing six bytes.

The source contains all 32 video-visible original test functions. Execution
validates functional compatibility, NOT historical byte identity.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tests" / "unit" / "test_run_metrics.py"
RECORDED_EDITOR_LINES = 507
RECORDED_EDITOR_CHARS = 20657
CANDIDATE_LF_CHARS = 20145
CANDIDATE_SHA256 = "64cbe5024e9e19377ce6ce54fbc2995dbb6e5d99c4807cee8e99e87148bbee9f"
CANDIDATE_EDITOR_MINUS_RECORDED_CHARS = -6
EXPECTED_TESTS = (
    "test_percentile_is_the_observed_value_at_nearest_rank_of_the_sorted_list",
    "test_percentile_of_one_value_is_that_value_at_every_rank",
    "test_percentile_leaves_the_input_list_in_its_original_order",
    "test_percentile_rejects_an_empty_list_and_p_outside_zero_exclusive_to_100",
    "test_epoch_metrics_reads_latency_tokens_digest_and_failed_checks_from_one_sample",
    "test_epoch_metrics_keeps_only_non_bool_int_token_counts_from_a_usage_dict",
    "test_epoch_metrics_has_no_digest_unless_case_checks_recorded_a_string",
    "test_epoch_metrics_names_failed_case_checks_by_check_and_other_scorers_by_name",
    "test_estimated_cost_prices_one_pass_of_per_epoch_average_tokens_per_million",
    "test_estimated_cost_is_none_without_both_prices_and_both_token_totals",
    "test_estimated_cost_of_free_tokens_is_zero_not_missing",
    "test_no_metric_sections_for_a_run_without_epoch_data_tokens_or_prices",
    "test_latency_line_reports_nearest_rank_p50_p90_p95_and_max_over_case_epochs",
    "test_token_lines_appear_independently_of_latency_and_of_each_other",
    "test_cost_line_divides_one_pass_cost_by_cases_and_by_passing_cases",
    "test_cost_line_uses_per_epoch_average_tokens_not_the_sum_over_epochs",
    "test_cost_per_passing_case_is_not_applicable_when_no_case_passed",
    "test_cost_line_is_omitted_without_both_prices_and_both_token_totals",
    "test_cost_line_at_zero_prices_shows_zero_cost",
    "test_failures_section_is_omitted_when_no_epoch_failed",
    "test_failures_section_on_the_flaky_demo_counts_case_epochs_checks_and_cases",
    "test_failure_rows_sort_by_failing_epochs_descending_then_name",
    "test_failure_cases_column_counts_distinct_cases_not_epochs",
    "test_failure_named_twice_in_one_epoch_counts_once",
    "test_failure_check_names_escape_the_table_pipe",
    "test_consistency_section_is_omitted_when_no_case_has_two_digests",
    "test_consistency_on_the_flaky_demo_is_92_percent_with_both_subtract_cases_least_consistent",
    "test_consistency_share_is_the_most_common_digest_over_epochs_that_recorded_one",
    "test_least_consistent_orders_by_share_then_case_id",
    "test_least_consistent_lists_at_most_five_cases_and_counts_the_rest",
    "test_consistency_reports_every_case_consistent_when_every_share_is_100_percent",
    "test_run_metric_sections_come_in_performance_failures_consistency_order",
)


def validate() -> None:
    source = PATH.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != CANDIDATE_SHA256:
        raise AssertionError("Recorded run metrics video candidate changed; visual review needed")
    if len(source) != CANDIDATE_LF_CHARS or not source.endswith("\n"):
        raise AssertionError("Recovered metrics source dimensions drifted")
    if source.count("\n") + 1 != RECORDED_EDITOR_LINES:
        raise AssertionError("Recorded 507 editor lines not preserved")
    delta = len(source) + source.count("\n") - RECORDED_EDITOR_CHARS
    if delta != CANDIDATE_EDITOR_MINUS_RECORDED_CHARS:
        raise AssertionError(f"Unexpected historical editor character discrepancy {delta:+d}")
    tree = ast.parse(source, filename=str(PATH), feature_version=(3, 11))
    tests = tuple(
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    if tests != EXPECTED_TESTS:
        raise AssertionError(f"Original video functions drifted: {set(tests)^set(EXPECTED_TESTS)}")
    print(
        "RECOVERED CANDIDATE: 507/507 editor lines; 32 original test functions; "
        "CRLF-equivalent chars 20,651 vs recorded 20,657 (-6); AST valid; "
        "video candidate SHA pinned. No original-byte equality claimed."
    )


if __name__ == "__main__":
    validate()
