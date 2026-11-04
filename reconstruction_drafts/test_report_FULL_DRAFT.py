import dataclasses
from pathlib import Path

import pytest

from agent_accelerator import readings
from agent_accelerator.compare import CaseResult, RunResults, Thresholds, compare
from agent_accelerator.judge import JudgedEpoch
from agent_accelerator.report import render_case_lines, render_comparison, render_run
from agent_accelerator.run_metrics import EpochMetrics
from agent_accelerator.tool_metrics import CaseToolUse
from agent_accelerator.trace_summary import TraceSummary


def result_cell(report, case_id):
    row = next(line for line in report.splitlines() if line.startswith(f"| {case_id} |"))
    return row.split("|")[2].strip()


def run_of(*cases):
    return RunResults(
        run_id="run",
        log_path=Path("run.json"),
        dataset_sha256=None,
        status="success",
        cases={case.id: case for case in cases},
    )


def render(*cases):
    return render_run(run_of(*cases))


def case(case_id, *, passed, runs=1, passes=0):
    return CaseResult(
        id=case_id,
        passed=passed,
        error=None,
        latency_s=None,
        failures={} if passed else {"case_checks": "wrong answer"},
        runs=runs,
        passes=passes,
    )


def test_single_epoch_cases_show_plain_verdict_without_tally():
    report = render(
        case("ok", passed=True, passes=1),
        case("bad", passed=False),
    )

    assert result_cell(report, "ok") == "pass"
    assert result_cell(report, "bad") == "FAIL"


def test_multi_epoch_cases_show_verdict_with_pass_tally():
    report = render(
        case("ok", passed=True, runs=4, passes=4),
        case("bad", passed=False, runs=4, passes=2),
    )

    assert result_cell(report, "ok") == "pass (4/4)"
    assert result_cell(report, "bad") == "FAIL (2/4)"


TRACE_HEADER = "## Trace summary (informational)"


def trace(sample_id, epoch=1, *, model_calls=0, tool_calls=(), tool_errors=0, model_time_s=0.0, tool_time_s=0.0):
    return TraceSummary(
        sample_id=sample_id,
        epoch=epoch,
        model_calls=model_calls,
        tool_calls=list(tool_calls),
        tool_errors=tool_errors,
        model_time_s=model_time_s,
        tool_time_s=tool_time_s,
    )


def trace_rows(report):
    section = report.split(TRACE_HEADER, 1)[1]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def trace_row(report, case_id):
    return next(row for row in trace_rows(report) if row[0] == case_id)


@pytest.mark.parametrize("traces", [None, []])
def test_no_trace_section_without_traces(traces):
    run = run_of(case("a", passed=True, passes=1))

    report = render_run(run, traces)

    assert "Trace summary" not in report
    assert report == render_run(run)


def test_trace_section_has_header_columns_and_rows_sorted_by_case_id():
    run = run_of(case("a", passed=True, passes=1), case("b", passed=True, passes=1))

    report = render_run(run, [trace("b"), trace("a")])

    section = report.split(TRACE_HEADER, 1)[1]
    header = next(line for line in section.splitlines() if line.startswith("|"))
    assert [c.strip() for c in header.strip("|").split("|")] == [
        "Case",
        "Model calls",
        "Tool calls",
        "Tool errors",
        "Model time",
        "Tool time",
    ]
    assert [row[0] for row in trace_rows(report)] == ["a", "b"]


def test_counts_are_averaged_per_epoch_whole_numbers_without_decimals():
    run = run_of(case("a", passed=True, runs=2, passes=2), case("b", passed=True, runs=2, passes=2))
    traces = [
        trace("a", 1, model_calls=1, tool_calls=["x"], tool_errors=1),
        trace("a", 2, model_calls=2, tool_calls=["x", "x"], tool_errors=0),
        trace("b", 1, model_calls=2, tool_calls=["x", "x"], tool_errors=2),
        trace("b", 2, model_calls=2, tool_calls=["x", "x"], tool_errors=2),
    ]

    report = render_run(run, traces)

    a, b = trace_row(report, "a"), trace_row(report, "b")
    assert a[1] == "1.5"
    assert a[2] == "1.5 (x)"
    assert a[3] == "0.5"
    assert b[1] == "2"
    assert b[2] == "2 (x)"
    assert b[3] == "2"


def test_tool_calls_list_distinct_names_in_first_seen_order():
    run = run_of(case("a", passed=True, runs=2, passes=2))
    traces = [
        trace("a", 1, tool_calls=["get_order", "find_customer", "get_order"]),
        trace("a", 2, tool_calls=["refund", "find_customer"]),
    ]

    report = render_run(run, traces)

    assert trace_row(report, "a")[2] == "2.5 (get_order, find_customer, refund)"


def test_no_brackets_when_there_were_no_tool_calls():
    run = run_of(case("a", passed=True, passes=1))

    report = render_run(run, [trace("a", model_calls=1)])

    assert trace_row(report, "a")[2] == "0"


def test_times_are_the_median_across_epochs_formatted_like_latency():
    run = run_of(case("a", passed=True, runs=3, passes=3))
    traces = [
        trace("a", 1, model_time_s=0.1, tool_time_s=0.9),
        trace("a", 2, model_time_s=0.9, tool_time_s=0.25),
        trace("a", 3, model_time_s=0.2, tool_time_s=0.1),
    ]

    report = render_run(run, traces)

    row = trace_row(report, "a")
    assert row[4] == "0.200s"
    assert row[5] == "0.250s"


# Terminal case lines


def failing(case_id, reason, *, runs=1, passes=0):
    return CaseResult(
        id=case_id,
        passed=False,
        error=None,
        latency_s=None,
        failures={"case_checks": reason},
        runs=runs,
        passes=passes,
    )


def test_case_lines_are_empty_for_a_run_with_no_cases():
    assert render_case_lines(run_of()) == []


def test_case_lines_put_failing_cases_first_then_sort_by_id():
    run = run_of(case("a", passed=True, passes=1), failing("z", "wrong"), case("m", passed=True, passes=1))

    lines = render_case_lines(run)

    assert [line.split()[0] for line in lines] == ["z", "a", "m"]


def test_case_lines_show_reason_only_on_failing_cases_with_pipes_unescaped():
    run = run_of(case("ok", passed=True, passes=1), failing("bad", "expected 'a|b', got 'c'"))

    bad, ok = render_case_lines(run)

    assert bad.split() == ["bad", "FAIL", "expected", "'a|b',", "got", "'c'"]
    assert r"\|" not in bad
    assert ok.split() == ["ok", "pass"]


def test_case_lines_show_pass_tally_only_when_there_are_several_epochs():
    single = render_case_lines(run_of(case("a", passed=True, passes=1)))
    multi = render_case_lines(run_of(case("a", passed=True, runs=3, passes=3), failing("b", "wrong", runs=3, passes=1)))

    assert single == ["  a  pass"]
    assert [line.split()[:3] for line in multi] == [["b", "FAIL", "(1/3)"], ["a", "pass", "(3/3)"]]


def tool_calls_cell(tool_calls):
    report = render(dataclasses.replace(case("a", passed=True, passes=1), tool_calls=tool_calls))
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")] for line in report.splitlines() if line.startswith("|")
    ]
    header, row = rows[0], next(r for r in rows if r[0] == "a")
    return row[header.index("Tool calls")]


@pytest.mark.parametrize(
    ("tool_calls", "cell"),
    [(2.0, "2"), (0.0, "0"), (1.5, "1.5"), (4 / 3, "1.3"), (None, "n/a")],
    ids=["integral", "zero", "half", "rounded-to-one-decimal", "not-recorded"],
)
def test_tool_calls_column_shows_integral_means_plainly_others_to_one_decimal_and_none_as_na(tool_calls, cell):
    # Witnesses: s16 report always one decimal gives "2.0" and "0.0"; s16 report n/a for zero (`if not value`).
    assert tool_calls_cell(tool_calls) == cell


def test_tool_calls_column_renders_an_int_count_without_decimals():
    # Witness: value.is_integer() in place of float(value).is_integer() raises AttributeError on 3.11.
    assert tool_calls_cell(2) == "2"


# Tool use section

TOOL_USE = CaseToolUse(
    calls_per_epoch=(2, 1), by_tool={"lookup": 3}, results=3, errors=0, redundant=0, precision=None, recall=None
)


def test_no_tool_use_section_when_no_case_recorded_tool_use():
    report = render(case("a", passed=True, passes=1))

    assert "## Tool use" not in report


def test_tool_use_section_follows_reliability_and_precedes_the_per_epoch_sections_and_traces():
    # Witnesses: s26 render_run tool use after metrics and s26 render_run tool use before reliability reorder the
    # headings; s26 render_run tool use dropped removes the section; s26 summary not rendered drops the Summary.
    # (The s21 anchors predate the plain-language layer and no longer match.)
    epochs = (
        EpochMetrics(latency_s=1.0, input_tokens=None, output_tokens=None, failed_checks=("x",), output_digest="d1"),
        EpochMetrics(latency_s=2.0, input_tokens=None, output_tokens=None, failed_checks=(), output_digest="d2"),
    )
    flaky = dataclasses.replace(failing("a", "wrong", runs=2, passes=1), epochs=epochs, tool_use=TOOL_USE)

    report = render_run(run_of(flaky), [trace("a")])

    # The Summary opens the report and the glossary closes it; the sections between keep their order.
    assert [line for line in report.splitlines() if line.startswith("## ")] == [
        "## Summary",
        "## Reliability (k = 2)",
        "## Tool use (informational)",
        "## Performance and cost",
        "## Failures",
        "## Consistency",
        TRACE_HEADER,
        "## How to read this report",
    ]
    assert "| lookup | 3 | 100.0% |" in report.split("## Tool use", 1)[1].split("## Performance", 1)[0]


def test_run_report_sections_follow_reliability_tool_use_metrics_then_trace_summary():
    # Witnesses: s26 render_run metrics after traces, s26 render_run tool use after metrics; s26 run glossary
    # dropped from render removes the closing heading. (The s22 anchors no longer match.)
    def metrics(failed, digest):
        return EpochMetrics(
            latency_s=1.0, input_tokens=None, output_tokens=None, failed_checks=failed, output_digest=digest
        )

    tool_use = CaseToolUse(
        calls_per_epoch=(1, 1), by_tool={"add": 2}, results=2, errors=0, redundant=0, precision=None, recall=None
    )
    flaky = dataclasses.replace(
        case("a", passed=False, runs=2, passes=1),
        epochs=(metrics(("expected_output",), "d1"), metrics((), "d2")),
        tool_use=tool_use,
    )

    report = render_run(run_of(flaky), [trace("a")])

    headings = [line for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Summary",
        "## Reliability (k = 2)",
        "## Tool use (informational)",
        "## Performance and cost",
        "## Failures",
        "## Consistency",
        "## Trace summary (informational)",
        "## How to read this report",
    ]


def test_run_report_cost_per_case_uses_the_prices_it_was_given():
    # 1,000 in and 500 out at $3 and $15 per million: $0.0105 for the one passing case.
    # Witness: s22 render_run prices not passed.
    priced = dataclasses.replace(case("a", passed=True, passes=1), input_tokens=1000, output_tokens=500)

    report = render_run(run_of(priced), input_price=3.0, output_price=15.0)

    assert "- Cost per case: $0.0105; per passing case: $0.0105" in report.splitlines()


# Reliability section (multi-epoch runs)

RELIABILITY_HEADER = "## Reliability"


def reliability_section(report):
    """The section's lines, from its heading up to the next heading."""
    lines = report.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(RELIABILITY_HEADER))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def mean_metric(report, label):
    line = next(line for line in reliability_section(report) if line.startswith(f"- Mean {label}: "))
    return line.split()[3]


def reliability_rows(report):
    rows = [line for line in reliability_section(report) if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def calculator_run():
    """Ten cases at 5 epochs, two of them at 3/5, as in a calculator run."""
    cases = [case(f"c{i:02}", passed=True, runs=5, passes=5) for i in range(1, 11) if i not in (3, 7)]
    return run_of(*cases, case("c07", passed=False, runs=5, passes=3), case("c03", passed=False, runs=5, passes=3))


def test_no_reliability_section_when_every_case_ran_once():
    # Witness: s19 report reliability shown at one epoch (`c.runs >= 1`).
    report = render(case("ok", passed=True, passes=1), case("bad", passed=False))

    assert RELIABILITY_HEADER not in report
    assert report.splitlines()[-1] == "| ok | pass | n/a | n/a | n/a |  |"


def test_no_reliability_section_and_no_error_for_a_run_with_no_cases():
    # Witness: s19 report reliability guard on any single-epoch case (min() of no cases raises).
    assert RELIABILITY_HEADER not in render_run(run_of())


def test_reliability_means_for_ten_cases_at_five_epochs_with_two_at_three_of_five():
    # pass@1 = (8 + 2 * 0.6) / 10; pass@5 = 1 for every case (3/5 has a pass in any 5 of 5);
    # pass^5 = 0 for the two 3/5 cases, so 8 / 10.
    # Witnesses: s19 report mean is max; pooled pass@1 is the same here, see the next test;
    # pass@k at k = 1; pass@1 line shows pass@k; pass^k line shows pass@k; pass@1 to no decimals; reliability dropped.
    report = render_run(calculator_run())

    assert reliability_section(report)[0] == "## Reliability (k = 5)"
    assert mean_metric(report, "pass@1") == "92.0%"
    assert mean_metric(report, "pass@5") == "100.0%"
    assert mean_metric(report, "pass^5") == "80.0%"


def test_reliability_k_is_the_fewest_epochs_and_means_are_per_case_not_pooled():
    # a 1/2, b 3/4, so k = 2. pass@1 = (0.5 + 0.75) / 2 = 62.5% (pooled 4/6 would be 66.7%).
    # pass@2: both cases have fewer than 2 failures, so 1. pass^2: a 0, b C(3,2)/C(4,2) = 1/2, mean 25%.
    # Witnesses: s19 report k is max; pooled pass@1; pass^k at each case runs; passes over k; interval over k.
    report = render(case("a", passed=False, runs=2, passes=1), case("b", passed=False, runs=4, passes=3))

    assert reliability_section(report)[0] == "## Reliability (k = 2)"
    assert mean_metric(report, "pass@1") == "62.5%"
    assert mean_metric(report, "pass@2") == "100.0%"
    assert mean_metric(report, "pass^2") == "25.0%"
    assert [row[:2] for row in reliability_rows(report)] == [["a", "1/2"], ["b", "3/4"]]


def test_reliability_section_appears_at_k_one_when_only_some_cases_ran_more_than_once():
    # Witness: s19 report reliability guard on any single-epoch case.
    report = render(case("x", passed=True, passes=1), case("y", passed=False, runs=3, passes=2))

    assert reliability_section(report)[0] == "## Reliability (k = 1)"
    assert [row[:2] for row in reliability_rows(report)] == [["y", "2/3"], ["x", "1/1"]]


@pytest.mark.parametrize(
    ("cases", "bullets"),
    [
        # x 1/1 and y 2/3, so k = 1: pass@1 = (1 + 2 / 3) / 2 = 83.3%, and pass@1 and pass^1 would only repeat it.
        (
            [case("x", passed=True, passes=1), case("y", passed=False, runs=3, passes=2)],
            ["- Mean pass@1: 83.3%", "- Intervals are wide at 1 epoch; run more for a tighter estimate."],
        ),
        # a 1/2 and b 2/2, so k = 2: pass@1 = (0.5 + 1) / 2 = 75%; pass@2 is 1 for both; pass^2 is 0 for a, 1 for b.
        (
            [case("a", passed=False, runs=2, passes=1), case("b", passed=True, runs=2, passes=2)],
            [
                "- Mean pass@1: 75.0%",
                "- Mean pass@2: 100.0% (at least one of 2 tries passes)",
                "- Mean pass^2: 50.0% (all 2 tries pass)",
                "- Intervals are wide at 2 epochs; run more for a tighter estimate.",
            ],
        ),
    ],
    ids=["k-one", "k-two"],
)
def test_reliability_bullets_show_pass_at_k_and_pass_hat_k_only_when_k_is_above_one(cases, bullets):
    # Witnesses: s30 report pass@k at k = 1 (`k > 1` to `k >= 1`, k-one fails); s30 report pass@k from k = 3 (`k > 1`
    # to `k > 2`, k-two fails); s30 report caveat epochs swapped (both fail); s30 counted singular from one up (k-two).
    assert [line for line in reliability_section(render(*cases)) if line.startswith("- ")] == bullets


def test_reliability_table_follows_case_table_order_with_wilson_intervals():
    # Wilson 95% at n = 5, computed by hand: 3/5 -> [0.2307, 0.8824], 5/5 -> [0.5655, 1], 0/5 -> [0, 0.4345].
    # Witnesses: s19 report reliability rows sorted by id; interval bounds swapped; rate to one decimal.
    report = render(
        case("z", passed=True, runs=5, passes=5),
        case("m", passed=False, runs=5, passes=3),
        case("a", passed=True, runs=5, passes=5),
        case("b", passed=False, runs=5, passes=0),
    )

    case_table = [line for line in report.split(RELIABILITY_HEADER)[0].splitlines() if line.startswith("|")][2:]
    case_table_order = [line.split("|")[1].strip() for line in case_table]
    assert case_table_order == ["b", "m", "a", "z"]
    assert reliability_rows(report) == [
        ["b", "0/5", "0% [0%, 43%]"],
        ["m", "3/5", "60% [23%, 88%]"],
        ["a", "5/5", "100% [57%, 100%]"],
        ["z", "5/5", "100% [57%, 100%]"],
    ]


def test_reliability_section_sits_between_case_table_and_trace_summary():
    # Witness: s19 report reliability after trace summary.
    run = run_of(case("a", passed=True, runs=2, passes=2))

    report = render_run(run, [trace("a", 1), trace("a", 2)])

    case_row = report.index("| a | pass (2/2) |")
    assert case_row < report.index(RELIABILITY_HEADER) < report.index(TRACE_HEADER)


@pytest.mark.parametrize(("epochs", "caveat"), [(4, True), (5, False)], ids=["under-five", "five"])
def test_wide_interval_caveat_only_below_five_epochs(epochs, caveat):
    # Witnesses: s19 report caveat at five epochs (`k <= 5`); caveat only below four (`k < 4`); s30 report caveat
    # epochs swapped (under-five fails).
    report = render(case("a", passed=True, runs=epochs, passes=epochs))

    caveats = [line for line in reliability_section(report) if line.startswith("- Intervals are wide")]
    assert caveats == ([f"- Intervals are wide at {epochs} epochs; run more for a tighter estimate."] if caveat else [])


# Judge section


JUDGE_HEADER = "## Judge"
JUDGE_GLOSSARY = [readings.GLOSSARY[k] for k in ("judge error", "reference-free", "kappa")]


def je(case_id, outcome="pass", mode="golden", *, model="m", criteria=(), label=None):
    return JudgedEpoch(case_id, outcome, mode, model, tuple(criteria), label)


def judged_run(*epochs):
    """A run of passing cases, one per case id in `epochs`, judged with `epochs`."""
    run = run_of(*(case(i, passed=True, passes=1) for i in dict.fromkeys(e.case_id for e in epochs)))
    return dataclasses.replace(run, judge=tuple(epochs))


def judge_section(report):
    lines = report.splitlines()
    start = lines.index(JUDGE_HEADER)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def judge_bullets(report):
    return [line for line in judge_section(report) if line.startswith("- ")]


def test_a_run_without_a_judge_has_no_judge_section_and_no_judge_glossary():
    # Witnesses: "s32 judge lines no empty guard" renders a section of zero errors; "s32 judge glossary no empty guard"
    # adds the judge error entry.
    report = render(case("a", passed=True, passes=1))

    assert JUDGE_HEADER not in report.splitlines()
    assert [text for text in JUDGE_GLOSSARY if text in report] == []


def test_judge_bullets_count_each_outcome_with_modes_by_case_and_models_sorted():
    # One epoch per case, so counts are in cases. Mode counts cases, not epochs: d recorded no mode.
    # Witnesses: "s32 judge models unsorted" lists z-model first; "s32 judge passed counts fails"; "s32 judge errors
    # counts not judged"; "s32 judged counts all epochs" (len(epochs) for len(verdicts)).
    run = judged_run(
        je("a", "pass", model="z-model"),
        je("b", "fail", "reference_free", model="a-model"),
        je("c", "error", model="z-model"),
        je("d", "not_judged", None, model=None),
    )

    assert judge_bullets(render_run(run)) == [
        "- Mode: golden (2 cases), reference-free (1 case)",
        "- Judge model: `a-model`, `z-model`",
        "- Judged: 2 of 4 cases",
        "- Judge passed: 1/2 (50.0%)",
        "- Judge errors: 1",
        "- Not judged (agent error): 1",
    ]


def test_judge_passed_omits_the_rate_when_there_are_no_verdicts():
    # Witness: "s32 judge rate unguarded" divides by zero.
    run = judged_run(je("a", "error"), je("b", "not_judged", None, model=None))

    bullets = judge_bullets(render_run(run))

    assert bullets[2:4] == ["- Judged: 0 of 2 cases", "- Judge passed: 0/0"]


@pytest.mark.parametrize(
    ("modes", "text"),
    [
        (["golden", "golden"], "golden"),
        (["reference_free", "reference_free"], "reference-free"),
        (["custom", "custom"], "custom"),
        ([None, None], "n/a"),
        (["custom", "golden"], "golden (1 case), custom (1 case)"),
    ],
    ids=["golden", "reference-free", "unknown-mode-as-recorded", "no-mode", "known-modes-first"],
)
def test_judge_mode_is_one_word_for_a_single_mode_and_counts_cases_per_mode_when_mixed(modes, text):
    # Witnesses: "s32 judge mode single counted" counts a single mode; "s32 judge mode raw" shows reference_free;
    # "s32 judge mode unknown first" sorts every mode alphabetically.
    run = judged_run(*(je(f"c{i}", "pass", mode) for i, mode in enumerate(modes)))

    assert judge_bullets(render_run(run))[0] == f"- Mode: {text}"


def test_judge_mode_counts_each_case_once_however_many_epochs_it_ran():
    # Witness: "s32 judge modes per epoch" counts a's three epochs.
    run = judged_run(je("a"), je("a"), je("a"), je("b", mode="reference_free"))

    assert judge_bullets(render_run(run))[0] == "- Mode: golden (1 case), reference-free (1 case)"


@pytest.mark.parametrize(
    ("epochs", "model", "judged"),
    [
        ([je("a"), je("b", model=None)], "- Judge model: `m`", "- Judged: 2 of 2 cases"),
        ([je("a"), je("a", "fail"), je("b", model=None)], "- Judge model: `m`", "- Judged: 3 of 3 tries"),
        ([je("a", model=None)], "- Judge model: n/a", "- Judged: 1 of 1 case"),
    ],
    ids=["one-epoch-each", "several-epochs", "no-model"],
)
def test_judge_counts_cases_with_one_epoch_each_and_tries_otherwise(epochs, model, judged):
    # Witnesses: "s32 judge unit always cases" and "s32 judge unit always tries".
    bullets = judge_bullets(render_run(judged_run(*epochs)))

    assert (bullets[1], bullets[2]) == (model, judged)


def criteria_table(report):
    section = judge_section(report)
    start = next(i for i, line in enumerate(section) if line.startswith("Reference-free criteria"))
    rows = [line for line in section[start + 4 :] if line.startswith("|")]
    return section[start], rows


def test_criteria_table_counts_reference_free_verdicts_only_in_rubric_order_with_zero_rows():
    # Counted: a's two epochs and b. Left out: c's judge error, d's golden verdict and e's verdict with no criteria.
    # brevity fails three tries over two cases; safety never fails and still has a row.
    tone, brevity, safety = "tone", "brevity", "safety"
    run = judged_run(
        je("a", "pass", "reference_free", criteria=[(tone, True), (brevity, False), (safety, True)]),
        je("a", "fail", "reference_free", criteria=[(tone, False), (brevity, False), (safety, True)]),
        je("b", "fail", "reference_free", criteria=[(tone, True), (brevity, False), (safety, True)]),
        je("c", "error", "reference_free", criteria=[(tone, False), (safety, False)]),
        je("d", "fail", "golden", criteria=[(tone, False), (safety, False)]),
        je("e", "pass", "reference_free"),
    )

    heading, rows = criteria_table(render_run(run))

    # Witnesses: "s32 criteria include golden"; "s32 criteria include errors"; "s32 criteria cases not distinct"
    # (len(ids) for cases); "s32 criteria zero rows dropped"; "s32 criteria sorted" (sorted(failing.items())).
    assert heading == "Reference-free criteria, over 3 tries judged:"
    assert rows == ["| tone | 1 | 1 |", "| brevity | 3 | 2 |", "| safety | 0 | 0 |"]


def test_criteria_table_counts_cases_when_every_case_ran_once():
    # Witness: "s32 judge unit always tries".
    run = judged_run(je("a", "fail", "reference_free", criteria=[("tone", False)]), je("b", "pass", "reference_free"))

    heading, rows = criteria_table(render_run(run))

    assert (heading, rows) == ("Reference-free criteria, over 1 case judged:", ["| tone | 1 | 1 |"])


def test_no_criteria_table_without_a_reference_free_verdict_with_criteria():
    # Witnesses: "s32 criteria include golden" prints a table for a's golden criteria, "s32 criteria include errors"
    # one for b's judge error; "s32 criteria empty guard dropped" prints a heading over 0 cases.
    run = judged_run(
        je("a", "fail", "golden", criteria=[("tone", False)]),
        je("b", "error", "reference_free", criteria=[("tone", False)]),
    )

    section = judge_section(render_run(run))

    assert [line for line in section if line.startswith(("Reference-free criteria", "|"))] == []
    assert len(section) > 5


def test_calibration_compares_judged_epochs_of_labelled_golden_cases_only():
    # Labelled cases: a (two epochs), b and d; d's judge error has no verdict to compare. c is reference-free, so its
    # label does not count, and e has no label. Compared: a pass/pass, a fail/pass, b fail/pass, so 1 of 3 agree. The
    # kappa minimum counts the cases with a verdict, a and b, so 2.
    run = judged_run(
        je("a", "pass", label="pass"),
        je("a", "fail", label="pass"),
        je("b", "fail", label="pass"),
        je("c", "pass", "reference_free", label="fail"),
        je("d", "error", label="fail"),
        je("e", "pass"),
    )

    report = render_run(run)

    # Witnesses: "s32 calibration any mode" counts c; "s32 calibration errors compared" compares d; "s32 labelled
    # counts epochs" gives 4 labelled; "s32 agreement counts disagreements"; "s34 comparable counts labelled" has 3.
    assert judge_bullets(report)[6:] == [
        "- Human-labelled golden cases: 3 (3 verdicts compared)",
        "- Agreement with human labels: 1/3 (33.3%)",
        "- Cohen's kappa: needs at least 10 labelled cases (have 2)",
    ]
    assert readings.GLOSSARY["kappa"] in report


def test_no_calibration_lines_or_kappa_glossary_without_human_labels():
    # Witness: "s32 calibration always" (has_calibration True) adds the kappa entry.
    report = render_run(judged_run(je("a"), je("b", "fail")))

    assert not any("Human-labelled" in text for text in judge_bullets(report))
    assert readings.GLOSSARY["kappa"] not in report
    assert readings.GLOSSARY["judge error"] in report




def test_labels_without_a_comparable_verdict_give_only_the_labelled_count():
    # Witness: "s32 calibration lines unguarded" divides by zero for the agreement.
    run = judged_run(je("a", "error", label="pass"), je("b", "not_judged", label="fail"))

    assert judge_bullets(render_run(run))[6:] == ["- Human-labelled golden cases: 2 (0 verdicts compared)"]


def labelled_cases(verdicts, labels):
    return judged_run(*(je(f"c{i:02}", v, label=h) for i, (v, h) in enumerate(zip(verdicts, labels, strict=True))))


# Ten cases, five labelled pass and five fail; the judge agrees on eight. p_o = 8/10, each side passes 5 of 10 so
# p_e = 1/2, and kappa = (0.8 - 0.5) / 0.5 = 0.60.
TEN_LABELS = ["pass"] * 5 + ["fail"] * 5
TEN_VERDICTS = ["pass"] * 4 + ["fail"] * 5 + ["pass"]
UNDEFINED_KAPPA = "- Cohen's kappa: undefined (every labelled case got the same verdict from both)"


@pytest.mark.parametrize(
    ("verdicts", "labels", "kappa_line"),
    [
        (TEN_VERDICTS[:9], TEN_LABELS[:9], "- Cohen's kappa: needs at least 10 labelled cases (have 9)"),
        (TEN_VERDICTS, TEN_LABELS, "- Cohen's kappa: 0.60"),
        (["pass"] * 10, ["pass"] * 10, UNDEFINED_KAPPA),
    ],
    ids=["nine-labelled", "ten-labelled", "ten-all-one-label"],
)
def test_kappa_needs_ten_labelled_cases_and_is_undefined_when_both_sides_are_constant(verdicts, labels, kappa_line):
    # Witnesses: "s32 kappa line minimum inclusive" (<=) fails both ten-label cases; "s32 kappa computed only above
    # ten" (>) makes ten-labelled undefined; "s32 kappa line none unchecked" formats None in ten-all-one-label.
    assert judge_bullets(render_run(labelled_cases(verdicts, labels)))[-1] == kappa_line


def test_ten_labelled_cases_report_the_agreement_beside_the_kappa():
    # Witness: "s32 agreement counts disagreements" gives 2/10.
    bullets = judge_bullets(render_run(labelled_cases(TEN_VERDICTS, TEN_LABELS)))

    assert bullets[6:8] == [
        "- Human-labelled golden cases: 10 (10 verdicts compared)",
        "- Agreement with human labels: 8/10 (80.0%)",
    ]


def test_judge_section_leaves_everything_above_it_unchanged():
    # The summary, case table and readings are those of the same run without a judge, even when the judge failed
    # every case the case checks passed; the Judge section only adds lines.
    # Witness: "s32 summary passed from judge" counts judge passes in the Passed line.
    plain = run_of(case("a", passed=True, passes=1), case("b", passed=True, passes=1), case("c", passed=False))
    judged = dataclasses.replace(plain, judge=(je("a", "fail"), je("b", "fail"), je("c", "error")))

    plain_lines, judged_lines = render_run(plain).splitlines(), render_run(judged).splitlines()

    assert "- Passed: 2/3 (66.7%)" in plain_lines
    assert judged_lines[: judged_lines.index(JUDGE_HEADER) - 1] == plain_lines


def test_comparison_report_has_no_judge_content_when_both_runs_were_judged():
    # Deliberately unchanged: the judge section is a run-report section only.
    # Witness: "s32 comparison renders judge" adds the current run's Judge section before the glossary.
    baseline = run_of(case("a", passed=True, passes=1), case("b", passed=False))
    current = run_of(case("a", passed=False), case("b", passed=True, passes=1))
    labelled = (je("a", "fail", label="pass"), je("b", "error", "reference_free", criteria=[("tone", False)]))

    plain = render_comparison(compare(baseline, current, Thresholds()))
    judged = render_comparison(
        compare(
            dataclasses.replace(baseline, judge=labelled), dataclasses.replace(current, judge=labelled), Thresholds()
        )
    )

    assert judged == plain
    assert [text for text in [JUDGE_HEADER, *JUDGE_GLOSSARY] if text in judged] == []


def judge_readings_in(report):
    return [line.removeprefix("  - ") for line in judge_section(report) if line.startswith("  - ")]


FEW_LABELS = "Kappa needs at least 10 labelled cases and there are {}; label more golden entries before relying on the "
FEW_LABELS += "agreement figure."


def test_kappa_is_not_printed_when_fewer_than_ten_labelled_cases_have_a_verdict_to_compare():
    # Ten labelled golden cases, but the judge could not score eight, so only two verdicts are compared. The minimum
    # exists because kappa from so few items is unstable; before the fix it printed 1.00 and read "almost perfect".
    # Witnesses: "s34 comparable counts labelled" prints kappa 1.00; "s34 kappa line counts labelled" calls it
    # undefined; "s34 readings given labelled" gives the undefined reading instead of the too-few one.
    run = labelled_cases(["pass", "fail"] + ["error"] * 8, ["pass", "fail"] + ["pass"] * 8)

    report = render_run(run)

    assert judge_bullets(report)[6:] == [
        "- Human-labelled golden cases: 10 (2 verdicts compared)",
        "- Agreement with human labels: 2/2 (100.0%)",
        "- Cohen's kappa: needs at least 10 labelled cases (have 2)",
    ]
    assert judge_readings_in(report)[-1] == FEW_LABELS.format(2)
    assert "almost perfect agreement" not in report


NINE = [je(f"c{i:02}", v, label=h) for i, (v, h) in enumerate(zip(TEN_VERDICTS[:9], TEN_LABELS[:9], strict=True))]
TEN = [je(f"c{i:02}", v, label=h) for i, (v, h) in enumerate(zip(TEN_VERDICTS, TEN_LABELS, strict=True))]


@pytest.mark.parametrize(
    ("epochs", "labelled_bullet", "kappa_line"),
    [
        (
            [*TEN, je("c10", "error", label="pass")],
            "- Human-labelled golden cases: 11 (10 verdicts compared)",
            "- Cohen's kappa: 0.60",
        ),
        (
            [*NINE, je("c10", "error", label="pass")],
            "- Human-labelled golden cases: 10 (9 verdicts compared)",
            "- Cohen's kappa: needs at least 10 labelled cases (have 9)",
        ),
        (
            [*NINE, je("c10", "not_judged", label="fail")],
            "- Human-labelled golden cases: 10 (9 verdicts compared)",
            "- Cohen's kappa: needs at least 10 labelled cases (have 9)",
        ),
        (
            [*NINE, je("c00", "pass", label="pass")],
            "- Human-labelled golden cases: 9 (10 verdicts compared)",
            "- Cohen's kappa: needs at least 10 labelled cases (have 9)",
        ),
        (
            [*NINE, je("c10", "pass", "reference_free", label="pass")],
            "- Human-labelled golden cases: 9 (9 verdicts compared)",
            "- Cohen's kappa: needs at least 10 labelled cases (have 9)",
        ),
    ],
    ids=[
        "ten-comparable-and-a-judge-error",
        "nine-comparable-and-a-judge-error",
        "nine-comparable-and-not-judged",
        "nine-cases-one-judged-twice",
        "nine-golden-and-a-labelled-reference-free",
    ],
)
def test_kappa_minimum_counts_each_labelled_golden_case_with_a_verdict_once(epochs, labelled_bullet, kappa_line):
    # TEN is the 0.60 run above; a labelled judge error beside it changes neither the minimum nor the figure. NINE has
    # nine comparable cases, so a tenth labelled case without a verdict, a second epoch of c00, or a labelled
    # reference-free case must still leave kappa unprinted. The labelled-cases bullet counts as before.
    # Witnesses: "s34 comparable counts labelled" and "s34 kappa line counts labelled" fail
    # nine-comparable-and-a-judge-error and not-judged; "s34 comparable counts pairs" (len(pairs)) fails judged-twice;
    # "s32 calibration any mode" fails reference-free; "s32 kappa computed only above ten" fails the ten-comparable
    # control, which shows a labelled case without a verdict does not hold kappa back once ten cases have one.
    bullets = judge_bullets(render_run(judged_run(*epochs)))

    assert (bullets[6], bullets[-1]) == (labelled_bullet, kappa_line)
