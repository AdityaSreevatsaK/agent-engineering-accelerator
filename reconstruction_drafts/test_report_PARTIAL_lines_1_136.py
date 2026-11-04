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
