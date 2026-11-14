import sys
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT, Score

from agent_accelerator.cli import main
from agent_accelerator.compare import (
    CaseResult,
    RunResults,
    Thresholds,
    compare,
    load_results,
    resolve_log,
)
from agent_accelerator.judge import JudgedEpoch
from agent_accelerator.report import render_comparison
from agent_accelerator.tool_metrics import CaseToolUse

FIXTURES = Path(__file__).parents[1] / "fixtures"


def make_run(cases=None, *, status="success", dataset_sha256=None, capture_content=False):
    return RunResults(
        run_id="run",
        log_path=Path("run.json"),
        dataset_sha256=dataset_sha256,
        status=status,
        cases=cases or {},
        capture_content=capture_content,
    )


def make_case(case_id, *, passed=True, error=None, latency_s=None):
    return CaseResult(
        id=case_id,
        passed=passed,
        error=error,
        latency_s=latency_s,
        failures={},
    )


def test_run_results_rates_and_median_latency_ignore_missing_latencies():
    run = make_run(
        {
            "one": make_case("one", passed=True, error=None, latency_s=1.0),
            "two": make_case("two", passed=False, error="failed", latency_s=None),
            "three": make_case("three", passed=True, error=None, latency_s=3.0),
        }
    )

    assert run.pass_rate == pytest.approx(2 / 3)
    assert run.error_rate == pytest.approx(1 / 3)
    assert run.median_latency_s == 2.0


def test_run_results_rates_and_latency_are_zero_or_none_for_no_cases():
    run = make_run()

    assert run.pass_rate == 0.0
    assert run.error_rate == 0.0
    assert run.median_latency_s is None


def test_run_results_median_latency_is_none_when_all_latencies_are_missing():
    run = make_run({"one": make_case("one"), "two": make_case("two")})

    assert run.median_latency_s is None


def test_case_classification_covers_each_baseline_and_current_state():
    baseline = make_run(
        {
            "new-failure": make_case("new-failure"),
            "new-pass": make_case("new-pass", passed=False),
            "still-failing": make_case("still-failing", passed=False),
            "still-passing": make_case("still-passing"),
            "removed": make_case("removed"),
        }
    )
    current = make_run(
        {
            "new-failure": make_case("new-failure", passed=False),
            "new-pass": make_case("new-pass"),
            "still-failing": make_case("still-failing", passed=False),
            "still-passing": make_case("still-passing"),
            "added": make_case("added", passed=False),
        }
    )

    result = compare(baseline, current, Thresholds())

    assert result.newly_failing == ["new-failure"]
    assert result.newly_passing == ["new-pass"]
    assert result.still_failing == ["still-failing"]
    assert result.added == ["added"]
    assert result.removed == ["removed"]


def test_removed_cases_are_sorted():
    baseline = make_run({case_id: make_case(case_id) for case_id in ("zulu", "alpha", "mike")})

    assert compare(baseline, make_run(), Thresholds()).removed == [
        "alpha",
        "mike",
        "zulu",
    ]


def test_passing_cases_in_both_runs_are_not_classified():
    result = compare(
        make_run({"same": make_case("same")}),
        make_run({"same": make_case("same")}),
        Thresholds(),
    )

    assert result.newly_failing == []
    assert result.newly_passing == []
    assert result.still_failing == []
    assert result.added == []
    assert result.removed == []


def test_non_success_current_status_is_a_regression():
    result = compare(
        make_run({"same": make_case("same")}),
        make_run({"same": make_case("same")}, status="error"),
        Thresholds(max_pass_rate_drop=1.0, max_error_rate_increase=1.0),
    )

    assert result.regressed


def test_new_failure_limit_is_strictly_exceeded():
    baseline = make_run({"case": make_case("case")})
    current = make_run({"case": make_case("case", passed=False)})

    result = compare(
        baseline,
        current,
        Thresholds(max_new_failures=1, max_pass_rate_drop=1.0),
    )

    assert not result.regressed


def test_new_failures_above_the_configured_limit_are_a_regression():
    baseline = make_run({str(index): make_case(str(index)) for index in range(2)})
    current = make_run(
        {
            "0": make_case("0", passed=False),
            "1": make_case("1", passed=False),
        }
    )

    result = compare(
        baseline,
        current,
        Thresholds(max_new_failures=1, max_pass_rate_drop=1.0),
    )

    assert result.regressed


@pytest.mark.parametrize(
    ("threshold", "regressed"),
    [(0.1, False), (0.09, True)],
    ids=["equal-to-limit", "above-limit"],
)
def test_pass_rate_drop_threshold_is_strict(threshold, regressed):
    baseline = make_run({str(index): make_case(str(index)) for index in range(10)})
    current_cases = dict(baseline.cases)
    current_cases["0"] = make_case("0", passed=False)

    result = compare(
        baseline,
        make_run(current_cases),
        Thresholds(max_new_failures=1, max_pass_rate_drop=threshold),
    )

    assert result.regressed is regressed


@pytest.mark.parametrize(
    ("threshold", "regressed"),
    [(0.1, False), (0.09, True)],
    ids=["equal-to-limit", "above-limit"],
)
def test_error_rate_rise_threshold_is_strict(threshold, regressed):
    baseline = make_run({str(index): make_case(str(index)) for index in range(10)})
    current_cases = dict(baseline.cases)
    current_cases["0"] = make_case("0", error="agent error")

    result = compare(
        baseline,
        make_run(current_cases),
        Thresholds(max_error_rate_increase=threshold),
    )

    assert result.regressed is regressed


def test_added_failure_can_trigger_pass_rate_regression():
    baseline = make_run({"existing": make_case("existing")})
    current = make_run(
        {
            "existing": make_case("existing"),
            "added-failure": make_case("added-failure", passed=False),
        }
    )

    result = compare(
        baseline,
        current,
        Thresholds(max_new_failures=1, max_pass_rate_drop=0.4),
    )

    assert result.newly_failing == []
    assert result.added == ["added-failure"]
    assert result.regressed


@pytest.mark.parametrize(
    ("baseline_ids", "current_ids", "baseline_hash", "current_hash"),
    [
        (["kept"], ["kept"], "baseline", "current"),
        (["removed", "kept"], ["kept"], "same", "same"),
    ],
    ids=["changed-dataset-hash", "removed-cases"],
)
def test_dataset_hash_difference_and_removed_cases_are_warnings(baseline_ids, current_ids, baseline_hash, current_hash
):
    baseline = make_run(
        {case_id: make_case(case_id) for case_id in baseline_ids},
        dataset_sha256=baseline_hash,
    )
    current = make_run(
        {case_id: make_case(case_id) for case_id in current_ids},
        dataset_sha256=current_hash,
    )

    result = compare(baseline, current, Thresholds())

    assert result.warnings
    assert not result.regressed

def test_identical_runs_have_no_regressions_or_warnings():
    baseline = make_run(
        {"pass": make_case("pass"), "fail": make_case("fail", passed=False)},
        dataset_sha256="same-hash",
    )

    result = compare(baseline, baseline, Thresholds())

    assert not result.regressed
    assert result.regressions == []
    assert result.warnings == []


def test_resolve_log_returns_a_file_path_unchanged(tmp_path):
    path = tmp_path / "run.json"
    path.write_text("{}", encoding="utf-8")

    assert resolve_log(path) == path


@pytest.mark.parametrize("file_count", [0, 2])
def test_resolve_log_rejects_directories_without_exactly_one_json(tmp_path, file_count):
    for index in range(file_count):
        (tmp_path / f"run-{index}.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        resolve_log(tmp_path)


def test_resolve_log_selects_the_only_json_in_a_directory(tmp_path):
    expected = tmp_path / "only.json"
    expected.write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a log", encoding="utf-8")

    assert resolve_log(tmp_path) == expected


def test_capture_fixture_loads_as_ten_successful_cases():
    results = load_results(FIXTURES / "calculator_capture_content.json")

    assert len(results.cases) == 10
    assert all(case.passed for case in results.cases.values())
    assert results.status == "success"
    assert all(case.error is None for case in results.cases.values())
    assert results.dataset_sha256 is not None
    assert len(results.dataset_sha256) == 64
    assert all(character in "0123456789abcdef" for character in results.dataset_sha256.lower())
    assert all(
        isinstance(case.latency_s, (int, float)) and not isinstance(case.latency_s, bool)
        for case in results.cases.values()
    )


def test_broken_fixture_has_the_two_specified_failures_and_explanations():
    results = load_results(FIXTURES / "calculator_broken_redacted.json")

    assert len(results.cases) == 10
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == {"subtract", "subtract_large"}
    assert all(
        results.cases[case_id].failures and all(results.cases[case_id].failures.values())
        for case_id in ("subtract", "subtract_large")
    )


def test_broken_fixture_regresses_against_capture_with_default_thresholds():
    result = compare(
        load_results(FIXTURES / "calculator_capture_content.json"),
        load_results(FIXTURES / "calculator_broken_redacted.json"),
        Thresholds(),
    )

    assert set(result.newly_failing) == {"subtract", "subtract_large"}
    assert result.regressed


def test_load_results_marks_sample_without_scores_as_failed(tmp_path):
    log = read_eval_log(FIXTURES / "calculator_capture_content.json")
    sample = log.samples[0]
    sample.scores = {}
    path = tmp_path / "without-scores.json"
    write_eval_log(log, location=path)

    results = load_results(path)

    assert not results.cases[str(sample.id)].passed
    assert results.cases[str(sample.id)].failures


def test_load_results_uses_sample_error_message_when_agent_error_is_absent(tmp_path):
    log = read_eval_log(FIXTURES / "calculator_capture_content.json")
    sample = log.samples[0]
    sample.metadata.pop("agent_error", None)
    sample.error = {
        "message": "sample-level failure",
        "traceback": "",
        "traceback_ansi": "",
    }
    path = tmp_path / "sample-error.json"
    write_eval_log(log, location=path)

    results = load_results(path)

    assert results.cases[str(sample.id)].error == "sample-level failure"


def write_epoch_log(tmp_path, epochs, *, case_id="add"):
    """Writes a log whose only case ran once per entry in `epochs`.

    Each entry may set `scores` ({scorer: (value, explanation) or (value, explanation, metadata)}), `error` and
    `latency`.
    """
    log = read_eval_log(FIXTURES / "calculator_capture_content.json")
    template = next(s for s in log.samples if str(s.id) == case_id)
    samples = []
    for number, spec in enumerate(epochs, start=1):
        sample = template.model_copy(deep=True)
        sample.epoch = number
        sample.scores = {
            name: Score(value=value, explanation=explanation, metadata=metadata[0] if metadata else None)
            for name, (value, explanation, *metadata) in spec.get(
                "scores", {"case_checks": (CORRECT, "all checks passed")}
            ).items()
        }
        sample.metadata["agent_error"] = spec.get("error")
        sample.error = None
        sample.total_time = spec.get("latency", template.total_time)
        samples.append(sample)
    log.samples = samples
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "epochs.json"
    write_eval_log(log, location=path)
    return path


PASS = {"scores": {"case_checks": (CORRECT, "all checks passed")}}


def fail(reason="wrong answer"):
    return {"scores": {"case_checks": (INCORRECT, reason)}}


def test_load_results_groups_epochs_into_one_case_with_run_and_pass_counts(tmp_path):
    path = write_epoch_log(
        tmp_path,
        [
            PASS,
            fail(),
            # One scorer passing is not enough: every scorer must pass.
            {
                "scores": {
                    "case_checks": (CORRECT, "all checks passed"),
                    "extra": (INCORRECT, "extra check failed"),
                }
            },
            PASS,
        ],
    )

    results = load_results(path, min_case_pass_rate=0.0)

    assert list(results.cases) == ["add"]
    case = results.cases["add"]
    assert case.id == "add"
    assert case.runs == 4
    assert case.passes == 2


@pytest.mark.parametrize(
    ("pass_count", "min_case_pass_rate", "passed"),
    [
        (4, None, True),
        (3, None, False),
        (2, 0.5, True),
        (1, 0.5, False),
        (3, 0.75, True),
    ],
    ids=[
        "default-all-epochs",
        "default-three-of-four-fails",
        "half-exactly-equal-passes",
        "quarter-below-half-fails",
        "three-quarters-exactly-equal-passes",
    ],
)
def test_case_passes_when_share_of_passing_epochs_reaches_threshold(tmp_path, pass_count, min_case_pass_rate, passed):
    path = write_epoch_log(tmp_path, [PASS] * pass_count + [fail()] * (4 - pass_count))

    if min_case_pass_rate is None:
        results = load_results(path)
    else:
        results = load_results(path, min_case_pass_rate=min_case_pass_rate)

    assert results.cases["add"].passes == pass_count
    assert results.cases["add"].passed is passed


def test_case_error_is_the_first_non_empty_error_across_epochs(tmp_path):
    path = write_epoch_log(
        tmp_path,
        [
            PASS,
            {**fail(), "error": "first error"},
            {**fail(), "error": ""},
            {**fail(), "error": "last error"},
        ],
    )

    assert load_results(path, min_case_pass_rate=0.0).cases["add"].error == "first error"


def test_case_error_is_none_when_no_epoch_errored(tmp_path):
    path = write_epoch_log(tmp_path, [PASS, fail(), PASS])

    assert load_results(path).cases["add"].error is None


def judged(value, metadata=None, *, error=None):
    """One epoch whose case checks pass and whose judge scored `value` with `metadata`."""
    scores = {"case_checks": (CORRECT, "all checks passed"), "judge": (value, "judge", metadata or {})}
    return {"scores": scores, "error": error}


@pytest.mark.parametrize(
    ("epoch", "error", "error_rate"),
    [
        (judged("N", {"mode": "golden", "error": "unparseable"}), "judge error: unparseable", 1.0),
        (judged("N", {"mode": "reference_free", "error": "TimeoutError"}), "judge error: TimeoutError", 1.0),
        (judged("C", {"mode": "golden"}), None, 0.0),
        (judged("I", {"mode": "golden"}), None, 0.0),
    ],
    ids=["unparseable", "failed-call", "judge-pass", "judge-fail"],
)
def test_a_judge_error_epoch_is_the_case_error_and_counts_in_the_error_rate(tmp_path, epoch, error, error_rate):
    # Witnesses: "s31 compare ignores judge errors" (return agent) fails unparseable and failed-call; "s31 judge_error
    # counts incorrect" fails judge-fail.
    results = load_results(write_epoch_log(tmp_path, [epoch]), min_case_pass_rate=0.0)

    assert (results.cases["add"].error, results.error_rate) == (error, error_rate)


@pytest.mark.parametrize(
    "judge",
    [("N", {"mode": "golden", "error": "unparseable"}), ("I", {"mode": "golden", "not_judged": "agent_error"})],
    ids=["judge-error-too", "not-judged-control"],
)
def test_an_agent_error_is_the_case_error_ahead_of_any_judge_error(tmp_path, judge):
    # The real judge never scores N after an agent error; judge-error-too is a hand-built log that has both.
    # not-judged-control is the shape the judge does record, which must give the agent's error alone.
    # Witness: "s31 compare judge_error first" (judge error/...) or agent) fails judge-error-too.
    path = write_epoch_log(tmp_path, [judged(*judge, error="RuntimeError: boom")])

    results = load_results(path, min_case_pass_rate=0.0)

    assert (results.cases["add"].error, results.error_rate) == ("RuntimeError: boom", 1.0)


def test_a_case_with_judge_errors_in_later_epochs_errors_once_with_the_first(tmp_path):
    # Witnesses: "first error kept" (errors[-1]) gives the TimeoutError; "s31 compare ignores judge errors" gives None.
    path = write_epoch_log(
        tmp_path,
        [
            judged("C", {"mode": "golden"}),
            judged("N", {"mode": "golden", "error": "unparseable"}),
            judged("N", {"mode": "golden", "error": "TimeoutError"}),
        ],
    )

    results = load_results(path, min_case_pass_rate=0.0)

    assert (results.cases["add"].runs, results.cases["add"].error) == (3, "judge error: unparseable")



def test_a_judge_fail_verdict_still_fails_its_epoch_and_a_judge_error_still_counts_as_an_error(tmp_path):
    # Deliberately unchanged by the judge report: verdicts still feed pass/fail through _sample_failures and
    # judge errors still feed the error rate through _epoch_error. Case checks pass in every epoch here.
    # Witness: "s32 sample failures skip judge" (ignore the judge score) passes all three epochs; "s31 compare
    # ignores judge errors" leaves the error None.
    path = write_epoch_log(
        tmp_path,
        [
            judged("C", {"mode": "golden"}),
            judged("I", {"mode": "golden"}),
            judged("N", {"mode": "golden", "error": "unparseable"}),
        ],
    )

    results = load_results(path, min_case_pass_rate=0.0)

    case = results.cases["add"]
    assert (case.runs, case.passes, case.failures) == (3, 1, {"judge": "judge"})
    assert (case.error, results.error_rate) == ("judge error: unparseable", 1.0)


def test_load_results_judge_is_empty_for_an_unjudged_run():
    # Witness: "s32 judged no-judge guard dropped" gives a not-judged epoch for each of the fixture's samples.
    results = load_results(FIXTURES / "calculator_capture_content.json")

    assert len(results.cases) == 10
    assert results.judge == ()


def test_load_results_judge_holds_every_case_epoch_of_a_judged_run(tmp_path):
    # Witness: "s32 load_results judge dropped" (judge=()) leaves the run with no judge epochs.
    path = write_epoch_log(
        tmp_path,
        [
            judged("C", {"mode": "golden", "judge_model": "m", "human_label": "fail"}),
            judged("I", {"mode": "reference_free", "judge_model": "m", "criteria": {"tone": False}}),
        ],
    )

    assert load_results(path).judge == (
        JudgedEpoch("add", "pass", "golden", "m", (), "fail"),
        JudgedEpoch("add", "fail", "reference_free", "m", (("tone", False),)),
    )


def test_case_latency_is_the_median_across_epochs(tmp_path):
    # Median 2 differs from the first (10), the last (1) and the mean (13/3).
    path = write_epoch_log(
        tmp_path,
        [
            {**PASS, "latency": 10.0},
            {**PASS, "latency": 2.0},
            {**PASS, "latency": 1.0},
        ],
    )

    assert load_results(path).cases["add"].latency_s == pytest.approx(2.0)


def test_case_epochs_hold_one_entry_per_epoch_in_epoch_order(tmp_path):
    # Each epoch keeps its own latency and its own failing scorers, so a reorder, a drop or the case-level first
    # failure repeated across epochs all show.
    # Witness: s22 case epochs reversed, s22 case epochs use first epoch failures.
    path = write_epoch_log(
        tmp_path,
        [
            {**PASS, "latency": 3.0},
            {**fail(), "latency": 1.0},
            {"scores": {"case_checks": (CORRECT, "ok"), "extra": (INCORRECT, "no")}, "latency": 2.0},
        ],
    )

    epochs = load_results(path).cases["add"].epochs

    assert [(e.latency_s, e.failed_checks) for e in epochs] == [
        (3.0, ()),
        (1.0, ("case_checks",)),
        (2.0, ("extra",)),
    ]


def test_case_failures_are_the_reasons_of_the_first_failing_epoch(tmp_path):
    path = write_epoch_log(
        tmp_path,
        [PASS, fail("first reason"), PASS, fail("second reason")],
    )

    case = load_results(path, min_case_pass_rate=0.0).cases["add"]

    assert case.failures == {"case_checks": "first reason"}


def test_case_failures_are_empty_when_every_epoch_passed(tmp_path):
    path = write_epoch_log(tmp_path, [PASS, PASS, PASS])

    assert load_results(path).cases["add"].failures == {}


@pytest.mark.parametrize(
    ("runs", "passes", "flaky"),
    [(4, 2, True), (4, 1, True), (4, 3, True), (4, 4, False), (4, 0, False), (1, 1, False), (1, 0, False)],
    ids=["half", "one", "all-but-one", "all-pass", "all-fail", "single-pass", "single-fail"],
)
def test_case_is_flaky_only_when_some_but_not_all_epochs_passed(runs, passes, flaky):
    case = CaseResult(
        id="case",
        passed=passes == runs,
        error=None,
        latency_s=None,
        failures={},
        runs=runs,
        passes=passes,
    )

    assert case.flaky is flaky


def test_case_result_defaults_to_one_run_and_no_passes():
    case = make_case("case")

    assert case.runs == 1
    assert case.passes == 0
    assert not case.flaky


def test_load_results_marks_mixed_epochs_flaky_and_uniform_epochs_not(tmp_path):
    mixed = load_results(write_epoch_log(tmp_path / "mixed", [PASS, fail(), PASS]))
    uniform = load_results(write_epoch_log(tmp_path / "uniform", [fail(), fail()]))

    assert mixed.cases["add"].flaky
    assert not uniform.cases["add"].flaky


def make_epoch_case(case_id, *, runs, passes):
    return CaseResult(
        id=case_id,
        passed=passes == runs,
        error=None,
        latency_s=None,
        failures={},
        runs=runs,
        passes=passes,
    )


def test_flaky_current_cases_are_a_sorted_warning_and_not_a_regression():
    baseline = make_run(
        {case_id: make_epoch_case(case_id, runs=4, passes=2) for case_id in ("zulu", "alpha", "steady")},
        dataset_sha256="same",
    )
    current = make_run(
        {
            "zulu": make_epoch_case("zulu", runs=4, passes=3),
            "alpha": make_epoch_case("alpha", runs=4, passes=1),
            "steady": make_epoch_case("steady", runs=4, passes=0),
        },
        dataset_sha256="same",
    )

    result = compare(baseline, current, Thresholds())

    assert not result.regressed
    flaky_warnings = [w for w in result.warnings if "alpha" in w or "zulu" in w]
    assert len(flaky_warnings) == 1
    warning = flaky_warnings[0]
    assert "steady" not in warning
    assert warning.index("alpha") < warning.index("zulu")


def test_no_flaky_warning_when_no_current_case_is_flaky():
    baseline = make_run(
        {
            "stable": make_epoch_case("stable", runs=4, passes=4),
            "broken": make_epoch_case("broken", runs=4, passes=0),
        },
        dataset_sha256="same",
    )
    current = make_run(
        {
            "stable": make_epoch_case("stable", runs=4, passes=4),
            "broken": make_epoch_case("broken", runs=4, passes=0),
        },
        dataset_sha256="same",
    )

    result = compare(baseline, current, Thresholds())

    assert not any("stable" in w or "broken" in w for w in result.warnings)
    assert result.warnings == []


CAPTURE_WARNING = "{side} log was made with --capture-content and contains unredacted content; do not commit it"
_ABSENT = object()


def write_capture_metadata_log(tmp_path, value):
    """Writes the capture fixture with its capture_content metadata set to value, or removed for _ABSENT."""
    log = read_eval_log(FIXTURES / "calculator_capture_content.json")
    metadata = dict(log.eval.metadata or {})
    metadata.pop("capture_content", None)
    if value is not _ABSENT:
        metadata["capture_content"] = value
    log.eval.metadata = metadata
    path = tmp_path / "capture-metadata.json"
    write_eval_log(log, location=path)
    return path


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [("calculator_capture_content.json", True), ("calculator_broken_redacted.json", False)],
)
def test_load_results_reads_capture_content_from_fixture_metadata(fixture, expected):
    assert load_results(FIXTURES / fixture).capture_content is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (False, False), (_ABSENT, False), ("true", False), (1, False)],
)
def test_load_results_capture_content_is_true_only_for_a_literal_true(tmp_path, value, expected):
    assert load_results(write_capture_metadata_log(tmp_path, value)).capture_content is expected


def test_run_results_capture_content_defaults_to_false():
    run = RunResults(run_id="run", log_path=Path("run.json"), dataset_sha256=None, status="success", cases={})

    assert run.capture_content is False


@pytest.mark.parametrize(
    ("baseline_captured", "current_captured", "expected"),
    [
        (False, False, []),
        (True, False, [CAPTURE_WARNING.format(side="baseline")]),
        (False, True, [CAPTURE_WARNING.format(side="current")]),
        (True, True, [CAPTURE_WARNING.format(side="baseline"), CAPTURE_WARNING.format(side="current")]),
    ],
)
def test_compare_warns_about_capture_content(baseline_captured, current_captured, expected):
    cases = {"add": make_case("add")}
    baseline = make_run(cases, dataset_sha256="same", capture_content=baseline_captured)
    current = make_run(cases, dataset_sha256="same", capture_content=current_captured)

    result = compare(baseline, current, Thresholds())

    assert result.warnings == expected
    assert result.regressions == []
    assert not result.regressed


def test_capture_warning_does_not_change_an_existing_regression():
    baseline_cases = {"add": make_case("add", passed=True)}
    current_cases = {"add": make_case("add", passed=False)}

    plain = compare(make_run(baseline_cases), make_run(current_cases), Thresholds())
    captured = compare(
        make_run(baseline_cases, capture_content=True),
        make_run(current_cases, capture_content=True),
        Thresholds(),
    )

    assert captured.regressed is plain.regressed is True
    assert captured.regressions == plain.regressions


def test_capture_warning_renders_as_a_warning_line():
    cases = {"add": make_case("add")}
    result = compare(make_run(cases), make_run(cases, capture_content=True), Thresholds())

    lines = render_comparison(result).splitlines()

    assert f"- Warning: {CAPTURE_WARNING.format(side='current')}" in lines
    assert f"- Warning: {CAPTURE_WARNING.format(side='baseline')}" not in lines
    assert "**OK**" in lines


@pytest.mark.parametrize(
    ("baseline", "current", "exit_code", "warned_sides"),
    [
        ("calculator_capture_content.json", "calculator_capture_content.json", 0, ["baseline", "current"]),
        ("calculator_broken_redacted.json", "calculator_capture_content.json", 0, ["current"]),
        ("calculator_capture_content.json", "calculator_broken_redacted.json", 1, ["baseline"]),
    ],
)
def test_cli_compare_exit_code_ignores_capture_warning(monkeypatch, capsys, baseline, current, exit_code, warned_sides
):
    monkeypatch.setattr(sys, "path", [*sys.path])  # main prepends the working directory

    code = main(["compare", str(FIXTURES / baseline), str(FIXTURES / current)])

    lines = capsys.readouterr().out.splitlines()
    assert code == exit_code
    warnings = [line for line in lines if "--capture-content" in line]
    assert warnings == [f"- Warning: {CAPTURE_WARNING.format(side=side)}" for side in warned_sides]

def test_failing_score_without_explanation_is_reported_as_scorer_name_failed(tmp_path):
    path = write_epoch_log(
        tmp_path, [{"scores": {"case_checks": (CORRECT, "all checks passed"), "no_jargon": (INCORRECT, None)}}]
    )

    assert load_results(path).cases["add"].failures == {"no_jargon": "no_jargon failed"}


def test_failing_score_with_explanation_keeps_the_explanation(tmp_path):
    path = write_epoch_log(
        tmp_path,
        [{"scores": {"case_checks": (CORRECT, "all checks passed"), "no_jargon": (INCORRECT, "said adstock")}}],
    )

    assert load_results(path).cases["add"].failures == {"no_jargon": "said adstock"}


def write_tool_count_log(tmp_path, epochs):
    """One epoch per entry; each entry maps scorer name -> tool_call_count (_ABSENT leaves the key out)."""
    path = write_epoch_log(
        tmp_path, [{"scores": dict.fromkeys(epoch, (CORRECT, "all checks passed"))} for epoch in epochs]
    )
    log = read_eval_log(path)
    for sample, epoch in zip(log.samples, epochs, strict=True):
        for name, count in epoch.items():
            sample.scores[name].metadata = {"checks": {}} | ({} if count is _ABSENT else {"tool_call_count": count})
    write_eval_log(log, location=path)
    return path


@pytest.mark.parametrize(
    ("epochs", "expected"),
    [
        ([{"case_checks": 1}, {"case_checks": 2}], 1.5),
        ([{"case_checks": 2}, {"case_checks": None}, {"case_checks": _ABSENT}, {"case_checks": 4}], 3.0),
        ([{"case_checks": 0}, {"case_checks": 0}], 0.0),
    ],
    ids=["mean-of-one-and-two", "unrecorded-epochs-skipped-not-zero", "recorded-zero-is-zero"],
)
def test_case_tool_calls_are_the_mean_over_epochs_that_recorded_a_count(tmp_path, epochs, expected):
    # Witnesses: s16 mean integer division gives 1 for mean-of-one-and-two; s16 mean counts None as zero gives
    # 1.5 for unrecorded-epochs-skipped-not-zero.
    assert load_results(write_tool_count_log(tmp_path, epochs)).cases["add"].tool_calls == expected


@pytest.mark.parametrize(
    "epochs",
    [
        [{"case_checks": _ABSENT}, {"case_checks": None}],
        [{"case_checks": _ABSENT, "no_jargon": 5}],
    ],
    ids=["no-epoch-recorded", "only-another-scorer-recorded"],
)
def test_case_tool_calls_are_none_when_no_epoch_recorded_a_case_checks_count(tmp_path, epochs):
    # Witness: s16 mean reads any scorer (every score's metadata, not only case_checks) gives 5.0.
    assert load_results(write_tool_count_log(tmp_path, epochs)).cases["add"].tool_calls is None


def test_case_tool_use_aggregates_every_epoch_not_only_the_first(tmp_path):
    # Witness: s24 load_results tool use reads the first epoch only (`for s in samples[:1]`) gives calls_per_epoch
    # (1,) and the first epoch's counts alone.
    # Expected by hand: calls 1 and 3; add 1 + 2 = 3, multiply 1; results 1 + 3 = 4; errors 0 + 1; redundant 0 + 1;
    # precision mean of 1.0 and 0.5 = 0.75; recall 1.0 in both epochs.
    epochs = [
        {
            "tool_names": ["add"],
            "tool_results": 1,
            "tool_errors": 0,
            "redundant_tool_calls": 0,
            "tool_precision": 1.0,
            "tool_recall": 1.0,
        },
        {
            "tool_names": ["add", "add", "multiply"],
            "tool_results": 3,
            "tool_errors": 1,
            "redundant_tool_calls": 1,
            "tool_precision": 0.5,
            "tool_recall": 1.0,
        },
    ]
    path = write_epoch_log(tmp_path, [PASS] * len(epochs))
    log = read_eval_log(path)
    for sample, metadata in zip(log.samples, epochs, strict=True):
        sample.scores["case_checks"].metadata = {"checks": {}} | metadata
    write_eval_log(log, location=path)

    assert load_results(path).cases["add"].tool_use == CaseToolUse(
        calls_per_epoch=(1, 3),
        by_tool={"add": 3, "multiply": 1},
        results=4,
        errors=1,
        redundant=1,
        precision=0.75,
        recall=1.0,
    )


def test_logs_from_before_tool_call_counts_load_with_none():
    # Witness: s16 mean counts None as zero gives 0.0 for every fixture case.
    cases = load_results(FIXTURES / "calculator_capture_content.json").cases

    assert len(cases) == 10
    assert {case.tool_calls for case in cases.values()} == {None}


# One-sided Fisher significance of a fall in pass share. Expected p-values are hypergeometric tails worked by
# hand: 3/3 -> 0/3 is 1/C(6,3) = 0.05, 5/5 -> 0/3 is 1/C(8,3) = 0.018, 10/10 -> 0/10 is 1/C(20,10).

SIGNIFICANT = "pass rate fell significantly (one-sided Fisher p <= 0.05): "
NOT_APPLIED = "--max-p-value not applied: needs more than one epoch per case in both runs"
# Existing gates opened wide, so any regression comes from the significance gate alone.
LENIENT = {"max_new_failures": 100, "max_pass_rate_drop": 1.0}


def fisher_pair(counts, *, baseline_only=(), current_only=()):
    """Baseline and current runs from {case_id: ((passes, epochs) before, (passes, epochs) after)}."""
    baseline = {c: make_epoch_case(c, runs=b[1], passes=b[0]) for c, (b, _) in counts.items()}
    current = {c: make_epoch_case(c, runs=a[1], passes=a[0]) for c, (_, a) in counts.items()}
    baseline |= {c: make_epoch_case(c, runs=3, passes=3) for c in baseline_only}
    current |= {c: make_epoch_case(c, runs=3, passes=0) for c in current_only}
    return make_run(baseline, dataset_sha256="same"), make_run(current, dataset_sha256="same")


def significance_warnings(result):
    return [w for w in result.warnings if w.startswith("pass rate fell")]


# Ten cases at 5/5 before; two broken to 0/3 after, the rest 3/3. Dict order puts "subtract" before "divide",
# so a listing in insertion order differs from a sorted one.
DEMO_IDS = ["add", "subtract", "multiply", "power", "divide", "modulo", "negate", "square", "root", "abs"]
DEMO = {c: ((5, 5), (0, 3) if c in ("subtract", "divide") else (3, 3)) for c in DEMO_IDS}
DEMO_ENTRIES = [
    "divide (5/5 -> 0/3, p=0.018)",
    "subtract (5/5 -> 0/3, p=0.018)",
    # all six failures fall in the current run: C(74,24) / C(80,30) = 0.00198
    "all 10 shared cases pooled (50/50 -> 24/30, p=0.002)",
]


def test_case_falling_3_of_3_to_0_of_3_is_flagged_at_p_exactly_alpha_without_regressing_by_default():
    # Witness: "s20 warn alpha strict", "s20 pooled single case", "s20 gate on by default",
    # "s20 significance not run".
    result = compare(*fisher_pair({"add": ((3, 3), (0, 3))}), Thresholds(**LENIENT))

    assert result.warnings == [SIGNIFICANT + "add (3/3 -> 0/3, p=0.050)"]
    assert result.regressions == []


def test_demo_warning_lists_failing_cases_sorted_then_the_pooled_test_last():
    # Witness: "s20 cases unsorted", "s20 pooled first", "s20 warn alpha".
    result = compare(*fisher_pair(DEMO), Thresholds(**LENIENT))

    assert result.warnings == [SIGNIFICANT + ", ".join(DEMO_ENTRIES)]
    assert result.regressions == []


def test_pooled_test_can_flag_a_fall_no_single_case_shows_and_counts_shared_cases_only():
    # Witness: "s20 pooled count all current". Each case 3/3 -> 2/3 has p = 10/20 = 0.5; pooled 12/12 -> 8/12
    # puts all four failures in the current run; C(20,8) / C(24,12) = 0.0466. Counting the added and removed
    # cases would change both the tallies and the case count.
    pair = fisher_pair(
        {c: ((3, 3), (2, 3)) for c in ("a", "b", "c", "d")}, baseline_only=["removed"], current_only=["added"]
    )

    result = compare(*pair, Thresholds(**LENIENT))

    assert significance_warnings(result) == [SIGNIFICANT + "all 4 shared cases pooled (12/12 -> 8/12, p=0.047)"]


@pytest.mark.parametrize(
    ("before", "after", "regressed"),
    [
        pytest.param((2, 4), (1, 2), False, id="equal-share"),  # p = 12/15 = 0.8 if it were tested
        pytest.param((1, 4), (2, 4), False, id="rising-share"),  # p = 65/70 = 0.929 if it were tested
        pytest.param((3, 4), (2, 4), True, id="falling-share-control"),  # p = 35/70 = 0.5
    ],
)
def test_only_a_case_whose_pass_share_fell_is_tested(before, after, regressed):
    # Witness: "s20 equal shares tested" (equal-share), "s20 rising case tested" (rising-share).
    result = compare(*fisher_pair({"add": (before, after)}), Thresholds(**LENIENT, max_p_value=0.99))

    assert result.regressed is regressed
    assert significance_warnings(result) == []


def test_pooled_epochs_are_not_tested_when_the_pooled_share_did_not_fall():
    # Witness: "s20 pooled rise tested". Pooled 3/8 -> 3/6 rose; its p would be 2534/3003 = 0.844.
    pair = fisher_pair({"equal": ((2, 4), (1, 2)), "rising": ((1, 4), (2, 4))})

    result = compare(*pair, Thresholds(**LENIENT, max_p_value=0.99))

    assert result.regressions == []
    assert significance_warnings(result) == []


def test_max_p_value_regresses_only_entries_at_or_below_it_while_the_warning_stays_at_005():
    # Witness: "s20 gate ignores flag" (the cases at 0.018 regress), "s20 warning follows flag" (the warning
    # loses the cases), "s20 gate is a warning".
    result = compare(*fisher_pair(DEMO), Thresholds(**LENIENT, max_p_value=0.01))

    assert result.warnings == [SIGNIFICANT + ", ".join(DEMO_ENTRIES)]
    [regression] = result.regressions
    assert regression.startswith("pass rate fell")
    assert regression.endswith(": " + DEMO_ENTRIES[-1])


@pytest.mark.parametrize(
    ("max_p_value", "regressed"),
    [pytest.param(0.05, True, id="p-equals-alpha"), pytest.param(0.04, False, id="p-above-alpha")],
)
def test_max_p_value_counts_a_p_value_equal_to_it(max_p_value, regressed):
    # Witness: "s20 gate alpha strict" (p-equals-alpha), "s20 gate tolerance wide" (p-above-alpha).
    result = compare(*fisher_pair({"add": ((3, 3), (0, 3))}), Thresholds(**LENIENT, max_p_value=max_p_value))

    assert result.regressed is regressed


def test_p_value_below_one_in_a_thousand_is_shown_as_a_bound():
    # Witness: "s20 tiny p shown as zero". p = 1/C(20,10) = 1/184756.
    result = compare(*fisher_pair({"add": ((10, 10), (0, 10))}), Thresholds(**LENIENT))

    assert result.warnings == [SIGNIFICANT + "add (10/10 -> 0/10, p<0.001)"]



# Pooled 2/2 -> 0/20 and 20/20 -> 0/2 both have p = 1/231, so any test that ran would warn and regress.
@pytest.mark.parametrize(
    "counts",
    [
        pytest.param({c: ((1, 1), (0, 10)) for c in "ab"}, id="baseline-single-epoch"),
        pytest.param({c: ((10, 10), (0, 1)) for c in "ab"}, id="current-single-epoch"),
    ],
)
@pytest.mark.parametrize("max_p_value", [pytest.param(None, id="no-flag"), pytest.param(0.05, id="flag")])
def test_no_test_runs_when_one_side_has_a_single_epoch_for_every_shared_case(counts, max_p_value):
    # Witness: "s20 baseline single epoch tested", "s20 current single epoch tested", "s20 skip warning dropped"
    # (flag ids) and "s20 skip warning without flag" (no-flag ids).
    result = compare(*fisher_pair(counts), Thresholds(**LENIENT, max_p_value=max_p_value))

    assert result.regressions == []
    assert result.warnings == ([] if max_p_value is None else [NOT_APPLIED])


@pytest.mark.parametrize("max_p_value", [pytest.param(None, id="no-flag"), pytest.param(0.05, id="flag")])
def test_no_shared_cases_runs_no_test_and_warns_not_applied_only_when_the_flag_is_set(max_p_value):
    # Witness: "s20 skip warning dropped" (flag), "s20 skip warning without flag" (no-flag).
    pair = fisher_pair({}, baseline_only=["old"], current_only=["new"])

    result = compare(*pair, Thresholds(**LENIENT, max_p_value=max_p_value))

    assert result.regressions == []
    assert (NOT_APPLIED in result.warnings) is (max_p_value is not None)
    assert significance_warnings(result) == []

def test_tests_run_when_only_some_shared_cases_have_a_single_epoch():
    # Witness: "s20 any single epoch skips". a: 1/1 -> 0/3 has p = 1/C(4,3) = 0.25, so it is not listed;
    # b: 0.05; pooled 4/4 -> 0/6 has p = 1/C(10,6) = 0.0048.
    result = compare(*fisher_pair({"a": ((1, 1), (0, 3)), "b": ((3, 3), (0, 3))}), Thresholds(**LENIENT))

    entries = "b (3/3 -> 0/3, p=0.050), all 2 shared cases pooled (4/4 -> 0/6, p=0.005)"
    assert result.warnings == [SIGNIFICANT + entries]


@pytest.mark.parametrize(
    ("flags", "exit_code"),
    [pytest.param([], 0, id="default"), pytest.param(["--max-p-value", "0.05"], 1, id="max-p-value")],
)
def test_cli_compare_max_p_value_turns_the_significance_warning_into_a_regression(
    monkeypatch, capsys, tmp_path, flags, exit_code
):
    # Witness: "s20 p value not passed" (max-p-value), "s20 p value default on" (default).
    monkeypatch.setattr(sys, "path", [*sys.path])  # main prepends the working directory
    baseline = write_epoch_log(tmp_path / "baseline", [PASS, PASS, PASS])
    current = write_epoch_log(tmp_path / "current", [fail(), fail(), fail()])
    lenient = ["--max-new-failures", "1", "--max-pass-rate-drop", "1"]

    code = main(["compare", str(baseline), str(current), *lenient, *flags])

    lines = capsys.readouterr().out.splitlines()
    entry = "add (3/3 -> 0/3, p=0.050)"
    regressions = [line for line in lines if line.startswith("- Regression:")]
    assert code == exit_code
    assert f"- Warning: {SIGNIFICANT}{entry}" in lines
    assert len(regressions) == (1 if flags else 0)
    assert all(line.startswith("- Regression: pass rate fell") and line.endswith(entry) for line in regressions)



@pytest.mark.parametrize(
    "settings",
    [
        {"max_new_failures": -1},
        {"max_new_failures": 0.25},
        {"max_pass_rate_drop": -0.1},
        {"max_pass_rate_drop": 1.1},
        {"max_pass_rate_drop": float("nan")},
        {"max_pass_rate_drop": float("inf")},
        {"max_error_rate_increase": -0.1},
        {"max_error_rate_increase": 1.1},
        {"max_error_rate_increase": float("nan")},
        {"max_p_value": 0.0},
        {"max_p_value": 1.0},
        {"max_p_value": float("nan")},
    ],
)
def test_thresholds_reject_invalid_direct_api_settings(settings):
    with pytest.raises(ValueError):
        Thresholds(**settings)


@pytest.mark.parametrize("rate", [-0.01, 1.01, float("nan"), float("inf")])
def test_load_results_rejects_invalid_pass_rate_before_reading_log(rate, tmp_path):
    with pytest.raises(ValueError, match="min_case_pass_rate"):
        load_results(tmp_path / "missing.json", min_case_pass_rate=rate)
