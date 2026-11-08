"""Replay original video-derived token tests without unavailable historical JSON.

The user's original calculator_capture_content.json fixture has not been
recoverable from its recorded video. Do NOT fabricate it or represent a
synthetic fixture as the original. Seven historical tests depending on it
are reported blocked; the other twenty original functions are executed
with their unmodified source and original parametrisations.

The three CLI price tests are offline, using local double in original code.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.verify_tokens_original_video import ORIGINAL_TEST_NAMES, check

ROOT = Path(__file__).resolve().parents[1]
FILE = "tests/unit/test_tokens.py"
CAPTURE_DEPENDENT = {
    "test_case_tokens_are_the_mean_over_epochs_rounded_to_int",
    "test_epochs_that_did_not_report_usage_are_skipped_not_counted_as_zero",
    "test_a_missing_key_skips_that_epoch_for_that_field_only",
    "test_case_tokens_are_none_when_no_epoch_reported",
    "test_run_tokens_sum_over_cases_that_reported",
    "test_run_tokens_are_none_when_no_case_reported",
    "test_report_with_prices_prints_estimated_cost",
}
CLI_TESTS = {
    "test_run_with_bad_price_exits_two_with_error_and_creates_no_run_dir",
    "test_run_with_prices_and_reported_usage_writes_estimated_cost_to_report",
    "test_report_with_bad_price_exits_two_with_error",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=["fast", "cli", "all"], default="all")
    mode = parser.parse_args().group
    check()
    if len(CAPTURE_DEPENDENT) != 7 or len(CLI_TESTS) != 3 or len(ORIGINAL_TEST_NAMES) != 27:
        raise AssertionError("Historical evidence test counts changed")
    if not (CAPTURE_DEPENDENT | CLI_TESTS) <= set(ORIGINAL_TEST_NAMES):
        raise AssertionError("Original video test inventory missing expected cases")
    eligible = [name for name in ORIGINAL_TEST_NAMES if name not in CAPTURE_DEPENDENT]
    if mode == "fast":
        selected = [name for name in eligible if name not in CLI_TESTS]
    elif mode == "cli":
        selected = [name for name in eligible if name in CLI_TESTS]
    else:
        selected = eligible
    expected = 17 if mode == "fast" else 3 if mode == "cli" else 20
    if len(selected) != expected:
        raise AssertionError("Unexpected replay test selection")
    print(
        f"Replay {len(selected)} recorded original function bodies ({mode}); "
        "seven fixture-dependent functions BLOCKED because original JSON unavailable, "
        "not counted as passing.",
        flush=True,
    )
    return subprocess.call(
        [
            sys.executable, "-m", "pytest", "-q", "-m", "not slow", "--maxfail=1",
            *[f"{FILE}::{name}" for name in selected],
        ],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
