import copy
import json
from dataclasses import replace
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_accelerator.cli import main
from agent_accelerator.compare import CaseResult, RunResults, Thresholds, compare, load_results
from agent_accelerator.report import render_comparison, render_run, validate_prices
from agent_accelerator.run_metrics import EpochMetrics, recorded_run_usage

REPO = Path(__file__).parents[2]
DATASET = REPO / "examples" / "calculator" / "dataset.jsonl"
AGENT = "examples.calculator.agent:build_agent"
FIXTURE = REPO / "tests" / "fixtures" / "calculator_capture_content.json"
MISSING = object()  # usage key absent from the sample metadata altogether


# Logs with chosen usage are built from the passing fixture's first sample, one copy per epoch.


def write_log(path, cases):
    """cases maps case id -> list of per-epoch usage values (MISSING drops the key)."""
    log = json.loads(FIXTURE.read_text(encoding="utf-8"))
    template = log["samples"][0]
    samples = []
    for case_id, usages in cases.items():
        for epoch, usage in enumerate(usages, start=1):
            sample = copy.deepcopy(template)
            sample["id"] = case_id
            sample["epoch"] = epoch
            if usage is MISSING:
                sample["metadata"].pop("usage", None)
            else:
                sample["metadata"]["usage"] = usage
            samples.append(sample)
    log["samples"] = samples
    path.write_text(json.dumps(log), encoding="utf-8")
    return path


def load(tmp_path, cases):
    return load_results(write_log(tmp_path / "log.json", cases))


def usage(input_tokens, output_tokens):
    return {"inputTokens": input_tokens, "outputTokens": output_tokens}


# load_results: per-case mean over epochs


def test_case_tokens_are_the_mean_over_epochs_rounded_to_int(tmp_path):
    run = load(tmp_path, {"a": [usage(100, 10), usage(102, 11), usage(103, 11)]})

    case = run.cases["a"]
    assert case.input_tokens == 102  # 101.67
    assert case.output_tokens == 11  # 10.67
    assert isinstance(case.input_tokens, int)
    assert isinstance(case.output_tokens, int)


@pytest.mark.parametrize(
    "unreported",
    [MISSING, None, ["inputTokens", 999], "inputTokens=999", {}, {"inputTokens": None, "outputTokens": None}],
    ids=["usage_missing", "usage_none", "usage_list", "usage_str", "keys_missing", "keys_none"],
)
def test_epochs_that_did_not_report_usage_are_skipped_not_counted_as_zero(tmp_path, unreported):
    run = load(tmp_path, {"a": [usage(300, 30), unreported]})

    assert run.cases["a"].input_tokens == 300
    assert run.cases["a"].output_tokens == 30


def test_a_missing_key_skips_that_epoch_for_that_field_only(tmp_path):
    run = load(tmp_path, {"a": [usage(300, 30), {"outputTokens": 50}, {"inputTokens": None, "outputTokens": 70}]})

    assert run.cases["a"].input_tokens == 300
    assert run.cases["a"].output_tokens == 50


@pytest.mark.parametrize("unreported", [MISSING, None, "n/a", {}], ids=["missing", "none", "non_dict", "no_keys"])
def test_case_tokens_are_none_when_no_epoch_reported(tmp_path, unreported):
    run = load(tmp_path, {"a": [unreported, unreported]})

    assert run.cases["a"].input_tokens is None
    assert run.cases["a"].output_tokens is None


# RunResults: sum over cases that reported


def test_run_tokens_sum_over_cases_that_reported(tmp_path):
    run = load(tmp_path, {"a": [usage(100, 10)], "b": [usage(250, 25)], "c": [None]})

    assert run.input_tokens == 350
    assert run.output_tokens == 35


def test_run_tokens_are_none_when_no_case_reported(tmp_path):
    run = load(tmp_path, {"a": [None], "b": [MISSING]})

    assert run.input_tokens is None
    assert run.output_tokens is None


def tokens_case(case_id, input_tokens=None, output_tokens=None, *, passed=True, latency_s=None):
    return CaseResult(
        id=case_id,
        passed=passed,
        error=None,
        latency_s=latency_s,
        failures={} if passed else {"case_checks": "wrong answer"},
        runs=1,
        passes=1 if passed else 0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def run_of(*cases, run_id="run"):
    return RunResults(
        run_id=run_id,
        log_path=Path("run.json"),
        dataset_sha256=None,
        status="success",
        cases={case.id: case for case in cases},
    )


def test_run_tokens_from_constructed_cases_ignore_cases_without_tokens():
    run = run_of(tokens_case("a", 1200, 300), tokens_case("b", 800, 100), tokens_case("c"))

    assert run.input_tokens == 2000
    assert run.output_tokens == 400


# validate_prices


@pytest.mark.parametrize("prices", [(None, None), (1.0, 5.0), (0.0, 0.0), (0.0, 3.5)])
def test_validate_prices_accepts_both_or_neither_and_zero(prices):
    validate_prices(*prices)


@pytest.mark.parametrize(
    "prices",
    [(1.0, None), (None, 5.0), (-1.0, 5.0), (1.0, -0.01), (math.nan, 5.0), (1.0, math.nan)],
    ids=["input_only", "output_only", "negative_input", "negative_output", "nan_input", "nan_output"],
)
def test_validate_prices_rejects_one_alone_negative_or_nan(prices):
    with pytest.raises(ValueError):
        validate_prices(*prices)


def test_render_run_rejects_a_single_price():
    with pytest.raises(ValueError):
        render_run(run_of(tokens_case("a", 1, 1)), input_price=1.0)


# render_run: case table


def table_rows(report):
    rows = [line for line in report.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


def test_case_table_has_tokens_column_between_latency_and_failure():
    header = table_rows(render_run(run_of(tokens_case("a", 1, 1))))[0]

    assert header == ["Case", "Result", "Latency", "Tokens (in/out)", "Tool calls", "Failure"]


def test_case_row_shows_tokens_with_thousands_separators_in_their_column():
    report = render_run(run_of(tokens_case("a", 1200, 300, passed=False, latency_s=0.5)))

    row = next(r for r in table_rows(report) if r[0] == "a")
    assert row == ["a", "FAIL", "0.500s", "1,200/300", "n/a", "wrong answer"]


def test_case_row_shows_na_when_the_case_has_no_tokens():
    report = render_run(run_of(tokens_case("a"), tokens_case("b", 5, 6)))

    row = next(r for r in table_rows(report) if r[0] == "a")
    assert row[3] == "n/a"


# render_run: summary and cost


def summary_lines(report):
    return [line for line in report.splitlines() if line.startswith("- ")]


def test_summary_tokens_line_with_thousands_separators():
    report = render_run(run_of(tokens_case("a", 1200, 300), tokens_case("b", 800, 100)))

    assert "- Tokens: 2,000 in / 400 out per run (informational)" in summary_lines(report)


def test_summary_tokens_line_is_na_without_tokens():
    report = render_run(run_of(tokens_case("a")))

    assert "- Tokens: n/a (informational)" in summary_lines(report)


def test_estimated_cost_line_with_both_prices_and_tokens():
    report = render_run(run_of(tokens_case("a", 1200, 300), tokens_case("b", 800, 100)), None, 1.0, 5.0)

    assert "- Estimated cost: $0.0040 (at $1/$5 per million tokens)" in summary_lines(report)


def test_estimated_cost_uses_input_and_output_prices_separately_and_rounds_to_four_decimals():
    # (1,000,000 x 0.5 + 12,345 x 3.25) / 1e6 = 0.54012125
    report = render_run(run_of(tokens_case("a", 1_000_000, 12_345)), None, 0.5, 3.25)

    assert "- Estimated cost: $0.5401 (at $0.5/$3.25 per million tokens)" in summary_lines(report)


def test_estimated_cost_with_zero_prices_is_shown_as_zero():
    report = render_run(run_of(tokens_case("a", 1200, 300)), None, 0.0, 0.0)

    assert "- Estimated cost: $0.0000 (at $0/$0 per million tokens)" in summary_lines(report)


def test_no_estimated_cost_without_prices():
    report = render_run(run_of(tokens_case("a", 1200, 300)))

    assert "Estimated cost" not in report


def test_no_estimated_cost_without_tokens_even_with_prices():
    report = render_run(run_of(tokens_case("a")), None, 1.0, 5.0)

    assert "Estimated cost" not in report


# render_comparison


def metric_row(report, metric):
    return next(r for r in table_rows(report) if r[0] == metric)


def test_comparison_has_tokens_per_run_row():
    base = run_of(tokens_case("a", 1200, 300), run_id="base")
    cur = run_of(tokens_case("a", 2500, 400), run_id="cur")

    report = render_comparison(compare(base, cur, Thresholds()))

    assert metric_row(report, "Tokens per run (informational)") == [
        "Tokens per run (informational)",
        "1,200/300",
        "2,500/400",
    ]


@pytest.mark.parametrize("side", ["baseline", "current"])
def test_comparison_tokens_row_is_na_for_a_side_without_tokens(side):
    with_tokens = run_of(tokens_case("a", 1200, 300), run_id="x")
    without = run_of(tokens_case("a"), run_id="y")
    base, cur = (without, with_tokens) if side == "baseline" else (with_tokens, without)

    row = metric_row(render_comparison(compare(base, cur, Thresholds())), "Tokens per run (informational)")

    assert row[1:] == (["n/a", "1,200/300"] if side == "baseline" else ["1,200/300", "n/a"])


def test_large_token_rise_is_not_a_regression():
    base = run_of(tokens_case("a", 100, 10), tokens_case("b", 100, 10), run_id="base")
    cur = run_of(tokens_case("a", 10_000_000, 1_000_000), tokens_case("b", 10_000_000, 1_000_000), run_id="cur")

    cmp = compare(base, cur, Thresholds())

    assert cmp.regressions == []
    assert cmp.regressed is False
    report = render_comparison(cmp)
    assert "**OK**" in report
    assert "- Regression:" not in report


# CLI


# The calculator double reports no usage; this one adds a Strands usage metadata event to every model call.
USAGE_DOUBLES_SOURCE = """
from examples.calculator.agent import OPERATIONS, RuleBasedModel, _build


class UsageModel(RuleBasedModel):
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
            yield event
        usage = {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 1}}}


def build_usage_agent():
    return _build(OPERATIONS, UsageModel)
"""


@pytest.fixture(scope="module")
def price_runs(tmp_path_factory):
    """`run` goes through a subprocess, as in test_cli.py; all start together."""
    doubles_dir = tmp_path_factory.mktemp("token_doubles")
    (doubles_dir / "aea_token_doubles.py").write_text(USAGE_DOUBLES_SOURCE, encoding="utf-8")
    cases = {
        "negative": ["--input-price", "-1", "--output-price", "5"],
        "input_only": ["--input-price", "1"],
        "output_only": ["--output-price", "5"],
        "priced": ["--agent", "aea_token_doubles:build_usage_agent", "--input-price", "1", "--output-price", "5"],
    }
    python_path = os.pathsep.join(p for p in [str(doubles_dir), os.environ.get("PYTHONPATH")] if p)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": python_path}
    started = {}
    for name, price_args in cases.items():
        runs_dir = tmp_path_factory.mktemp(f"runs_price_{name}")
        command = [
            sys.executable,
            "-m",
            "agent_accelerator.cli",
            "run",
            str(DATASET),
            "--agent",
            AGENT,
            "--runs-dir",
            str(runs_dir),
            *price_args,
        ]
        process = subprocess.Popen(
            command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
        )
        started[name] = (process, runs_dir)
    results = {}
    for name, (process, runs_dir) in started.items():
        stdout, stderr = process.communicate(timeout=300)
        results[name] = {"code": process.returncode, "stdout": stdout, "stderr": stderr, "runs_dir": runs_dir}
    return results


@pytest.mark.parametrize("name", ["negative", "input_only", "output_only"])
def test_run_with_bad_price_exits_two_with_error_and_creates_no_run_dir(price_runs, name):
    result = price_runs[name]

    assert result["code"] == 2
    assert result["stderr"].lstrip().startswith("error:"), result["stderr"]
    assert list(result["runs_dir"].iterdir()) == []


def test_run_with_prices_and_reported_usage_writes_estimated_cost_to_report(price_runs):
    result = price_runs["priced"]
    assert result["code"] == 0, result["stderr"]

    run_dirs = [p for p in result["runs_dir"].iterdir() if p.is_dir()]
    assert len(run_dirs) == 1, (run_dirs, result["stdout"], result["stderr"])
    report = (run_dirs[0] / "report.md").read_text(encoding="utf-8")
    cost = [line for line in report.splitlines() if line.startswith("- Estimated cost: $")]
    assert len(cost) == 1, (report, result["stderr"])
    assert cost[0].endswith("(at $1/$5 per million tokens)")


@pytest.mark.parametrize(
    "price_args",
    [["--input-price", "1", "--output-price", "-5"], ["--input-price", "1"], ["--output-price", "5"]],
    ids=["negative", "input_only", "output_only"],
)
def test_report_with_bad_price_exits_two_with_error(capsys, price_args):
    assert main(["report", str(FIXTURE), *price_args]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_report_with_prices_prints_estimated_cost(tmp_path, capsys):
    log = write_log(tmp_path / "log.json", {"a": [usage(1200, 300)], "b": [usage(800, 100)]})

    assert main(["report", str(log), "--input-price", "1", "--output-price", "5"]) == 0
    printed = capsys.readouterr().out
    assert "- Tokens: 2,000 in / 400 out per run (informational)" in printed
    assert "- Estimated cost: $0.0040 (at $1/$5 per million tokens)" in printed


def multi_epoch_case(case_id, recorded, *, passed=True):
    """Construct a case using explicit epoch usage, without relying on averaged totals."""
    epochs = tuple(
        EpochMetrics(
            latency_s=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            failed_checks=(),
            output_digest=None,
        )
        for input_tokens, output_tokens in recorded
    )
    input_values = [a for a, _ in recorded if a is not None]
    output_values = [b for _, b in recorded if b is not None]
    return replace(
        tokens_case(case_id, passed=passed),
        runs=len(epochs),
        epochs=epochs,
        input_tokens=round(sum(input_values) / len(input_values)) if input_values else None,
        output_tokens=round(sum(output_values) / len(output_values)) if output_values else None,
    )


def test_full_evaluation_cost_uses_every_observed_epoch_without_averaging():
    run = run_of(
        multi_epoch_case("one", [(100, 10), (200, 20)]),
        multi_epoch_case("two", [(300, 30), (400, 40)]),
    )
    usage = recorded_run_usage(run)
    assert usage is not None
    assert usage.complete is True
    assert (usage.input_tokens, usage.output_tokens, usage.expected_epochs) == (1000, 100, 4)

    report = render_run(run, input_price=1.0, output_price=5.0)
    assert "- Estimated cost: $0.0008 (at $1/$5 per million tokens)" in report
    assert "- Recorded usage across all epochs: 1,000 input / 100 output tokens " in report
    assert "(input reported 4/4 epochs; output reported 4/4 epochs)" in report
    assert "- Estimated total evaluation cost: $0.0015 (at $1/$5 per million tokens; all epochs)" in report


def test_missing_epoch_usage_does_not_understate_total_evaluation_cost():
    run = run_of(multi_epoch_case("one", [(100, 10), (200, None)]))

    usage = recorded_run_usage(run)
    assert usage is not None
    assert usage.complete is False
    assert (usage.input_epochs, usage.output_epochs) == (2, 1)

    report = render_run(run, input_price=1.0, output_price=5.0)
    assert "(input reported 2/2 epochs; output reported 1/2 epochs)" in report
    assert "- Estimated total evaluation cost: n/a (incomplete epoch usage; no extrapolation)" in report


def test_legacy_result_without_epoch_details_does_not_claim_observed_cost():
    run = run_of(tokens_case("one", 100, 10))
    assert recorded_run_usage(run) is None
    assert "Recorded usage across all epochs" not in render_run(run, input_price=1.0, output_price=5.0)


def test_full_evaluation_usage_is_visible_without_prices():
    run = run_of(multi_epoch_case("one", [(100, 10), (200, 20)]))

    report = render_run(run)
    assert "- Recorded usage across all epochs: 300 input / 30 output tokens" in report
    assert "Estimated total evaluation cost" not in report
