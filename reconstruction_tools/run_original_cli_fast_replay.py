"""Replay the original-video CLI's fixture-independent tests against real AEA code.

The original 1,133-line candidate is copied temporarily to tests/unit/ so its
historical REPO = Path(__file__).parents[2] calculation remains valid.
It is NEVER promoted as a source-fidelity-certified original file.

Only explicitly selected, non-subprocess tests run. The incomplete calculator
capture fixtures and triage/expense configurations are neither fabricated nor
referenced. Neither cloud models nor credentials are needed.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reconstruction_drafts" / "test_cli_FULL_VIDEO_CANDIDATE.py"
TEMP = ROOT / "tests" / "unit" / "test_cli_original_source_replay_TEMP.py"

# Recorded by the 6 November 2026 full-video transcription checkpoint.
EXPECTED_SHA256 = "3483b4c44b31224179df78a5778ee36fe45e305c9ebb6aa68bfed21d8038c58f"
EXPECTED_LINES = 1133

# Exact historical test functions selected for replay. Exclude any tests that
# need the module's subprocess 'runs'/'check_runs' fixtures, historical Inspect
# capture JSON files, or missing triage/expense example configurations.
REPLAY_TESTS = (
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
    "test_commands_that_do_not_run_an_agent_have_no_config_flag",
    "test_adapter_flag_outside_strands_and_langgraph_is_still_rejected_by_the_parser",
)


def validate_source() -> bytes:
    data = SOURCE.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            "Provisional original-video draft changed: "
            f"expected SHA256 {EXPECTED_SHA256}, observed {digest}. "
            "Reconcile source evidence before updating the replay."
        )
    source = data.decode("utf-8")
    if len(source.splitlines()) != EXPECTED_LINES:
        raise RuntimeError("Original-video CLI source line count changed")

    tree = ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    if len(REPLAY_TESTS) != len(set(REPLAY_TESTS)):
        raise RuntimeError("Duplicate historical CLI replay test name")
    missing = set(REPLAY_TESTS) - functions.keys()
    if missing:
        raise RuntimeError(f"Missing recorded test functions: {sorted(missing)}")

    # Fail closed if someone changes the selected functions to request the
    # original slow subprocess fixtures. Indirect fixture use still requires
    # review when the recording changes (digest above).
    blocked = {"runs", "check_runs", "price_runs"}
    for name in REPLAY_TESTS:
        fn = functions[name]
        arguments = {arg.arg for arg in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
        if arguments & blocked:
            raise RuntimeError(f"Selected test {name} requires slow subprocess fixtures")
    return data


def main() -> int:
    data = validate_source()
    if TEMP.exists() or TEMP.is_symlink():
        raise RuntimeError(f"Refusing to replace an existing file: {TEMP}")
    if not TEMP.parent.is_dir():
        raise RuntimeError(f"Tests directory missing: {TEMP.parent}")

    TEMP.write_bytes(data)
    try:
        node_ids = [f"{TEMP.relative_to(ROOT).as_posix()}::{name}" for name in REPLAY_TESTS]
        argv = [
            sys.executable, "-m", "pytest", "-q", "-m", "not slow",
            *node_ids,
        ]
        env = dict(os.environ)
        env["AWS_EC2_METADATA_DISABLED"] = "true"
        print(
            f"Replaying {len(node_ids)} original-video CLI test functions "
            "with their recorded parameterisations; no historical data substitutes.",
            flush=True,
        )
        return subprocess.call(argv, cwd=ROOT, env=env)
    finally:
        # Temporary original-path copy is an execution staging file only.
        TEMP.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
