import inspect
from pathlib import Path

import pytest

from agent_accelerator import readings
from agent_accelerator.compare import (
    CaseResult,
    Comparison,
    MedianChange,
    RateInterval,
    RunResults,
    Statistics,
    Thresholds,
    compare,
)
from agent_accelerator.judge import JudgedEpoch
from agent_accelerator.report import _sections, render_comparison, render_run
from agent_accelerator.run_metrics import EpochMetrics
from agent_accelerator.tool_metrics import CaseToolUse
from agent_accelerator.trace_summary import TraceSummary

# Wilson bounds quoted below are hand-derived with z^2 = 3.8415: at 0/n the upper bound is z^2 / (n + z^2), at n/n
# the lower bound is n / (n + z^2), and at 1/2 the interval is 0.5 +- 0.4055.
# Test parameters never say `runs`: tests/conftest.py marks any test with a `runs` argument as slow.

GLOSSARY_HEADING = "## How to read this report"


# TODO: run_of and the case builders overlap tests/unit/test_report.py; move to a shared helper when that file settles.
def epoch(*failed, latency_s=None, digest=None):
    return EpochMetrics(
        latency_s=latency_s, input_tokens=None, output_tokens=None, failed_checks=failed, output_digest=digest
    )


def case(case_id, passes=1, epochs=1, *, error=None, latency_s=None, per_epoch=(), tool_use=None):
    passed = passes == epochs and error is None
    return CaseResult(
        id=case_id,
        passed=passed,
        error=error,
        latency_s=latency_s,
        failures={} if passed else {"check": "failed"},
        runs=epochs,
        passes=passes,
        epochs=tuple(per_epoch),
        tool_use=tool_use,
    )


def run_of(*cases, status="success"):
    return RunResults(
        run_id="run",
        log_path=Path("run.json"),
        dataset_sha256=None,
        status=status,
        cases={c.id: c for c in cases},
    )


def tools(*, errors=0, redundant=0, results=1, precision=None, recall=None):
    return CaseToolUse(
        calls_per_epoch=(1,),
        by_tool={"lookup": 1},
        results=results,
        errors=errors,
        redundant=redundant,
        precision=precision,
        recall=recall,
    )


def paragraph(run):
    lines = readings.summary_lines(run)
    assert len(lines) == 4
    return lines[2]


def matching(found, marker):
    return [r for r in found if marker in r]


# Counted nouns


@pytest.mark.parametrize(
    ("n", "singular", "plural", "expected"),
    [
        (0, "epoch", "epochs", "0 epochs"),
        (1, "epoch", "epochs", "1 epoch"),
        (2, "epoch", "epochs", "2 epochs"),
        (0, "try", "tries", "0 tries"),
        (1, "try", "tries", "1 try"),
        (2, "try", "tries", "2 tries"),
    ],
    ids=["zero-epochs", "one-epoch", "two-epochs", "zero-tries", "one-try", "two-tries"],
)
def test_counted_uses_the_singular_only_for_exactly_one(n, singular, plural, expected):
    # Witnesses: s30 counted singular at zero (`n == 1` to `n <= 1`, the zero cases fail); s30 counted singular from
    # one up (`n == 1` to `n >= 1`, the two cases fail); s30 counted nouns swapped (every case fails).
    assert readings.counted(n, singular, plural) == expected


# Summary


def test_summary_is_a_heading_a_blank_one_paragraph_and_a_blank():
    # Witness: s26 summary sentences joined by newline; the paragraph then spans lines and this test fails.
    run = run_of(case("a"), case("b", passes=0, latency_s=1.0), case("c", latency_s=2.0))

    lines = readings.summary_lines(run)

    assert lines == ["## Summary", "", lines[2], ""]
    assert lines[2] == "2 of 3 cases passed (67%). Failed: b. The slowest case is c at 2.000s."


def test_summary_says_no_cases_ran_for_an_empty_run():
    # Witness: s26 summary empty guard dropped; min() of no cases then raises.
    assert readings.summary_lines(run_of()) == ["## Summary", "", "No cases ran.", ""]


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        ([case("a", 3, 3), case("b", 3, 3)], "2 of 2 cases passed (100%), each run 3 times."),
        ([case("a", 2, 2), case("b", 3, 3)], "2 of 2 cases passed (100%), each run 2 to 3 times."),
        ([case("a", 1, 1), case("b", 3, 3)], "2 of 2 cases passed (100%), each run 1 to 3 times."),
        ([case("a"), case("b")], "2 of 2 cases passed (100%)."),
    ],
    ids=["same-epochs", "differing-epochs", "one-and-three-epochs", "one-epoch"],
)
def test_summary_overall_sentence_names_the_epochs_only_when_some_case_ran_more_than_once(cases, expected):
    # Witnesses: s26 summary epochs said at one epoch (`most == 1` to `most == 0`); s26 summary epoch range
    # always single (`fewest == most` to `True`); s26 summary one-epoch test uses fewest.
    assert paragraph(run_of(*cases)) == expected


def test_summary_overall_sentence_counts_cases_that_ended_with_an_error():
    # Witness: s26 summary error count dropped (`if errored` to `if False`).
    run = run_of(case("a", passes=0, error="boom"), case("b"))

    assert paragraph(run) == "1 of 2 cases passed (50%), and 1 ended with an error. Failed: a."


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("error", "The run ended with status 'error', so results may be incomplete. 1 of 1 cases passed (100%)."),
        ("success", "1 of 1 cases passed (100%)."),
    ],
    ids=["not-success", "success"],
)
def test_summary_opens_with_the_status_only_when_the_run_did_not_succeed(status, expected):
    # Witness: s26 summary status check inverted; s26 summary status check dropped.
    assert paragraph(run_of(case("a"), status=status)) == expected


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        (
            [case("a", 1, 3), case("b", 0, 3), case("c", 3, 3)],
            "1 of 3 cases passed (33%), each run 3 times. "
            "Flaky (passed some epochs but not all): a (1/3); failed every epoch: b.",
        ),
        ([case("a", 0, 1), case("b")], "1 of 2 cases passed (50%). Failed: a."),
        ([case("a", 0, 2), case("b")], "1 of 2 cases passed (50%), each run 1 to 2 times. Failed every epoch: a."),
        (
            [case("a", 1, 2), case("b", 2, 2)],
            "1 of 2 cases passed (50%), each run 2 times. Flaky (passed some epochs but not all): a (1/2).",
        ),
        # The label reads the never-passed cases only: twice ran two epochs but passed, so solo is just "Failed".
        (
            [case("solo", 0, 1), case("twice", 2, 2)],
            "1 of 2 cases passed (50%), each run 1 to 2 times. Failed: solo.",
        ),
        (
            [case("solo", 0, 1), case("twice", 0, 2)],
            "0 of 2 cases passed (0%), each run 1 to 2 times. Never passed: solo and twice.",
        ),
        (
            [case("multi", 1, 2), case("solo", 0, 1)],
            "0 of 2 cases passed (0%), each run 1 to 2 times. "
            "Flaky (passed some epochs but not all): multi (1/2); failed: solo.",
        ),
    ],
    ids=[
        "flaky-then-never",
        "never-every-case-once",
        "never-some-case-more",
        "flaky-only",
        "never-once-beside-a-passing-multi-epoch-case",
        "never-passed-once-and-every-epoch",
        "flaky-then-failed-once",
    ],
)
def test_summary_names_flaky_then_never_passed_cases_with_the_label_set_by_the_epochs(cases, expected):
    # Witnesses: s29 summary label from every case (`for c in never_cases` to `for c in cases` in the "Failed" test);
    # s29 summary failed label any; s29 summary every-epoch label any; s29 summary mixed label ("Never passed" to
    # "Failed"); s29 summary label not lowercased; s26 summary never before flaky; s26 summary first letter not
    # capitalised; s26 summary flaky omitted.
    assert paragraph(run_of(*cases)) == expected


@pytest.mark.parametrize(
    ("cases", "sentence"),
    [
        (
            # x fails in both epochs of a and the first of b: 3 of 4 tries across 2 cases; y once.
            [
                case("a", 0, 2, per_epoch=[epoch("x"), epoch("x")]),
                case("b", 1, 2, per_epoch=[epoch("x", "y"), epoch()]),
            ],
            "The most common failing check is x, failing in 3 of 4 tries across 2 case(s).",
        ),
        (
            [case("a", 0, 2, per_epoch=[epoch("x"), epoch("y")])],
            "The most common failing checks are x and y, each failing in 1 of 2 tries.",
        ),
    ],
    ids=["single", "tie"],
)
def test_summary_names_the_most_common_failing_check_or_the_tied_checks_over_all_tries(cases, sentence):
    # Witnesses: s26 top checks tie only first; s29 summary tie branch off by one (`> 1` to `> 2` in _check_sentence);
    # s26 summary tries counted per case.
    assert paragraph(run_of(*cases)).endswith(sentence)


@pytest.mark.parametrize(
    ("cases", "sentence"),
    [
        (
            [case("a", 2, 2, tool_use=tools(errors=2)), case("b", 2, 2)],
            "2 tool call(s) returned an error, in a (2); that case still passed every time, so the errors may be "
            "expected.",
        ),
        (
            [case("a", tool_use=tools(errors=1)), case("b", tool_use=tools(errors=3))],
            "4 tool call(s) returned an error, in a (1) and b (3); those cases still passed every time, so the "
            "errors may be expected.",
        ),
        ([case("a", 0, 1, tool_use=tools(errors=1))], "1 tool call(s) returned an error, in a (1)."),
        (
            [case("a", tool_use=tools(errors=1)), case("b", 0, 1, tool_use=tools(errors=2))],
            "3 tool call(s) returned an error, in a (1) and b (2).",
        ),
    ],
    ids=["one-passing-case", "two-passing-cases", "failing-case", "passing-and-failing"],
)
def test_summary_tool_error_sentence_says_may_be_expected_only_when_every_erring_case_always_passed(cases, sentence):
    # Witnesses: s26 summary tool clause any instead of all; s26 summary tool that case for many; s26 summary tool
    # clause dropped.
    assert paragraph(run_of(*cases)).endswith(sentence)


def test_summary_has_no_tool_error_sentence_when_recorded_calls_had_no_errors():
    # Witness: s26 summary tool sentence without errors (`not use.errors` dropped).
    assert paragraph(run_of(case("a", tool_use=tools()))) == "1 of 1 cases passed (100%)."


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        (
            [case("b", latency_s=1.25), case("a", latency_s=0.5)],
            "2 of 2 cases passed (100%). The slowest case is b at 1.250s.",
        ),
        (
            [case("a", 2, 2, latency_s=0.5), case("b", 2, 2, latency_s=1.25)],
            "2 of 2 cases passed (100%), each run 2 times. The slowest case is b at 1.250s (median across its epochs).",
        ),
        (
            [case("b", latency_s=2.0), case("a", latency_s=2.0)],
            "2 of 2 cases passed (100%). The slowest case is a at 2.000s.",
        ),
        ([case("a", latency_s=0.5), case("b")], "2 of 2 cases passed (100%)."),
    ],
    ids=["single-epoch", "several-epochs", "tie-goes-to-lowest-id", "one-latency"],
)
def test_summary_names_the_slowest_case_only_when_two_cases_have_a_latency(cases, expected):
    # Witnesses: s26 summary slowest with one latency (`< 2` to `< 1`); s26 summary slowest tie to highest id;
    # s26 summary median note at one epoch; s26 summary slowest is fastest.
    assert paragraph(run_of(*cases)) == expected


# Readings: reliability


def test_reliability_reading_gives_each_flaky_case_its_wilson_range():
    # Witness: s26 reliability flaky range uses runs for passes: 1/2 is 0.5 +- 0.4055: 9% to 91%.
    found = readings.reliability_readings([case("a", 1, 2), case("b", 2, 2)], 2, 0.5, 0.5)

    assert matching(found, "true pass rate could be anywhere") == [
        "a passed 1 of 2; its true pass rate could be anywhere from 9% to 91%, so run more epochs to narrow it."
    ]


@pytest.mark.parametrize(
    ("flaky_count", "more"),
    [(5, []), (6, ["1 more flaky case(s) read the same way; see the table."])],
    ids=["five", "six"],
)
def test_reliability_names_at_most_five_flaky_cases_then_counts_the_rest(flaky_count, more):
    # Witnesses: s26 reliability shown six; s26 reliability more at five (`>` to `>=`).
    cases = [case(f"c{i}", 1, 2) for i in range(1, flaky_count + 1)]

    found = readings.reliability_readings(cases, 2, 0.5, 0.5)

    named = matching(found, "true pass rate could be anywhere")
    assert [r.split()[0] for r in named] == ["c1", "c2", "c3", "c4", "c5"]
    assert matching(found, "more flaky case(s)") == more


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        # 0/3: 3.8415 / 6.8415 = 56%. The case that ran once is left out.
        (
            [case("a", 0, 1), case("b", 0, 3)],
            ["b failed every epoch; the true pass rate is probably no higher than 56%."],
        ),
        # 0/2 is 66% and 0/4 is 49%: the reading quotes the higher ceiling.
        (
            [case("b", 0, 2), case("c", 0, 4)],
            ["b and c failed every epoch; the true pass rate is probably no higher than 66%."],
        ),
        ([case("a", 0, 1), case("b", 1, 2)], []),
    ],
    ids=["once-skipped", "highest-ceiling", "only-ran-once"],
)
def test_reliability_never_passed_ceiling_only_for_cases_that_ran_more_than_once(cases, expected):
    # Witnesses: s26 reliability never includes single epoch; s26 reliability ceiling min.
    assert matching(readings.reliability_readings(cases, 1, 0.5, 0.5), "failed every epoch") == expected


@pytest.mark.parametrize(
    ("count", "names"),
    [
        (1, "n1"),
        (2, "n1 and n2"),
        (3, "n1, n2 and n3"),
        (5, "n1, n2, n3, n4 and n5"),
        (6, "n1, n2, n3, n4, n5 and 1 more"),
        (7, "n1, n2, n3, n4, n5 and 2 more"),
    ],
    ids=["one", "two", "three", "five", "six", "seven"],
)
def test_case_names_read_as_an_english_list_of_at_most_five_then_a_count(count, names):
    # Exercises _names through the never-passed reading, which passes it the bare ids.
    # Witnesses: s26 names and becomes comma; s26 names more at five; s26 names shown six; s26 names more count.
    cases = [case(f"n{i}", 0, 2) for i in range(1, count + 1)]

    found = readings.reliability_readings(cases, 2, 0.0, 0.0)

    assert matching(found, "failed every epoch") == [
        f"{names} failed every epoch; the true pass rate is probably no higher than 66%."
    ]


def test_reliability_floor_is_the_lowest_wilson_bound_of_the_always_passing_cases():
    # Witness: s26 reliability floor max. 2/2 is 2 / 5.8415 = 34%; 4/4 is 4 / 7.8415 = 51%.
    found = readings.reliability_readings([case("a", 2, 2), case("b", 4, 4), case("c", 0, 2)], 2, 0.5, 0.5)

    assert matching(found, "passed every epoch") == [
        "2 case(s) passed every epoch; even so, with this few tries their true pass rate could be as low as 34%."
    ]


def test_reliability_has_no_floor_reading_without_an_always_passing_case():
    # Witness: s26 reliability floor without solid cases; min() of nothing then raises.
    assert matching(readings.reliability_readings([case("a", 1, 2)], 2, 0.5, 0.5), "passed every epoch") == []


def gap_reading(points):
    return f"pass@2 is {points} above pass^2: retrying hides failures that a user with one attempt would see."


@pytest.mark.parametrize(
    ("at_k", "hat_k", "expected"),
    [
        # Points are the gap in percentage points rounded half up: 0.5 -> 1, 1.5 -> 2, 2.5 -> 3, 0.49 -> 0.
        (0.005, 0.0, [gap_reading("1 point")]),
        (0.505, 0.5, [gap_reading("1 point")]),
        (0.0049, 0.0, []),
        (0.504, 0.5, []),
        (0.015, 0.0, [gap_reading("2 points")]),
        (0.025, 0.0, [gap_reading("3 points")]),
        (0.5, 0.5, []),
        (0.4, 0.5, []),
    ],
    ids=[
        "half-point",
        "half-point-off-zero",
        "under-half-point",
        "under-half-point-off-zero",
        "one-and-a-half",
        "two-and-a-half-rounds-up",
        "no-gap",
        "negative-gap",
    ],
)
def test_reliability_pass_at_k_gap_reading_rounds_half_up_and_shows_only_a_gap_of_at_least_one_point(
    at_k, hat_k, expected
):
    # Witnesses: s29 reliability gap truncated (`+ 0.5` dropped); s29 reliability gap bankers rounding (`math.floor(x
    # + 0.5)` to `round(x)`, so 2.5 gives 2); s29 reliability gap ceiling (`floor` to `ceil`); s29 reliability gap
    # shown at zero (`>= 1` to `>= 0`); s29 reliability gap shown when negative (`>= 1` to `!= 0`); s29 reliability
    # gap needs two points (`>= 1` to `> 1`); s29 reliability gap unit always plural; s29 reliability gap singular to
    # two; s29 reliability gap old formatting (`{points}` to `{gap * 100:.0f}`, which prints the half point as 0).
    found = readings.reliability_readings([case("a", 2, 2)], 2, at_k, hat_k)

    assert [r for r in found if r.startswith("pass@2")] == expected


def test_reliability_gap_reading_quotes_the_gap_in_points():
    # Witness: s29 reliability gap sign (`at_k - hat_k` to `hat_k - at_k`). 0.75 - 0.5 is 25 points.
    found = readings.reliability_readings([case("a", 2, 2)], 2, 0.75, 0.5)

    assert [r for r in found if r.startswith("pass@2")] == [
        "pass@2 is 25 points above pass^2: retrying hides failures that a user with one attempt would see."
    ]


WIDE = "Some ranges span more than half the scale; at 3 epochs per case, treat per-case rates as rough."


@pytest.mark.parametrize(("high", "wide"), [(0.75, []), (0.75 + 1e-9, [WIDE])], ids=["exactly-half", "over-half"])
def test_reliability_wide_range_reading_only_when_a_range_is_wider_than_half(monkeypatch, high, wide):
    # Witness: s26 reliability wide boundary (`>` to `>=`). The interval is fixed so the width is exactly 0.5.
    monkeypatch.setattr(readings, "wilson_interval", lambda passes, n: (0.25, high))

    assert matching(readings.reliability_readings([case("a", 3, 3)], 3, 1.0, 1.0), "half the scale") == wide


@pytest.mark.parametrize(("epochs", "wide"), [(3, True), (4, False)], ids=["three-of-three", "four-of-four"])
def test_reliability_wide_range_reading_uses_the_real_interval_width(epochs, wide):
    # Witness: s26 reliability wide threshold 0.6. 3/3 spans 1 - 3 / 6.8415 = 0.56; 4/4 spans 0.49.
    found = readings.reliability_readings([case("a", epochs, epochs)], epochs, 1.0, 1.0)

    assert bool(matching(found, "half the scale")) is wide


@pytest.mark.parametrize(
    ("cases", "k", "count"),
    [([case("a", 1, 1), case("b", 2, 3)], 1, "1 epoch"), ([case("a", 2, 2)], 2, "2 epochs")],
    ids=["one-epoch", "two-epochs"],
)
def test_reliability_wide_range_reading_counts_the_epochs_in_the_right_number(cases, k, count):
    # 1/1 spans 1 - 1 / 4.8415 = 0.79 and 2/2 spans 1 - 2 / 5.8415 = 0.66, both over half the scale.
    # Witnesses: s30 reliability rough epochs swapped (`counted(k, 'epoch', 'epochs')` to `counted(k, 'epochs',
    # 'epoch')`, both cases fail); s30 counted singular from one up (the two-epochs case fails).
    found = readings.reliability_readings(cases, k, 1.0, 1.0)

    assert matching(found, "half the scale") == [
        f"Some ranges span more than half the scale; at {count} per case, treat per-case rates as rough."
    ]


# Readings: tool use


def test_tool_use_readings_count_errors_and_repeats_with_per_case_counts():
    # Witnesses: s26 tool readings error names drop counts; s26 tool readings redundant uses errors.
    cases = [case("a", tool_use=tools(errors=2)), case("b", tool_use=tools(errors=1, redundant=3)), case("c")]

    assert readings.tool_use_readings(cases) == [
        "3 call(s) returned an error, in a (2) and b (1); check whether that was expected.",
        "3 call(s) repeated an identical earlier call, in b (3).",
    ]


@pytest.mark.parametrize(
    ("use", "expected"),
    [
        (None, []),
        (tools(results=2), ["No tool errors and no repeated calls."]),
        (tools(results=0), []),
        (tools(results=2, errors=1), ["1 call(s) returned an error, in a (1); check whether that was expected."]),
    ],
    ids=["no-tool-use", "clean", "no-results-recorded", "errors"],
)
def test_tool_use_readings_say_clean_only_when_results_were_recorded_and_none_failed_or_repeated(use, expected):
    # Witnesses: s26 tool readings clean without results; s26 tool readings clean with errors.
    assert readings.tool_use_readings([case("a", tool_use=use)]) == expected


@pytest.mark.parametrize(
    ("precision", "recall", "expected"),
    [
        (0.5, None, ["Precision below 100% means the agent called tools some cases did not expect."]),
        (None, 0.5, ["Recall below 100% means the agent skipped tools some cases expected."]),
        (1.0, 1.0, []),
    ],
    ids=["low-precision", "low-recall", "both-full"],
)
def test_tool_use_readings_flag_precision_and_recall_only_below_full(precision, recall, expected):
    # Witnesses: s26 tool readings precision at full (`< 1` to `<= 1`); s26 tool readings recall at full.
    use = tools(results=0, precision=precision, recall=recall)

    assert readings.tool_use_readings([case("a", tool_use=use)]) == expected


# Readings: performance


def timed(*latencies):
    return run_of(case("a", 1, len(latencies), per_epoch=[epoch(latency_s=s) for s in latencies]))


STEADY = "Latency is steady: even the slow end (p95) is within 2 times the typical try."


@pytest.mark.parametrize(
    ("latencies", "expected"),
    [
        # Nearest rank over two tries: p50 is the first, p95 the second.
        ((1.0, 2.0), ["The slow tail is long: 1 of 2 tries took 2.000s or more, 2.0 times the typical try."]),
        ((1.0, 1.99), [STEADY]),
        ((0.0, 0.0), [STEADY]),
        ((None, None), []),
        # Over three tries p50 is the second and p95 the third.
        (
            (0.0, 0.0, 5.0),
            ["The slow tail is long: 1 of 3 tries took 5.000s or more, while the typical try took no measurable time."],
        ),
        ((1.0, 3.0, 3.0), [STEADY]),
        # Over four tries p50 is the second and p95 the fourth; both tries at p95 count.
        ((1.0, 1.0, 3.0, 3.0), ["The slow tail is long: 2 of 4 tries took 3.000s or more, 3.0 times the typical try."]),
        # A try without a latency is left out of both the count and the total.
        ((1.0, None, 2.0), ["The slow tail is long: 1 of 2 tries took 2.000s or more, 2.0 times the typical try."]),
        # Over twenty tries p95 is the 19th, so the 2.0s and the 5.0s tries are both at or above it.
        (
            (1.0,) * 18 + (2.0, 5.0),
            ["The slow tail is long: 2 of 20 tries took 2.000s or more, 2.0 times the typical try."],
        ),
    ],
    ids=[
        "exactly-twice",
        "under-twice",
        "zero-typical",
        "no-latencies",
        "zero-typical-positive-tail",
        "typical-is-the-slow-end",
        "ties-at-p95",
        "missing-latency",
        "twenty-tries",
    ],
)
def test_performance_reading_calls_the_tail_long_from_twice_the_typical_try(latencies, expected):
    # Witnesses: s29 performance tail boundary (`<` to `<=`); s29 performance zero tail not steady (`p95 == 0 or`
    # dropped); s29 performance zero typical steady (`p50 > 0 and` to `p50 == 0 or`); s29 performance slow strictly
    # above (`>=` to `>`); s29 performance slow fixed at one; s29 performance total fixed at 20; s29 performance total
    # counts missing latencies; s29 performance ratio at zero typical (`p50 > 0` to `p50 >= 0`, which divides by 0);
    # s26 performance no-latency guard dropped; s26 performance tail ratio 2.5.
    assert readings.performance_readings(timed(*latencies)) == expected


# Readings: failures


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        (
            [
                case("a", 1, 2, per_epoch=[epoch("x"), epoch()]),
                case("b", 1, 2, per_epoch=[epoch("x"), epoch()]),
                case("c", 2, 2, per_epoch=[epoch(), epoch()]),
            ],
            [
                "x failed most often (2 tries, 2 case(s)); start there.",
                "Every failure comes from a case that passes on other tries: the agent is inconsistent rather than "
                "always wrong.",
            ],
        ),
        (
            [case("a", 0, 2, per_epoch=[epoch("x"), epoch("x")]), case("c", 2, 2, per_epoch=[epoch(), epoch()])],
            [
                "x failed most often (2 tries, 1 case(s)); start there.",
                "Every failure comes from a case that never passed: these are consistent failures.",
            ],
        ),
        (
            [case("a", 1, 2, per_epoch=[epoch("x"), epoch()]), case("b", 0, 2, per_epoch=[epoch("x"), epoch("x")])],
            ["x failed most often (3 tries, 2 case(s)); start there."],
        ),
        (
            [case("a", 0, 1, per_epoch=[epoch("x")]), case("b", 1, 1, per_epoch=[epoch()])],
            [
                "x failed most often (1 try, 1 case(s)); start there.",
                "Every failure comes from a case that never passed: these are consistent failures.",
            ],
        ),
        (
            [case("a", 0, 2, per_epoch=[epoch("x"), epoch("y")])],
            [
                "x and y failed most often (1 try each); start there.",
                "Every failure comes from a case that never passed: these are consistent failures.",
            ],
        ),
        # x hits one case and y two, so a single case count would be wrong for one of them.
        (
            [
                case("a", 1, 2, per_epoch=[epoch("y"), epoch()]),
                case("b", 1, 2, per_epoch=[epoch("y"), epoch()]),
                case("c", 0, 2, per_epoch=[epoch("x"), epoch("x")]),
            ],
            ["x and y failed most often (2 tries each); start there."],
        ),
        ([case("a", 2, 2, per_epoch=[epoch(), epoch()])], []),
    ],
    ids=[
        "all-flaky",
        "all-never-passed",
        "mixed",
        "single-once",
        "tie",
        "tie-across-different-case-counts",
        "nothing-failed",
    ],
)
def test_failure_readings_name_the_top_check_and_say_whether_failures_are_flaky_or_consistent(cases, expected):
    # Witnesses: s26 failures flaky any; s26 failures consistent any; s26 failures failing includes passing cases;
    # s26 top checks tie only first; s29 failures tie branch off by one (`> 1` to `> 2` in failure reading); s30
    # failures tie quotes a case count; s30 failures single drops the case count; s30 failures single tries swapped
    # (single-once and the single cases fail); s30 failures tie tries swapped (tie and tie-across fail).
    assert readings.failure_readings(run_of(*cases)) == expected


# Readings: consistency


def answered(case_id, passes, *digests):
    return case(case_id, passes, len(digests), per_epoch=[epoch(digest=d) for d in digests])


@pytest.mark.parametrize(
    ("cases", "expected"),
    [
        (
            [answered("a", 1, "d1", "d2"), answered("b", 2, "d1", "d1"), answered("c", 2, "d1", "d2")],
            [
                "2 of 3 case(s) gave a different answer in at least one epoch.",
                "For a, the answer changed along with the result, which likely explains the flaky passes.",
            ],
        ),
        (
            [answered("c", 2, "d1", "d2"), answered("b", 2, "d1", "d1")],
            ["1 of 2 case(s) gave a different answer in at least one epoch."],
        ),
        (
            [answered("a", 1, "d1", "d1")],
            [
                "Answers never varied, so the flaky results come from something other than the final answer, such "
                "as the tool calls."
            ],
        ),
        ([answered("b", 2, "d1", "d1"), case("a", 1, 2, per_epoch=[epoch(), epoch()])], []),
        ([answered("b", 2, "d1", "d1")], []),
        ([case("a", 1, 2, per_epoch=[epoch(), epoch()])], []),
    ],
    ids=[
        "varied-and-flaky",
        "varied-not-flaky",
        "never-varied-but-flaky",
        "flaky-without-answers",
        "steady",
        "no-answers",
    ],
)
def test_consistency_readings_tie_varied_answers_to_flaky_results(cases, expected):
    # Witnesses: s26 consistency both drops flaky filter; s26 consistency never varied without flaky; s26 consistency
    # flaky counts cases without answers; s26 consistency varied at full.
    assert readings.consistency_readings(run_of(*cases)) == expected


