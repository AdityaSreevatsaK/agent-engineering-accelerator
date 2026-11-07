"""Run recorded CLI subprocess assertions with a focused, offline test fixture.

The historical 1,133-line video candidate is never modified. A temporary
test-only copy filters its original RUNS fixture to four safe scenarios so
one CI job needn't launch all eighteen original subprocess variations.

This is behaviour verification of original test functions, not full historical
fixture execution or original-video byte-fidelity certification.
"""
from __future__ import annotations

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
SCENARIOS = ("good", "capture", "failing", "failing_capture")
# Each selected test below comes from the original 1,133-line video candidate.
# Historical runs fixture is filtered to four scenarios ONLY, and does not
# refer to the original missing capture/broken fixture paths.
NODES = (
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
)
FIXTURE_ANCHOR = '\n@pytest.fixture(scope="module")\ndef runs(tmp_path_factory):'


def stage_source() -> str:
    # Python normalises CRLF when reading text. Hash Git-normalised UTF-8 on
    # every OS; never change the saved recovered source to match a checksum.
    source = SOURCE.read_text(encoding="utf-8")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Original-video CLI draft has changed: require source evidence review")
    if len(source.splitlines()) != 1133:
        raise RuntimeError("Unexpected historical draft physical-line count")
    tree = ast.parse(source, filename=str(SOURCE), feature_version=(3, 11))
    tests = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    }
    seen = [name.partition("[")[0] for name in NODES]
    if len(seen) != len(set(seen)):
        raise RuntimeError("Duplicate replay test selection")
    if set(seen) - tests.keys():
        raise RuntimeError("Selected original test no longer exists")

    runs_assignment = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "RUNS" for target in node.targets)
    ]
    if len(runs_assignment) != 1 or not isinstance(runs_assignment[0].value, ast.Dict):
        raise RuntimeError("Original RUNS scenario map structure changed")
    keys = {k.value for k in runs_assignment[0].value.keys if isinstance(k, ast.Constant)}
    if not set(SCENARIOS) <= keys:
        raise RuntimeError("Expected offline original scenarios absent")

    for name in seen:
        fn = tests[name]
        params = {a.arg for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
        if "runs" not in params or params & {"check_runs", "price_runs"}:
            raise RuntimeError(f"Replay test fixture dependency changed: {name}")

    if source.count(FIXTURE_ANCHOR) != 1:
        raise RuntimeError("Historical runs fixture anchor changed")
    selection = '\n# REPLAY-ONLY: restrict costly test fixture without modifying historic test bodies\n'
    selection += "RUNS = {name: RUNS[name] for name in " + repr(SCENARIOS) + "}\n"
    staged = source.replace(FIXTURE_ANCHOR, selection + FIXTURE_ANCHOR, 1)
    ast.parse(staged, filename=str(STAGED), feature_version=(3, 11))
    return staged


def main() -> int:
    content = stage_source()
    if STAGED.exists() or STAGED.is_symlink():
        raise RuntimeError(f"Refusing to replace existing test file: {STAGED}")
    STAGED.write_text(content, encoding="utf-8", newline="\n")
    try:
        path = STAGED.relative_to(ROOT).as_posix()
        selected = [f"{path}::{node}" for node in NODES]
        # Original tests are marked slow by the source-recovered conftest.py;
        # include them rather than silently deselecting with default pytest -m.
        command = [sys.executable, "-m", "pytest", "-q", "-m", "slow", *selected]
        environment = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "PYTHONUTF8": "1"}
        print(
            f"Running {len(NODES)} original-source CLI functions with "
            f"only {len(SCENARIOS)} deterministic offline subprocess scenarios",
            flush=True,
        )
        return subprocess.call(command, cwd=ROOT, env=environment)
    finally:
        STAGED.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
