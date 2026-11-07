"""Replay recorded CLI subprocess tests, in bounded, offline scenario groups.

All selected test function bodies come unchanged from the provisional original
1,133-line video draft. Each pytest invocation runs only the named scenarios,
so expensive original RUNS fixture subprocesses are not started needlessly.
The draft itself is never modified, copied into Git, or claimed byte-perfect.

No historical original JSON fixtures, provider credentials or paid model calls
are required. Existing fixture/config-dependent omissions remain explicit.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reconstruction_drafts" / "test_cli_FULL_VIDEO_CANDIDATE.py"
STAGED = ROOT / "tests" / "unit" / "test_cli_original_slow_replay_TEMP.py"
SOURCE_SHA256 = "3483b4c44b31224179df78a5778ee36fe45e305c9ebb6aa68bfed21d8038c58f"
FIXTURE_ANCHOR = '\n@pytest.fixture(scope="module")\ndef runs(tmp_path_factory):'

# The original full RUNS fixture contains 18 subprocess scenarios. Run it in
# three bounded batches, preserving all source test bodies and helper functions.
# Each suite is a mapping of its only required scenarios to exact original
# pytest node IDs. The original suite's 8-case BAD_RUNS parametrisation remains
# intact: all eight cases are included in the 'errors' scenario set.
SUITES = {
    "core": {
        "scenarios": ("good", "capture", "failing", "failing_capture"),
        "nodes": (
            "test_run_good_agent_exits_zero_and_first_line_is_run_dir_status_and_tally",
            "test_run_prints_one_line_per_case_between_status_and_report_lines",
            "test_run_last_line_is_report_path_of_an_existing_report",
            "test_run_with_failures_lists_failing_cases_first_with_redacted_reasons",
            "test_run_case_order_matches_report",
            "test_run_with_capture_content_shows_values_with_pipe_unescaped",
            "test_run_with_a_failed_case_and_no_capture_content_prints_the_hint_once_on_stderr_only[failed-cases]",
            "test_run_prints_no_hint_when_every_case_passes_or_values_are_captured",
            "test_run_without_capture_writes_no_other_log_under_runs_dir",
            "test_run_dir_has_one_log_traces_and_report_with_trace_summary",
            "test_run_without_capture_content_keeps_input_out_of_log_traces_and_report",
            "test_run_with_capture_content_keeps_input_in_log",
            "test_report_of_run_dir_with_traces_includes_trace_summary",
        ),
    },
    "errors": {
        "scenarios": (
            "no_colon", "unknown_module", "unknown_function", "missing_dataset",
            "epochs_0", "max_samples_0", "scorer_no_colon",
            "scorer_missing_attribute", "eval_error",
        ),
        "nodes": (
            "test_bad_run_exits_two_with_error_and_leaves_no_run_dir",
            "test_run_that_completes_with_eval_status_error_exits_two",
        ),
    },
    "scorers": {
        "scenarios": (
            "failing_epochs", "half_passing",
            "custom_scorer", "custom_scorer_capture", "two_scorers",
        ),
        "nodes": (
            "test_run_with_epochs_shows_pass_tally_per_case",
            "test_run_with_a_failed_case_and_no_capture_content_prints_the_hint_once_on_stderr_only[partial-pass-over-epochs]",
            "test_custom_scorer_failing_fails_cases_whose_case_checks_pass_and_is_named",
            "test_custom_scorer_explanation_is_not_stored_without_capture_content",
            "test_custom_scorer_explanation_is_shown_with_capture_content",
            "test_repeated_scorers_are_all_applied_in_the_given_order",
        ),
    },
}


def original_source() -> tuple[str, ast.Module]:
    # CRLF Windows checkouts are normalised when reading text. The expected
    # checksum is for the original Git LF content, not checkout bytes.
    source = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Original-video CLI draft changed: reconcile source evidence")
    if len(source.splitlines()) != 1133:
        raise RuntimeError("Unexpected physical line count for original CLI draft")
    tree = ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))
    return source, tree


def stage_source(source: str, tree: ast.Module, suite: str) -> str:
    spec = SUITES[suite]
    scenarios, nodes = spec["scenarios"], spec["nodes"]
    assert isinstance(scenarios, tuple) and isinstance(nodes, tuple)
    if len(scenarios) != len(set(scenarios)) or len(nodes) != len(set(nodes)):
        raise RuntimeError(f"Duplicate scenario or test in {suite} replay")

    original_tests = {
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    }
    original_scenarios = [
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "RUNS" for target in n.targets)
    ]
    if len(original_scenarios) != 1 or not isinstance(original_scenarios[0].value, ast.Dict):
        raise RuntimeError("Recorded CLI RUNS fixture structure changed")
    keys = {
        key.value for key in original_scenarios[0].value.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    if not set(scenarios) <= keys:
        raise RuntimeError(f"Recorded CLI scenarios missing from {suite} replay")

    for node in nodes:
        name = node.partition("[")[0]
        if name not in original_tests:
            raise RuntimeError(f"Recorded CLI test absent: {node}")
        fn = original_tests[name]
        arguments = {a.arg for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
        if "runs" not in arguments or arguments & {"check_runs", "price_runs"}:
            raise RuntimeError(f"Recorded CLI test fixture contract changed: {node}")
    if source.count(FIXTURE_ANCHOR) != 1:
        raise RuntimeError("Original runs fixture source anchor changed")

    selection = "\n# REPLAY-ONLY: restrict source RUNS data, never historical test function bodies\n"
    selection += "RUNS = {name: RUNS[name] for name in " + repr(scenarios) + "}\n"
    staged = source.replace(FIXTURE_ANCHOR, selection + FIXTURE_ANCHOR, 1)
    ast.parse(staged, filename=str(STAGED), feature_version=(3, 11))
    return staged


def run_suite(source: str, tree: ast.Module, suite: str) -> int:
    staged = stage_source(source, tree, suite)
    if STAGED.exists() or STAGED.is_symlink():
        raise RuntimeError(f"Refusing to overwrite existing test file: {STAGED}")
    STAGED.write_text(staged, encoding="utf-8", newline="\n")
    try:
        test_file = STAGED.relative_to(ROOT).as_posix()
        nodes = [f"{test_file}::{name}" for name in SUITES[suite]["nodes"]]
        # Historical tests use the original conftest.py subprocess marker.
        argv = [sys.executable, "-m", "pytest", "-q", "-m", "slow", *nodes]
        env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"}
        print(
            f"Replaying {suite}: {len(nodes)} historical CLI test functions "
            f"with {len(SUITES[suite]['scenarios'])} bounded offline subprocess scenarios",
            flush=True,
        )
        return subprocess.call(argv, cwd=ROOT, env=env)
    finally:
        STAGED.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=(*SUITES, "all"), default="all",
        help="Run one recorded original-source subset, or all subsets in order",
    )
    args = parser.parse_args()
    source, tree = original_source()
    selected = tuple(SUITES) if args.suite == "all" else (args.suite,)
    failed = []
    for suite in selected:
        if run_suite(source, tree, suite) != 0:
            failed.append(suite)
    if failed:
        print(f"Original-source offline replay failed in: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"All {len(selected)} original-source CLI subprocess replay suites passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
