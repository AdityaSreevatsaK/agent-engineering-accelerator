import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.scorer import CORRECT

import agent_accelerator.cli as cli_module
from agent_accelerator.cli import build_parser, main

REPO = Path(__file__).parents[2]
DATASET = REPO / "examples" / "calculator" / "dataset.jsonl"
AGENT = "examples.calculator.agent:build_agent"
FIXTURE = REPO / "tests" / "fixtures" / "calculator_capture_content.json"
BROKEN_FIXTURE = REPO / "tests" / "fixtures" / "calculator_broken_redacted.json"
TRACE_HEADER = "## Trace summary (informational)"
INPUT_TEXT = "What is 2 plus 3?"
# Replaced in the runs fixture by a dataset with one passing and two failing cases. The failing ids sort
# after the passing one, so failing-first order is not alphabetical order. "4|2" puts a pipe in the reason.
FAILING_DATASET = "<failing dataset>"
FAILING_CASES = [
    {"id": "a_pass", "input": "What is 2 plus 3?", "expected_output": "5"},
    {"id": "y_fail", "input": "What is 6 times 7?", "expected_output": "4|2"},
    {"id": "z_fail", "input": "What is 9 minus 4?", "expected_output": "6"},
]

# Every `run` goes through a subprocess: the tracer provider can only be set once per process.
# All runs start together in one module fixture, since each takes several seconds.
RUNS = {
    "good": [str(DATASET), "--agent", AGENT],
    "capture": [str(DATASET), "--agent", AGENT, "--capture-content"],
    "no_colon": [str(DATASET), "--agent", "examples.calculator.agent.build_agent"],
    "unknown_module": [str(DATASET), "--agent", "examples.calculator.no_such_module:build_agent"],
    "unknown_function": [str(DATASET), "--agent", "examples.calculator.agent:no_such_function"],
    "missing_dataset": [str(REPO / "examples" / "calculator" / "no_such_dataset.jsonl"), "--agent", AGENT],
    "epochs_0": [str(DATASET), "--agent", AGENT, "--epochs", "0"],
    "max_samples_0": [str(DATASET), "--agent", AGENT, "--max-samples", "0"],
    "eval_error": [str(DATASET), "--agent", "aea_cli_doubles:fatal_factory"],
    "failing": [FAILING_DATASET, "--agent", AGENT],
    "failing_capture": [FAILING_DATASET, "--agent", AGENT, "--capture-content"],
    "failing_epochs": [FAILING_DATASET, "--agent", AGENT, "--epochs", "2"],
    "half_passing": [str(DATASET), "--agent", AGENT, "--epochs", "2", "--scorer", "aea_cli_doubles:first_epoch_only"],
    "custom_scorer": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles:always_wrong"],
    "custom_scorer_capture": [
        *[str(DATASET), "--agent", AGENT, "--capture-content"],
        *["--scorer", "aea_cli_doubles:always_wrong"],
    ],
    "two_scorers": [
        *[str(DATASET), "--agent", AGENT],
        *["--scorer", "aea_cli_doubles:always_right", "--scorer", "aea_cli_doubles:always_wrong"],
    ],
    "scorer_no_colon": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles.always_wrong"],
    "scorer_missing_attribute": [str(DATASET), "--agent", AGENT, "--scorer", "aea_cli_doubles:no_such_scorer"],
}
HINT = "hint: failure values are redacted; rerun with --capture-content to see them (do not commit that log)"
BAD_RUNS = [
    *["no_colon", "unknown_module", "unknown_function", "missing_dataset", "epochs_0", "max_samples_0"],
    *["scorer_no_colon", "scorer_missing_attribute"],
]
CUSTOM_EXPLANATION = "custom scorer saw the output"

# A BaseException that is not an Exception escapes the adapter's per-case handling, so Inspect ends
# the eval with status "error" after the run dir and log already exist.
CLI_DOUBLES_SOURCE = """
from inspect_ai.scorer import CORRECT, INCORRECT, Score, accuracy, scorer


@scorer(metrics=[accuracy()])
def always_wrong():
    async def score(state, target):
        return Score(value=INCORRECT, explanation="custom scorer saw the output")

    return score


@scorer(metrics=[accuracy()])
def always_right():
    async def score(state, target):
        return Score(value=CORRECT, explanation="fine")

    return score


@scorer(metrics=[accuracy()])
def first_epoch_only():
    async def score(state, target):
        return Score(value=CORRECT if state.epoch == 1 else INCORRECT)

    return score


class Fatal(BaseException):
    pass


def fatal_factory():
    raise Fatal("factory aborted the eval")
"""


def doubles_env(doubles_dir):
    """Writes the CLI doubles module and returns a subprocess environment that can import it."""
    (doubles_dir / "aea_cli_doubles.py").write_text(CLI_DOUBLES_SOURCE, encoding="utf-8")
    python_path = os.pathsep.join(p for p in [str(doubles_dir), os.environ.get("PYTHONPATH")] if p)
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": python_path}


def start_cli(command, env):
    return subprocess.Popen(
        [sys.executable, "-m", "agent_accelerator.cli", *command],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    doubles_dir = tmp_path_factory.mktemp("cli_doubles")
    env = doubles_env(doubles_dir)
    failing_dataset = doubles_dir / "failing.jsonl"
    failing_dataset.write_text("".join(json.dumps(case) + "\n" for case in FAILING_CASES), encoding="utf-8")
    started = {}
    for name, run_args in RUNS.items():
        args = [str(failing_dataset) if arg == FAILING_DATASET else arg for arg in run_args]
        runs_dir = tmp_path_factory.mktemp(f"runs_{name}")
        started[name] = (start_cli(["run", *args, "--runs-dir", str(runs_dir)], env), runs_dir)
    results = {}
    for name, (process, runs_dir) in started.items():
        stdout, stderr = process.communicate(timeout=300)
        results[name] = {"code": process.returncode, "stdout": stdout, "stderr": stderr, "runs_dir": runs_dir}
    return results


def run_dir_of(result):
    [run_dir] = [p for p in result["runs_dir"].iterdir() if p.is_dir()]
    return run_dir


def run_files(result):
    run_dir = run_dir_of(result)
    [log] = run_dir.glob("*.json")
    return log, run_dir / "traces.jsonl", run_dir / "report.md"


# run


def stdout_lines(result):
    return [line for line in result["stdout"].splitlines() if line.strip()]


def test_run_good_agent_exits_zero_and_first_line_is_run_dir_status_and_tally(runs):
    result = runs["good"]
    assert result["code"] == 0, result["stderr"]

    first = stdout_lines(result)[0]
    run_dir = run_dir_of(result)
    assert run_dir.as_posix() in first or str(run_dir) in first
    assert "status=success" in first
    assert "passed=10/10" in first


def test_run_prints_one_line_per_case_between_status_and_report_lines(runs):
    lines = stdout_lines(runs["good"])

    case_lines = lines[1:-1]
    assert len(case_lines) == 10
    assert all(line.split()[1] == "pass" for line in case_lines)


def test_run_last_line_is_report_path_of_an_existing_report(runs):
    result = runs["good"]

    last = stdout_lines(result)[-1]
    assert last.startswith("report: ")
    report = Path(last.removeprefix("report: "))
    assert report.is_file()
    assert report.resolve() == (run_dir_of(result) / "report.md").resolve()


def failing_case_lines(result):
    return [line.split(maxsplit=2) for line in stdout_lines(result)[1:-1]]


def test_run_with_failures_lists_failing_cases_first_with_redacted_reasons(runs):
    result = runs["failing"]
    assert result["code"] == 0, result["stderr"]
    assert "passed=1/3" in stdout_lines(result)[0]

    lines = failing_case_lines(result)

    assert [line[:2] for line in lines] == [["y_fail", "FAIL"], ["z_fail", "FAIL"], ["a_pass", "pass"]]
    assert lines[0][2] == "expected_output: expected <redacted>, got <redacted>"
    assert lines[1][2] == "expected_output: expected <redacted>, got <redacted>"
    assert len(lines[2]) == 2


def test_run_case_order_matches_report(runs):
    result = runs["failing"]
    report = (
        (run_dir_of(result) / "report.md").read_text(encoding="utf-8").split(TRACE_HEADER)[0].split("## Tool use")[0]
    )
    report_ids = [line.split("|")[1].strip() for line in report.splitlines() if line.startswith("| ")][1:]

    assert [line[0] for line in failing_case_lines(result)] == report_ids


def test_run_with_capture_content_shows_values_with_pipe_unescaped(runs):
    result = runs["failing_capture"]
    assert result["code"] == 0, result["stderr"]

    [reason] = [line[2] for line in failing_case_lines(result) if line[0] == "y_fail"]

    assert reason.startswith("expected_output: expected '4|2', got ")
    assert r"\|" not in reason
    assert "<redacted>" not in reason


def test_run_with_epochs_shows_pass_tally_per_case(runs):
    result = runs["failing_epochs"]
    assert result["code"] == 0, result["stderr"]

    lines = [line.split(maxsplit=3) for line in stdout_lines(result)[1:-1]]

    assert [line[:3] for line in lines] == [
        ["y_fail", "FAIL", "(0/2)"],
        ["z_fail", "FAIL", "(0/2)"],
        ["a_pass", "pass", "(2/2)"],
    ]


def hint_lines(result):
    return [line for line in result["stderr"].splitlines() if line == HINT]


@pytest.mark.parametrize(
    "name, tally",
    [("failing", "passed=1/3"), ("half_passing", "passed=0/10")],
    ids=["failed-cases", "partial-pass-over-epochs"],
)
def test_run_with_a_failed_case_and_no_capture_content_prints_the_hint_once_on_stderr_only(runs, name, tally):
    # half_passing passes each case in one epoch of two, which fails the case at the default min case pass rate.
    # Witnesses: "s43 cli hint to stdout" fails both ids (stderr loses it, stdout gains it); "s43 cli hint any epoch
    # passed" fails partial-pass-over-epochs (0/10 becomes 10/10 and the hint goes).
    result = runs[name]
    assert result["code"] == 0, result["stderr"]
    assert tally in stdout_lines(result)[0]

    assert hint_lines(result) == [HINT]
    assert HINT not in result["stdout"]


@pytest.mark.parametrize("name", ["good", "capture", "failing_capture"])
def test_run_prints_no_hint_when_every_case_passes_or_values_are_captured(runs, name):
    # failing_capture has failures, so only --capture-content keeps the hint away.
    # Witnesses: "s43 cli hint failure condition dropped" and "s43 cli hint lt to le" fail good (capture still hides
    # the hint); "s43 cli hint capture condition dropped" fails failing_capture.
    result = runs[name]
    assert result["code"] == 0, result["stderr"]
    if name == "failing_capture":
        assert "passed=1/3" in stdout_lines(result)[0]

    assert HINT not in result["stderr"]
    assert HINT not in result["stdout"]


def test_run_without_capture_writes_no_other_log_under_runs_dir(runs):
    result = runs["good"]
    log, _, _ = run_files(result)

    assert list(result["runs_dir"].rglob("*.json")) == [log]


def test_run_dir_has_one_log_traces_and_report_with_trace_summary(runs):
    run_dir = run_dir_of(runs["good"])

    assert len(list(run_dir.glob("*.json"))) == 1
    assert (run_dir / "traces.jsonl").is_file()
    assert (run_dir / "report.md").is_file()
    assert TRACE_HEADER in (run_dir / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", BAD_RUNS)
def test_bad_run_exits_two_with_error_and_leaves_no_run_dir(runs, name):
    result = runs[name]

    assert result["code"] == 2
    assert result["stderr"].lstrip().startswith("error:"), result["stderr"]
    assert list(result["runs_dir"].iterdir()) == []


def test_run_that_completes_with_eval_status_error_exits_two(runs):
    result = runs["eval_error"]

    # The run itself completed: it printed its status line and wrote its log and report.
    assert "status=error" in result["stdout"], result["stderr"]
    assert (run_dir_of(result) / "report.md").is_file()
    assert result["code"] == 2


def test_run_without_capture_content_keeps_input_out_of_log_traces_and_report(runs):
    for path in run_files(runs["good"]):
        assert INPUT_TEXT not in path.read_text(encoding="utf-8"), path.name


def test_run_with_capture_content_keeps_input_in_log(runs):
    result = runs["capture"]
    assert result["code"] == 0, result["stderr"]

    log, _, _ = run_files(result)
    assert INPUT_TEXT in log.read_text(encoding="utf-8")


def test_run_scorer_option_defaults_to_none():
    args = build_parser().parse_args(["run", "dataset.jsonl", "--agent", AGENT])

    assert args.scorer == []
