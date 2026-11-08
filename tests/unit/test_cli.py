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


def test_custom_scorer_failing_fails_cases_whose_case_checks_pass_and_is_named(runs):
    result = runs["custom_scorer"]
    assert result["code"] == 0, result["stderr"]
    log, _, _ = run_files(result)
    samples = read_eval_log(log).samples

    assert "passed=0/10" in stdout_lines(result)[0]
    assert all(s.scores["case_checks"].value == CORRECT for s in samples)
    lines = failing_case_lines(result)
    assert len(lines) == 10
    assert all(line[1:] == ["FAIL", "always_wrong failed"] for line in lines)


def test_custom_scorer_explanation_is_not_stored_without_capture_content(runs):
    for path in run_files(runs["custom_scorer"]):
        assert CUSTOM_EXPLANATION not in path.read_text(encoding="utf-8"), path.name


def test_custom_scorer_explanation_is_shown_with_capture_content(runs):
    result = runs["custom_scorer_capture"]
    assert result["code"] == 0, result["stderr"]

    assert all(line[1:] == ["FAIL", CUSTOM_EXPLANATION] for line in failing_case_lines(result))


def test_repeated_scorers_are_all_applied_in_the_given_order(runs):
    result = runs["two_scorers"]
    assert result["code"] == 0, result["stderr"]
    log, _, _ = run_files(result)

    for sample in read_eval_log(log).samples:
        assert list(sample.scores) == ["case_checks", "always_right", "always_wrong"]
    # always_right passing does not rescue the case: every scorer must pass.
    assert all(line[1:] == ["FAIL", "always_wrong failed"] for line in failing_case_lines(result))


# compare


def test_compare_without_regression_exits_zero(runs, capsys):
    run_dir = str(run_dir_of(runs["good"]))

    assert main(["compare", str(FIXTURE), run_dir]) == 0


def test_compare_with_regression_exits_one(capsys):
    assert main(["compare", str(FIXTURE), str(BROKEN_FIXTURE)]) == 1


def test_compare_output_file_matches_printed_markdown(tmp_path, capsys):
    output = tmp_path / "comparison.md"

    main(["compare", str(FIXTURE), str(BROKEN_FIXTURE), "--output", str(output)])

    printed = capsys.readouterr().out
    written = output.read_text(encoding="utf-8")
    assert written.strip()
    assert printed.rstrip("\n") == written.rstrip("\n")


@pytest.mark.parametrize("missing", ["baseline", "current"])
def test_compare_missing_path_exits_two_with_error(tmp_path, capsys, missing):
    absent = str(tmp_path / "no_such_run")
    args = [absent, str(FIXTURE)] if missing == "baseline" else [str(FIXTURE), absent]

    assert main(["compare", *args]) == 2
    assert capsys.readouterr().err.startswith("error:")


# report


def test_report_of_run_dir_with_traces_includes_trace_summary(runs, capsys):
    run_dir = run_dir_of(runs["good"])

    assert main(["report", str(run_dir)]) == 0
    assert TRACE_HEADER in capsys.readouterr().out


def test_report_of_bare_log_without_traces_has_no_trace_summary(tmp_path, capsys):
    log = tmp_path / "log.json"
    shutil.copy(FIXTURE, log)

    assert main(["report", str(log)]) == 0
    printed = capsys.readouterr().out
    assert printed.strip()
    assert "Trace summary" not in printed


# check

BASELINE_LOG = REPO / "baselines" / "calculator.json"
CASE_INPUTS = [json.loads(line)["input"] for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
FATAL = [str(DATASET), "--agent", "aea_cli_doubles:fatal_factory"]
GOOD = [str(DATASET), "--agent", AGENT]
UPDATE = "--update-baseline"
ALWAYS_WRONG = ["--scorer", "aea_cli_doubles:always_wrong"]
HALF_PASSING = ["--epochs", "2", "--scorer", "aea_cli_doubles:first_epoch_only"]
RUN_DEFAULTS = {
    **{"adapter": "strands", "runs_dir": Path("runs"), "epochs": 1, "scorer": [], "capture_content": False},
    **{"max_samples": None, "input_price": None, "output_price": None},
}
THRESHOLD_DEFAULTS = {
    "max_new_failures": 0,
    "max_pass_rate_drop": 0.0,
    "max_error_rate_increase": 0.0,
    "min_case_pass_rate": 1.0,
    "max_p_value": None,
}


def seed_run_dir(path):
    """A baseline run directory: one log (the committed calculator baseline) and an old report."""
    path.mkdir(parents=True)
    shutil.copy(BASELINE_LOG, path / "old.json")
    (path / "report.md").write_text("old report\n", encoding="utf-8")
    return path


def seed_files(path, *names):
    path.mkdir(parents=True)
    for name in names:
        (path / name).write_text("{}\n", encoding="utf-8")
    return path


def seed_file(path):
    shutil.copy(BASELINE_LOG, path)
    return path


def with_run_dir(path):
    return seed_run_dir(path / "baseline")


# name -> scenario directory -> (baseline, check args, --runs-dir or None for <scenario>/runs)
CHECKS = {
    "missing": lambda d: (d / "absent", GOOD, None),
    "freeze_new": lambda d: (d / "frozen" / "calculator", [*GOOD, UPDATE], None),
    "freeze_replace": lambda d: (with_run_dir(d), [*GOOD, UPDATE], None),
    "freeze_empty_dir": lambda d: (seed_files(d / "baseline"), [*GOOD, UPDATE], None),
    "refuse_capture": lambda d: (with_run_dir(d), [*GOOD, UPDATE, "--capture-content"], None),
    "refuse_file": lambda d: (seed_file(d / "baseline.json"), [*GOOD, UPDATE], None),
    "refuse_no_log": lambda d: (seed_files(d / "baseline", "notes.txt"), [*GOOD, UPDATE], None),
    "refuse_two_logs": lambda d: (seed_files(d / "baseline", "a.json", "b.json"), [*GOOD, UPDATE], None),
    "refuse_runs_dir_is_baseline": lambda d: (with_run_dir(d), [*GOOD, UPDATE], d / "baseline"),
    "refuse_runs_dir_inside": lambda d: (with_run_dir(d), [*GOOD, UPDATE], d / "baseline" / "runs"),
    "same_agent": lambda d: (with_run_dir(d), GOOD, None),
    "log_file_baseline": lambda d: (BASELINE_LOG, GOOD, None),
    "regressed": lambda d: (with_run_dir(d), [*GOOD, *ALWAYS_WRONG], None),
    "regressed_within_thresholds": lambda d: (
        with_run_dir(d),
        [*GOOD, *ALWAYS_WRONG, "--max-new-failures", "10", "--max-pass-rate-drop", "1.0"],
        None,
    ),
    "regressed_one_over_threshold": lambda d: (
        with_run_dir(d),
        [*GOOD, *ALWAYS_WRONG, "--max-new-failures", "9", "--max-pass-rate-drop", "1.0"],
        None,
    ),
    "half_passing_current": lambda d: (with_run_dir(d), [*GOOD, *HALF_PASSING, "--min-case-pass-rate", "0.5"], None),
    "error_compare": lambda d: (with_run_dir(d), FATAL, None),
    "error_freeze": lambda d: (d / "frozen", [*FATAL, UPDATE], None),
    "bad_agent": lambda d: (with_run_dir(d), [str(DATASET), "--agent", "examples.calculator.agent.build_agent"], None),
    "bad_scorer_freeze": lambda d: (with_run_dir(d), [*GOOD, UPDATE, "--scorer", "aea_cli_doubles.always_wrong"], None),
}
# Started once `aea run` has written a log in which every case passes one epoch in two.
HALF_PASSING_BASELINE = "half_passing_baseline"
REFUSALS = [
    *["refuse_capture", "refuse_file", "refuse_no_log", "refuse_two_logs"],
    *["refuse_runs_dir_is_baseline", "refuse_runs_dir_inside"],
]


def snapshot(path):
    """Every file under path with its bytes, so 'untouched' is checked exactly; None if path is absent."""
    if not path.exists():
        return None
    if path.is_file():
        return {"": path.read_bytes()}
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def check_runs(tmp_path_factory):
    env = doubles_env(tmp_path_factory.mktemp("check_doubles"))
    half_runs = tmp_path_factory.mktemp("half_passing_runs")
    half = start_cli(["run", *GOOD, *HALF_PASSING, "--runs-dir", str(half_runs)], env)

    def start(baseline, args, runs_dir, scenario_dir):
        runs_dir = runs_dir or scenario_dir / "runs"
        before = snapshot(baseline)
        process = start_cli(["check", *args, "--baseline", str(baseline), "--runs-dir", str(runs_dir)], env)
        return process, {"baseline": baseline, "runs_dir": runs_dir, "before": before}

    started = {}
    for name, scenario in CHECKS.items():
        scenario_dir = tmp_path_factory.mktemp(f"check_{name}")
        started[name] = start(*scenario(scenario_dir), scenario_dir)
    _, stderr = half.communicate(timeout=300)
    assert half.returncode == 0, stderr
    [half_run_dir] = [p for p in half_runs.iterdir() if p.is_dir()]
    scenario_dir = tmp_path_factory.mktemp(f"check_{HALF_PASSING_BASELINE}")
    started[HALF_PASSING_BASELINE] = start(half_run_dir, [*GOOD, "--min-case-pass-rate", "0.5"], None, scenario_dir)

    results = {}
    for name, (process, result) in started.items():
        stdout, stderr = process.communicate(timeout=300)
        results[name] = {**result, "code": process.returncode, "stdout": stdout, "stderr": stderr}
    return results


def check_run_dirs(result):
    runs_dir = result["runs_dir"]
    return [p for p in runs_dir.iterdir() if p.is_dir()] if runs_dir.exists() else []


def check_run_dir(result):
    [run_dir] = check_run_dirs(result)
    return run_dir


def lines_starting(result, prefix):
    return [line for line in stdout_lines(result) if line.startswith(prefix)]


def expected_comparison(baseline, run_dir, thresholds=None, min_case_pass_rate=1.0):
    """What `aea compare` logic renders for the pair, built from the library rather than the CLI."""
    from agent_accelerator.compare import Thresholds, compare, load_results
    from agent_accelerator.report import render_comparison

    pair = (load_results(baseline, min_case_pass_rate), load_results(run_dir, min_case_pass_rate))
    return render_comparison(compare(*pair, thresholds or Thresholds()))


class StopBeforeRun(Exception):
    """Raised by the run fakes below, so main stops once the settings it would run with are known."""


@pytest.fixture
def merged_args(monkeypatch):
    """Replaces the run with a recorder of the arguments main hands it, after --config and the defaults are applied."""
    seen = []

    def record(args):
        seen.append(vars(args).copy())
        raise StopBeforeRun

    monkeypatch.setattr(cli_module, "_execute_run", record)
    monkeypatch.setattr(sys, "path", [*sys.path])  # main prepends the working directory
    return seen


@pytest.fixture
def task_args(monkeypatch):
    """Runs the real run path up to build_task, records what build_task received, then stops; tracing is stubbed
    because the tracer provider can only be set once per process."""
    import agent_accelerator.run as run_module
    import agent_accelerator.tracing as tracing_module

    seen = []

    class Provider:
        def shutdown(self):
            pass

    def record(dataset, agent, adapter, capture_content, **kwargs):
        maps_and_config = {k: kwargs[k] for k in ("input_map", "output_map", "config")}
        seen.append({"agent": agent, "adapter": adapter, **maps_and_config})
        raise StopBeforeRun

    monkeypatch.setattr(tracing_module, "configure_tracing", lambda path, capture_content: Provider())
    monkeypatch.setattr(run_module, "build_task", record)
    monkeypatch.setattr(sys, "path", [*sys.path])  # main prepends the working directory
    return seen


@pytest.mark.parametrize("command", ["run", "check"])
def test_run_flags_have_the_documented_defaults_in_run_and_check(merged_args, tmp_path, command):
    # The adapter default is filled in by main after --config is merged, so the defaults are read from what main hands
    # the run rather than from the parser. Witnesses: s47 adapter fallback dropped, s47 default adapter langgraph,
    # "s15 default runs dir", "s15 default epochs" fail both ids.
    argv = [command, "dataset.jsonl", "--agent", AGENT, *(["--baseline", str(tmp_path)] if command == "check" else [])]

    with pytest.raises(StopBeforeRun):
        main(argv)

    [args] = merged_args
    assert {key: args[key] for key in RUN_DEFAULTS} == RUN_DEFAULTS


@pytest.mark.parametrize("command", ["compare", "check"])
def test_threshold_flags_have_the_documented_defaults_in_compare_and_check(command):
    # Witness: "s15 default max new failures", "s15 default pass rate drop", "s15 default error rate",
    # "s15 default min case pass rate", "s20 p value default on" in _add_threshold_args fail both ids.
    argv = ["compare", "a", "b"] if command == "compare" else ["check", "d.jsonl", "--agent", AGENT, "--baseline", "b"]
    args = vars(build_parser().parse_args(argv))

    assert {key: args[key] for key in THRESHOLD_DEFAULTS} == THRESHOLD_DEFAULTS


THRESHOLD_ARGV = {
    "compare": ["compare", "a", "b"],
    "check": ["check", "d.jsonl", "--agent", AGENT, "--baseline", "b"],
}


@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize("value", ["0.05", "1e-3", "0.999"])
def test_max_p_value_strictly_between_zero_and_one_is_parsed_as_a_float(command, value):
    # Witness: "s20 p value unvalidated" leaves the string unparsed.
    args = build_parser().parse_args([*THRESHOLD_ARGV[command], "--max-p-value", value])

    assert args.max_p_value == float(value)


@pytest.mark.parametrize("command", ["compare", "check"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("abc", id="not-a-number"),  # witness: "s20 p value unvalidated"
        pytest.param("0", id="zero"),  # witness: "s20 alpha zero accepted"
        pytest.param("1", id="one"),  # witness: "s20 alpha one accepted"
    ],
)
def test_max_p_value_outside_the_open_unit_interval_is_a_usage_error(capsys, command, value):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([*THRESHOLD_ARGV[command], "--max-p-value", value])

    assert exc.value.code == 2
    assert "--max-p-value" in capsys.readouterr().err


def test_check_update_baseline_defaults_off():
    # Witness: "s15 update baseline default on" (store_false on --update-baseline).
    args = build_parser().parse_args(["check", "d.jsonl", "--agent", AGENT, "--baseline", "base"])

    assert args.update_baseline is False
    assert args.baseline == Path("base")


def test_check_without_baseline_flag_is_a_usage_error(capsys):
    # Witness: "s15 baseline optional" (required=False on --baseline).
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["check", "d.jsonl", "--agent", AGENT])

    assert exc.value.code == 2
    assert "--baseline" in capsys.readouterr().err


def test_check_with_missing_baseline_exits_two_naming_path_and_flag_without_running(check_runs):
    # Witness: "s15 missing baseline check dropped" (`elif not baseline.exists()` in _check).
    result = check_runs["missing"]

    assert result["code"] == 2
    assert result["stderr"].startswith("error:"), result["stderr"]
    assert result["baseline"].as_posix() in result["stderr"]
    assert "--update-baseline" in result["stderr"]
    assert not result["runs_dir"].exists()


def test_check_update_baseline_freezes_a_copy_of_the_new_run_into_a_missing_dir(check_runs):
    # Witness: "s15 copy into subdir", "s15 update exits regression", "s15 frozen line dropped".
    result = check_runs["freeze_new"]
    assert result["code"] == 0, result["stderr"]
    run_dir = check_run_dir(result)

    frozen = snapshot(result["baseline"])
    assert frozen == snapshot(run_dir)
    assert len([name for name in frozen if name.endswith(".json")]) == 1
    assert {"report.md", "traces.jsonl"} <= set(frozen)
    [line] = lines_starting(result, "BASELINE frozen")
    assert result["baseline"].as_posix() in line
    assert run_dir.as_posix() in line


def test_check_frozen_baseline_from_a_default_run_holds_no_case_input(check_runs):
    # Witness: "s15 freeze unscrubbed" (run_task given capture_content=True in _execute_run).
    frozen = snapshot(check_runs["freeze_new"]["baseline"])
    assert frozen

    leaked = [(name, text) for name, data in frozen.items() for text in CASE_INPUTS if text.encode() in data]
    assert leaked == []


def test_check_update_baseline_replaces_an_existing_run_dir(check_runs):
    # Witness: "s15 rmtree skipped" (copytree then fails on the existing dir), "s15 copy into subdir".
    result = check_runs["freeze_replace"]
    assert result["code"] == 0, result["stderr"]

    frozen = snapshot(result["baseline"])
    assert "old.json" not in frozen
    assert frozen == snapshot(check_run_dir(result))


def test_check_update_baseline_freezes_into_an_existing_empty_dir(check_runs):
    # Witness: in cli.py _validate_baseline_target, revert the early return to `if not baseline.exists():`. The empty
    # DIR then reaches resolve_log, which finds no log, and the run is refused with exit 2.
    result = check_runs["freeze_empty_dir"]
    assert result["code"] == 0, result["stderr"]

    assert snapshot(result["baseline"]) == snapshot(check_run_dir(result))


@pytest.mark.parametrize("name", REFUSALS)
def test_check_update_baseline_refusal_exits_two_before_running_and_leaves_dir_untouched(check_runs, name):
    # Witness per id: "s15 capture refusal removed" (refuse_capture), "s15 file refusal removed" (refuse_file),
    # "s15 not run dir refusal removed" (refuse_no_log, refuse_two_logs), "s15 runs-dir containment removed"
    # (both runs_dir ids), "s15 validation after run" (every id: a run directory now exists).
    result = check_runs[name]

    assert result["code"] == 2
    assert result["stderr"].startswith("error:"), result["stderr"]
    assert check_run_dirs(result) == []
    assert result["before"] is not None
    assert snapshot(result["baseline"]) == result["before"]


@pytest.mark.parametrize("name", ["same_agent", "log_file_baseline"])
def test_check_same_agent_as_baseline_exits_zero_and_writes_the_comparison(check_runs, name):
    # Witness: "s15 comparison not written" fails both ids; "s15 update exits regression" does not apply here.
    result = check_runs[name]
    assert result["code"] == 0, result["stderr"]
    run_dir = check_run_dir(result)
    comparison = run_dir / "comparison.md"

    assert comparison.read_text(encoding="utf-8") == expected_comparison(result["baseline"], run_dir)
    [line] = lines_starting(result, "OK")
    assert line == stdout_lines(result)[-1]
    for path in (result["baseline"], run_dir, comparison):
        assert path.as_posix() in line


def test_check_regressed_agent_exits_one_with_regression_line_and_comparison(check_runs):
    # Witness: "s15 regressed exits ok", "s15 verdict always OK", "s15 comparison swapped" (the new
    # failures read as newly passing, so the run no longer regresses).
    result = check_runs["regressed"]
    assert result["code"] == 1, result["stderr"]
    run_dir = check_run_dir(result)

    text = (run_dir / "comparison.md").read_text(encoding="utf-8")
    assert text == expected_comparison(result["baseline"], run_dir)
    assert "## Newly failing" in text
    assert len(lines_starting(result, "REGRESSION")) == 1
    assert lines_starting(result, "OK") == []


def test_check_prints_the_hint_on_stderr_only_when_a_case_fails_without_capture_content(check_runs):
    # Witnesses: "s43 cli hint to stdout" fails regressed; "s43 cli hint failure condition dropped" and "s43 cli hint
    # it to le" fail same_agent.
    regressed, same = check_runs["regressed"], check_runs["same_agent"]
    assert regressed["code"] == 1, regressed["stderr"]
    assert same["code"] == 0, same["stderr"]

    assert hint_lines(regressed) == [HINT]
    assert HINT not in regressed["stdout"]
    assert HINT not in same["stderr"]
    assert HINT not in same["stdout"]


def test_check_thresholds_reach_the_comparison(check_runs):
    # Witness: "s15 thresholds ignored" (Thresholds(0, 0.0, 0.0) in _comparison). Ten new failures with ten
    # allowed and a full pass-rate drop allowed is OK; with nine allowed it is a REGRESSION.
    from agent_accelerator.compare import Thresholds

    within, over = check_runs["regressed_within_thresholds"], check_runs["regressed_one_over_threshold"]

    assert within["code"] == 0, within["stderr"]
    assert over["code"] == 1, over["stderr"]
    run_dir = check_run_dir(over)
    expected = expected_comparison(over["baseline"], run_dir, Thresholds(9, 1.0, 0.0))
    assert (run_dir / "comparison.md").read_text(encoding="utf-8") == expected


def test_check_min_case_pass_rate_applies_to_the_current_run(check_runs):
    # Witness: "s15 min case pass rate ignored current". Each case passes one epoch in two: passing at 0.5,
    # but ten new failures at the default 1.0.
    result = check_runs["half_passing_current"]

    assert result["code"] == 0, result["stderr"]
    assert lines_starting(result, "OK")


def test_check_min_case_pass_rate_applies_to_the_baseline(check_runs):
    # Witness: "s15 min case pass rate ignored baseline". At 0.5 the half-passing baseline passes every
    # case, so a fully passing run has nothing newly passing.
    result = check_runs[HALF_PASSING_BASELINE]
    assert result["code"] == 0, result["stderr"]
    run_dir = check_run_dir(result)

    text = (run_dir / "comparison.md").read_text(encoding="utf-8")
    assert "## Newly passing" not in text
    assert text == expected_comparison(result["baseline"], run_dir, min_case_pass_rate=0.5)


@pytest.mark.parametrize("name", ["error_compare", "error_freeze"])
def test_check_run_with_error_status_exits_two_without_comparing_or_freezing(check_runs, name):
    # Witness: "s15 failed run continues" (error_compare writes comparison.md, error_freeze copies to DIR),
    # "s15 failed run exits ok", "s15 error line dropped".
    result = check_runs[name]
    run_dir = check_run_dir(result)

    assert result["code"] == 2, result["stderr"]
    [line] = lines_starting(result, "ERROR")
    assert run_dir.as_posix() in line
    assert not (run_dir / "comparison.md").exists()
    assert snapshot(result["baseline"]) == result["before"]


@pytest.mark.parametrize("name", ["bad_agent", "bad_scorer_freeze"])
def test_check_run_that_raises_exits_two_leaving_no_run_dir_and_baseline_untouched(check_runs, name):
    # Witness: "cli cleanup on failure" (the rmtree in _execute_run's except) fails both ids.
    result = check_runs[name]

    assert result["code"] == 2
    assert result["stderr"].startswith("error:"), result["stderr"]
    assert check_run_dirs(result) == []
    assert snapshot(result["baseline"]) == result["before"]


# --config


REFS = {
    "agent": "cfg.agent:build_agent",
    "input_map": "cfg.agent:to_input",
    "output_map": "cfg.agent:from_output",
}
FLAG_REFS = {
    "agent": "flag.agent:build_agent",
    "input_map": "flag.agent:to_input",
    "output_map": "flag.agent:from_output",
}
MAPS_NEED_LANGGRAPH = "--input-map and --output-map need --adapter langgraph"
AGENT_REQUIRED = "--agent is required (flag or config)"


def write_toml(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f'{key} = "{value}"\n' for key, value in settings.items()), encoding="utf-8")
    return path


def run_argv(command, tmp_path, *extra):
    """A run or check command line with its run directory under tmp_path; check gets an existing baseline."""
    baseline = ["--baseline", str(tmp_path)] if command == "check" else []
    return [command, "dataset.jsonl", "--runs-dir", str(tmp_path / "runs"), *baseline, *extra]


def flags(settings):
    return [arg for key, value in settings.items() for arg in (f"--{key.replace('_', '-')}", value)]


def recorded(adapter, agent, input_map=None, output_map=None, config=None):
    return {"agent": agent, "adapter": adapter, "input_map": input_map, "output_map": output_map, "config": config}


@pytest.mark.parametrize("command", ["run", "check"])
def test_config_fills_every_run_setting_left_off_the_command_line(task_args, tmp_path, command):
    # Witness: s47 config values not applied (`setattr(args, key, value)` -> `pass`) fails both ids.
    config = write_toml(tmp_path / "aea.toml", {"adapter": "langgraph", **REFS})

    with pytest.raises(StopBeforeRun):
        main(run_argv(command, tmp_path, "--config", str(config)))

    assert task_args == [recorded("langgraph", **REFS, config=config.as_posix())]


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize(
    ("settings", "given", "expected"),
    [
        pytest.param(
            {"adapter": "langgraph", **REFS}, FLAG_REFS, recorded("langgraph", **FLAG_REFS), id="refs_from_flags"
        ),
        pytest.param(
            {"adapter": "langgraph", "agent": REFS["agent"]},
            {"adapter": "strands"},
            recorded("strands", REFS["agent"]),
            id="adapter_from_flag",
        ),
        pytest.param(
            {"adapter": "langgraph", **REFS},
            {"agent": FLAG_REFS["agent"]},
            recorded("langgraph", FLAG_REFS["agent"], REFS["input_map"], REFS["output_map"]),
            id="agent_from_flag_maps_from_config",
        ),
    ],
)
def test_a_flag_on_the_command_line_beats_the_same_setting_in_the_config(
    task_args, tmp_path, command, settings, given, expected
):
    # Witness: s47 config overrides flags (`if getattr(args, key) is None:` -> `if True:`) fails every id.
    config = write_toml(tmp_path / "aea.toml", settings)

    with pytest.raises(StopBeforeRun):
        main(run_argv(command, tmp_path, "--config", str(config), *flags(given)))

    assert task_args == [{**expected, "config": config.as_posix()}]


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("with_config", [False, True], ids=["no_config", "config_without_adapter"])
def test_adapter_set_neither_by_flag_nor_config_is_strands_with_no_maps(task_args, tmp_path, command, with_config):
    # Witness: s47 adapter fallback dropped (`args.adapter = "strands"` -> `pass`) fails every id.
    config = write_toml(tmp_path / "aea.toml", {"agent": REFS["agent"]})
    argv = ["--config", str(config)] if with_config else ["--agent", REFS["agent"]]

    with pytest.raises(StopBeforeRun):
        main(run_argv(command, tmp_path, *argv))

    assert task_args == [recorded("strands", REFS["agent"], config=config.as_posix() if with_config else None)]


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("with_config", [False, True], ids=["no_config", "config_without_agent"])
def test_agent_set_neither_by_flag_nor_config_is_a_usage_error_before_running(
    task_args, tmp_path, capsys, command, with_config
):
    # Witness: s47 agent required error dropped (`parser.error(...)` -> `pass`) lets the run start with agent None.
    config = write_toml(tmp_path / "aea.toml", {"adapter": "langgraph"})

    with pytest.raises(SystemExit) as exc:
        main(run_argv(command, tmp_path, *(["--config", str(config)] if with_config else [])))

    assert exc.value.code == 2
    assert AGENT_REQUIRED in capsys.readouterr().err
    assert task_args == []


@pytest.mark.parametrize("command", ["run", "check"])
def test_without_config_every_run_setting_comes_from_its_flag(task_args, tmp_path, command):
    # Witness: s47 config loaded when absent (`if args.config is not None:` -> `if True:`) fails both ids.
    with pytest.raises(StopBeforeRun):
        main(run_argv(command, tmp_path, "--adapter", "langgraph", *flags(FLAG_REFS)))

    assert task_args == [recorded("langgraph", **FLAG_REFS)]


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize(
    ("settings", "given"),
    [
        pytest.param({"agent": REFS["agent"], "input_map": REFS["input_map"]}, [], id="config_maps_default_adapter"),
        pytest.param(
            {"adapter": "strands", "agent": REFS["agent"], "output_map": REFS["output_map"]}, [], id="config_strands"
        ),
        pytest.param({"adapter": "langgraph", **REFS}, ["--adapter", "strands"], id="flag_strands_config_maps"),
        pytest.param(None, ["--agent", REFS["agent"], "--input-map", REFS["input_map"]], id="flags_only_control"),
    ],
)
def test_maps_without_langgraph_are_a_usage_error_whether_they_come_from_config_or_flags(
    task_args, tmp_path, capsys, command, settings, given
):
    # Witness: s47 apply config after maps check (the two blocks in main swapped) fails every id but the flags-only
    # control, which shows the expected error is the one flags already gave.
    config = ["--config", str(write_toml(tmp_path / "aea.toml", settings))] if settings else []

    with pytest.raises(SystemExit) as exc:
        main(run_argv(command, tmp_path, *config, *given))

    assert exc.value.code == 2
    assert MAPS_NEED_LANGGRAPH in capsys.readouterr().err
    assert task_args == []


UNKNOWN_KEY = b'model = "gpt"\n'
NOT_UTF8 = b'agent = "caf\xff:build_agent"\n' 


def decoder_message(content):
    with pytest.raises(UnicodeDecodeError) as exc:
        content.decode("utf-8")
    return str(exc.value)


@pytest.mark.parametrize(
    ("command", "extra", "content", "reason"),
    [
        pytest.param("run", [], UNKNOWN_KEY, "unknown key 'model'", id="run"),
        pytest.param(
            "check",
            ["--update-baseline", "--capture-content"],
            UNKNOWN_KEY,
            "unknown key 'model'",
            id="check_refused_freeze",
        ),
        pytest.param("check", ["--baseline", "absent"], UNKNOWN_KEY, "unknown key 'model'", id="check_missing_baseline"),
        pytest.param("run", [], NOT_UTF8, decoder_message(NOT_UTF8), id="run_not_utf8"),
    ],
)
def test_config_error_exits_two_before_the_runs_dir_exists_and_before_baseline_validation(
    task_args, tmp_path, capsys, command, extra, content, reason
):
    # The check ids would otherwise fail baseline validation (exit 2 with "error:", not a usage error naming the file).
    # The non-UTF-8 reason is read from the decoder, not written down.
    # Witnesses: s47 config applied inside the run (the _apply_config call moved from main to after new_run_dir in
    # _execute_run, a two-site edit applied by hand) fails every id; s48 config UnicodeDecodeError not caught
    # (`except (tomllib.TOMLDecodeError, UnicodeDecodeError)` -> `except tomllib.TOMLDecodeError`) fails run_not_utf8.
    config = tmp_path / "aea.toml"
    config.write_bytes(content)
    argv = run_argv(command, tmp_path, "--agent", AGENT, "--config", str(config), *extra)

    assert main(argv) == 2
    err = capsys.readouterr().err
    assert f"{config.as_posix()}: {reason}" in err
    assert "Traceback" not in err
    assert not (tmp_path / "runs").exists()
    assert task_args == []





@pytest.mark.parametrize("command", ["run", "check"])
def test_an_aea_toml_in_the_working_directory_is_ignored_without_config(task_args, tmp_path, monkeypatch, command):
    # Witness: s47 aea.toml auto-discovered (`args.config = Path("aea.toml")` when absent and present) fails both ids.
    monkeypatch.chdir(tmp_path)
    write_toml(tmp_path / "aea.toml", {"adapter": "langgraph", **REFS})

    with pytest.raises(StopBeforeRun):
        main(run_argv(command, tmp_path, "--agent", FLAG_REFS["agent"]))

    assert task_args == [recorded("strands", FLAG_REFS["agent"])]


def test_config_directory_is_not_added_to_the_import_path(task_args, tmp_path, monkeypatch):
    # Refs resolve from the working directory only, which main does put on the path (the reachability control).
    # Witness: s47 config dir on sys.path (`sys.path.insert(0, str(args.config.parent))` after load_config).
    work, settings = tmp_path / "work", tmp_path / "settings"
    work.mkdir()
    monkeypatch.chdir(work)
    config = write_toml(settings / "aea.toml", {"agent": REFS["agent"]})

    with pytest.raises(StopBeforeRun):
        main(run_argv("run", tmp_path, "--config", str(config)))

    on_path = {Path(p).resolve() for p in sys.path if p}
    assert work.resolve() in on_path
    assert settings.resolve() not in on_path


def test_config_path_reaches_build_task_as_given_in_posix_form_not_resolved(task_args, tmp_path, monkeypatch):
    # Witnesses: s47 cli config not passed (`config=None`); s47 cli config resolved
    # (`args.config.resolve().as_posix()`); s47 cli config not posix (`str(args.config)`, Windows only).
    monkeypatch.chdir(tmp_path)
    write_toml(tmp_path / "conf" / "aea.toml", {"agent": REFS["agent"]})

    with pytest.raises(StopBeforeRun):
        main(run_argv("run", tmp_path, "--config", os.path.join("conf", "aea.toml")))

    assert task_args == [recorded("strands", REFS["agent"], config="conf/aea.toml")]


@pytest.mark.parametrize("example", ["triage", "expense"])
def test_example_config_alone_supplies_a_runnable_setting_set(task_args, tmp_path, example):
    # Every ref is resolved with load_factory, as the real run would, after main has merged the file.
    # Witnesses: s47 triage config adapter dropped (maps then need langgraph, exit 2); s47 triage config input_map ref
    # broken and s47 expense config agent ref broken fail load_factory.
    from agent_accelerator.adapters import load_factory

    config = REPO / "examples" / example / "aea.toml"

    with pytest.raises(StopBeforeRun):
        main(run_argv("run", tmp_path, "--config", str(config)))

    [settings] = task_args
    refs = [settings[key] for key in ("agent", "input_map", "output_map") if settings[key] is not None]
    assert settings["adapter"] == "langgraph"
    assert refs
    for ref in refs:
        assert callable(load_factory(ref))


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["compare", "a", "b"], id="compare"),
        pytest.param(["report", "a"], id="report"),
        pytest.param(["init", "a"], id="init"),
        pytest.param(["export", "a.md"], id="export"),
    ],
)
def test_commands_that_do_not_run_an_agent_have_no_config_flag(capsys, argv):
    # Witnesses: s47 compare gains --config, s47 report gains --config, s47 init gains --config, s47 export gains
    # --config each fail their id.
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([*argv, "--config", "aea.toml"])

    assert exc.value.code == 2
    assert "unrecognized arguments: --config" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "check"])
@pytest.mark.parametrize("adapter", ["Strands", "openai"])
def test_adapter_flag_outside_strands_and_langgraph_is_still_rejected_by_the_parser(capsys, command, adapter):
    # Witness: s47 cli adapter choices dropped (`choices=ADAPTERS` removed from --adapter) fails every id.
    check = ["--baseline", "b"] if command == "check" else []
    argv = [command, "d.jsonl", "--agent", AGENT, "--adapter", adapter, *check]

    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(argv)

    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err

