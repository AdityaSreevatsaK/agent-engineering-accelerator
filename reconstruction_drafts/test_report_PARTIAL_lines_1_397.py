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
