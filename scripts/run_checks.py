"""Run AEA's offline unit-test matrix without cloud credentials."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from make_test_log import make_capture

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tests" / "fixtures" / "calculator_capture_content.json"

TEST_MODULES = (
    "test_adapters.py",
    "test_baseline_replacement_safety.py",
    "test_baseline_transaction.py",
    "test_build_task.py",
    "test_calculator_dataset.py",
    "test_calculator_rules.py",
    "test_orders_contract.py",
    "test_calculator_log_sample.py",
    "test_cli_controls.py",
    "test_cli_pairwise.py",
    "test_compare.py",
    "test_compare_statistics.py",
    "test_config.py",
    "test_dataset.py",
    "test_export.py",
    "test_expense.py",
    "test_helpdesk.py",
    "test_init.py",
    "test_init_symlink_safety.py",
    "test_judge.py",
    "test_judge_double.py",
    "test_judge_double_pairwise.py",
    "test_judge_interrupt.py",
    "test_judge_pairwise.py",
    "test_judge_pairwise_prefix.py",
    "test_langgraph_adapter.py",
    "test_policy_rag.py",
    "test_readings.py",
    "test_readings_pairwise.py",
    "test_report.py",
    "test_report_pairwise.py",
    "test_run_metrics.py",
    "test_run_task.py",
    "test_scorers.py",
    "test_scrub.py",
    "test_stats_compare.py",
    "test_stats.py",
    "test_tool_metrics.py",
    "test_tokens.py",
    "test_trace_summary.py",
    "test_tracing.py",
    "test_trace_export_privacy.py",
    "test_triage.py",
)

# Only the integrated CLI contract suite depends on a separate, fixed baseline
# archive that is not distributed with this project. All other test modules must
# be explicitly listed for offline execution.
EXCLUDED_MODULES = {
    "test_cli.py": "requires a baseline archive that is not distributed",
}

# These particular assertions require a second, immutable full-run sample log.
# Avoid synthesising test evidence to satisfy fixed snapshot expectations.
DEFERRED_CASES = (
    "tests/unit/test_compare.py::test_capture_fixture_loads_as_ten_successful_cases",
    "tests/unit/test_compare.py::test_broken_fixture_has_the_two_specified_failures_and_explanations",
    "tests/unit/test_compare.py::test_broken_fixture_regresses_against_capture_with_default_thresholds",
    "tests/unit/test_compare.py::test_load_results_marks_sample_without_scores_as_failed",
    "tests/unit/test_compare.py::test_load_results_uses_sample_error_message_when_agent_error_is_absent",
    "tests/unit/test_compare.py::test_load_results_judge_is_empty_for_an_unjudged_run",
    "tests/unit/test_compare.py::test_load_results_reads_capture_content_from_fixture_metadata",
    "tests/unit/test_compare.py::test_cli_compare_exit_code_ignores_capture_warning",
    "tests/unit/test_compare.py::test_logs_from_before_tool_call_counts_load_with_none",
    "tests/unit/test_compare_statistics.py::test_demo_statistics_match_hand_derived_values",
    "tests/unit/test_compare_statistics.py::test_statistics_block_is_the_last_section_before_the_glossary_and_appears_once",
)

def main() -> int:
    unit_dir = ROOT / "tests" / "unit"
    listed = set(TEST_MODULES) | set(EXCLUDED_MODULES)
    actual = {path.name for path in unit_dir.glob("test_*.py")}
    if actual != listed:
        raise RuntimeError(
            f"Offline test inventory differs: unlisted={sorted(actual - listed)} "
            f"missing={sorted(listed - actual)}"
        )
    for name, reason in EXCLUDED_MODULES.items():
        print(f"EXCLUDED MODULE: {name}: {reason}", flush=True)
    print(f"DEFERRED CASE GROUPS: {len(DEFERRED_CASES)}", flush=True)
    if CAPTURE.exists() or CAPTURE.is_symlink():
        raise FileExistsError(f"Refusing to overwrite local data: {CAPTURE}")
    with TemporaryDirectory(prefix="aea-unit-fixture-") as temp:
        target = Path(temp) / "capture.json"
        make_capture(target)
        CAPTURE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, CAPTURE)
        expected_digest = sha256(CAPTURE.read_bytes()).hexdigest()
        try:
            command = [
                sys.executable, "-m", "pytest", "-q", "-m", "not slow",
                *(arg for case in DEFERRED_CASES for arg in ("--deselect", case)),
                *(f"tests/unit/{name}" for name in TEST_MODULES),
            ]
            return subprocess.call(command, cwd=ROOT)
        finally:
            if CAPTURE.is_symlink() or not CAPTURE.is_file():
                raise RuntimeError("Temporary unit-test fixture changed type; refusing deletion")
            if sha256(CAPTURE.read_bytes()).hexdigest() != expected_digest:
                raise RuntimeError("Temporary unit-test fixture changed; refusing deletion")
            CAPTURE.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
