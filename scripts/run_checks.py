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
    "test_factory_references.py",
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
    "test_pilot_rehearsal.py",
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

# Run independent CLI parser/configuration contracts without requiring archived
# comparison logs. Other tests in the same module depend on unavailable fixed
# reference archives; they must not be represented as passing coverage.
PARTIAL_MODULE_CASES = {
    "test_cli.py": (
        "test_run_scorer_option_defaults_to_none",
        "test_run_flags_have_the_documented_defaults_in_run_and_check",
        "test_threshold_flags_have_the_documented_defaults_in_compare_and_check",
        "test_max_p_value_strictly_between_zero_and_one_is_parsed_as_a_float",
        "test_max_p_value_outside_the_open_unit_interval_is_a_usage_error",
        "test_check_update_baseline_defaults_off",
        "test_check_without_baseline_flag_is_a_usage_error",
        "test_config_fills_every_run_setting_left_off_the_command_line",
        "test_a_flag_on_the_command_line_beats_the_same_setting_in_the_config",
        "test_adapter_set_neither_by_flag_nor_config_is_strands_with_no_maps",
        "test_agent_set_neither_by_flag_nor_config_is_a_usage_error_before_running",
        "test_without_config_every_run_setting_comes_from_its_flag",
        "test_maps_without_langgraph_are_a_usage_error_whether_they_come_from_config_or_flags",
        "test_config_error_exits_two_before_the_runs_dir_exists_and_before_baseline_validation",
        "test_an_aea_toml_in_the_working_directory_is_ignored_without_config",
        "test_config_directory_is_not_added_to_the_import_path",
        "test_config_path_reaches_build_task_as_given_in_posix_form_not_resolved",
        "test_example_config_alone_supplies_a_runnable_setting_set",
        "test_commands_that_do_not_run_an_agent_have_no_config_flag",
        "test_adapter_flag_outside_strands_and_langgraph_is_still_rejected_by_the_parser",
    ),
}

# No comparison/statistics test groups remain excluded: their replacement assertions
# use independently constructed synthetic runs. Fixed-reference CLI integration tests
# are still partially selected until their fixtures can be independently reproduced.
DEFERRED_CASES: tuple[str, ...] = ()

def main() -> int:
    unit_dir = ROOT / "tests" / "unit"
    listed = set(TEST_MODULES) | set(PARTIAL_MODULE_CASES)
    actual = {path.name for path in unit_dir.glob("test_*.py")}
    if actual != listed:
        raise RuntimeError(
            f"Offline test inventory differs: unlisted={sorted(actual - listed)} "
            f"missing={sorted(listed - actual)}"
        )
    for name, selected_cases in PARTIAL_MODULE_CASES.items():
        print(
            f"PARTIALLY COVERED MODULE: {name}, {len(selected_cases)} selected test groups; "
            "fixed-reference integration cases remain deferred",
            flush=True,
        )
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
                *(
                    f"tests/unit/{module}::{case}"
                    for module, selected_cases in PARTIAL_MODULE_CASES.items()
                    for case in selected_cases
                ),
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
