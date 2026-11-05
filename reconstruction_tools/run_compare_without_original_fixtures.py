"""Run original comparison/statistics tests that do not require missing calculator logs.

This is an INCOMPLETE, explicitly fixture-gated verification lane.
No synthetic data are represented as historical baseline/fixture bytes.
The manifest is validated against AST dependencies so adding new fixture-bound
tests cannot silently expand the executed set.
"""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# Source-backed omissions ONLY. These tests need originals at
# tests/fixtures/calculator_capture_content.json and/or
# tests/fixtures/calculator_broken_redacted.json.
DEFERRED: dict[str, tuple[str, ...]] = {
    "tests/unit/test_compare.py": (
        "test_capture_fixture_loads_as_ten_successful_cases",
        "test_broken_fixture_has_the_two_specified_failures_and_explanations",
        "test_broken_fixture_regresses_against_capture_with_default_thresholds",
        "test_load_results_marks_sample_without_scores_as_failed",
        "test_load_results_uses_sample_error_message_when_agent_error_is_absent",
        "test_load_results_groups_epochs_into_one_case_with_run_and_pass_counts",
        "test_case_passes_when_share_of_passing_epochs_reaches_threshold",
        "test_case_error_is_the_first_non_empty_error_across_epochs",
        "test_case_error_is_none_when_no_epoch_errored",
        "test_a_judge_error_epoch_is_the_case_error_and_counts_in_the_error_rate",
        "test_an_agent_error_is_the_case_error_ahead_of_any_judge_error",
        "test_a_case_with_judge_errors_in_later_epochs_errors_once_with_the_first",
        "test_a_judge_fail_verdict_still_fails_its_epoch_and_a_judge_error_still_counts_as_an_error",
        "test_load_results_judge_is_empty_for_an_unjudged_run",
        "test_load_results_judge_holds_every_case_epoch_of_a_judged_run",
        "test_case_latency_is_the_median_across_epochs",
        "test_case_epochs_hold_one_entry_per_epoch_in_epoch_order",
        "test_case_failures_are_the_reasons_of_the_first_failing_epoch",
        "test_case_failures_are_empty_when_every_epoch_passed",
        "test_load_results_marks_mixed_epochs_flaky_and_uniform_epochs_not",
        "test_load_results_reads_capture_content_from_fixture_metadata",
        "test_load_results_capture_content_is_true_only_for_a_literal_true",
        "test_cli_compare_exit_code_ignores_capture_warning",
        "test_failing_score_without_explanation_is_reported_as_scorer_name_failed",
        "test_failing_score_with_explanation_keeps_the_explanation",
        "test_case_tool_use_aggregates_every_epoch_not_only_the_first",
        "test_logs_from_before_tool_call_counts_load_with_none",
        "test_cli_compare_max_p_value_turns_the_significance_warning_into_a_regression",
    ),
    "tests/unit/test_compare_statistics.py": (
        "test_demo_statistics_match_hand_derived_values",
        "test_statistics_block_is_the_last_section_before_the_glossary_and_appears_once",
    ),
}

DEPENDENCY_SYMBOLS = {
    "tests/unit/test_compare.py": {"FIXTURES", "write_epoch_log", "write_capture_metadata_log"},
    "tests/unit/test_compare_statistics.py": {"demo_comparison"},
}


def preflight() -> None:
    """Ensure the omission list contains exactly all known fixture-dependent tests.

    Source AST reference checking is conservative; it errs closed when a new test
    starts to use an original-fixture helper and has not been reviewed.
    """
    for relative_path, names in DEFERRED.items():
        if len(names) != len(set(names)):
            raise RuntimeError(f"Duplicate deferral in {relative_path}")
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        module = ast.parse(source, filename=relative_path, feature_version=(3, 11))
        test_defs = {
            n.name: n
            for n in module.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test_")
        }
        missing = set(names) - test_defs.keys()
        if missing:
            raise RuntimeError(f"Outdated deferrals in {relative_path}: {sorted(missing)}")
        dependency_symbols = DEPENDENCY_SYMBOLS[relative_path]
        fixture_dependent = {
            name
            for name, fn in test_defs.items()
            if any(isinstance(n, ast.Name) and n.id in dependency_symbols for n in ast.walk(fn))
        }
        unexpected = fixture_dependent - set(names)
        stale = set(names) - fixture_dependent
        if unexpected or stale:
            raise RuntimeError(
                f"Fixture classification changed in {relative_path}: "
                f"newly dependent={sorted(unexpected)}, review no-longer-dependent={sorted(stale)}"
            )
        print(
            f"{relative_path}: {len(test_defs)} top-level tests; "
            f"{len(names)} explicitly deferred original-fixture tests",
            flush=True,
        )


def main() -> int:
    preflight()
    argv = [sys.executable, "-m", "pytest", "-q", "-m", "not slow"]
    for path, tests in DEFERRED.items():
        argv.extend(f"--deselect={path}::{name}" for name in tests)
    argv.extend(DEFERRED.keys())
    print("Executing fixture-independent original comparison tests only.", flush=True)
    return subprocess.call(argv, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
