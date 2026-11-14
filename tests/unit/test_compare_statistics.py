from fractions import Fraction
from math import comb, sqrt
from pathlib import Path

import pytest

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
from agent_accelerator.report import render_comparison
from agent_accelerator.stats import Z_95, bootstrap_median_interval

HEADER = "## Statistics (informational)"

# Test parameters say `epochs`, not `runs`: tests/conftest.py marks any test with a `runs` argument as slow.


# TODO: make_run duplicates tests/unit/test_compare.py; move both to a shared helper when that file settles.
def make_run(cases=None, *, run_id="run"):
    return RunResults(
        run_id=run_id, log_path=Path("run.json"), dataset_sha256=None, status="success", cases=cases or {}
    )


def make_case(case_id, *, passed=True, latency_s=None, input_tokens=None, output_tokens=None, epochs=1, passes=None):
    return CaseResult(
        id=case_id,
        passed=passed,
        error=None,
        latency_s=latency_s,
        failures={} if passed else {"check": "failed"},
        runs=epochs,
        passes=(epochs if passed else 0) if passes is None else passes,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def run_of(**cases):
    return make_run({case_id: make_case(case_id, **fields) for case_id, fields in cases.items()})


def wilson_bounds(passes, n):
    """Roots of (p - x)^2 = z^2 x (1 - x) / n, solved as a quadratic in x."""
    p, k = passes / n, Z_95 * Z_95 / n
    a, b, c = 1 + k, -(2 * p + k), p * p
    root = sqrt(b * b - 4 * a * c)
    return ((-b - root) / (2 * a), (-b + root) / (2 * a))


def two_sided_exact(b, c):
    """2 * P(X <= min(b, c)) for X ~ Binomial(b + c, 1/2), capped at 1, as an exact fraction."""
    n = b + c
    return min(Fraction(1), 2 * Fraction(sum(comb(n, i) for i in range(min(b, c) + 1)), 2**n))


def statistics_of(baseline, current):
    return compare(baseline, current, Thresholds()).statistics


# Pass rates and the Newcombe difference


def test_pass_rates_count_cases_not_epochs():
    # Witness: in compare.py _rate, change `sum(c.passed for c in run.cases.values())` to `sum(c.passes ...)`; the
    # baseline then counts 4 passes over 2 cases and wilson interval raises.
    # Baseline: "one" passed 3 of 4 epochs but failed as a case, "two" passed its one epoch: 1 case of 2 passes.
    baseline = run_of(one={"passed": False, "epochs": 4, "passes": 3}, two={"passed": True})
    current = run_of(one={"passed": True, "epochs": 4}, two={"passed": True})

    stats = statistics_of(baseline, current)

    assert (stats.baseline.passes, stats.baseline.cases) == (1, 2)
    assert (stats.baseline.low, stats.baseline.high) == pytest.approx(wilson_bounds(1, 2), abs=1e-12)
    assert stats.baseline.rate == 0.5
    assert stats.current.passes == 2 and stats.current.cases == 2
    assert stats.current.high == 1.0


def test_difference_is_current_minus_baseline():
    # Witness: in compare.py _statistics, swap the arguments to newcombe_difference_interval so it reads
    # `(before.passes, before.cases, after.passes, after.cases)`; the interval turns positive and this test fails.
    # All passing to all failing over two cases: Newcombe for 0/2 - 2/2 is [-1, -1 + sqrt(2) * z^2 / (2 + z^2)].
    q = Z_95 * Z_95 / (2 + Z_95 * Z_95)
    baseline = run_of(a={"passed": True}, b={"passed": True})
    current = run_of(a={"passed": False}, b={"passed": False})

    low, high = statistics_of(baseline, current).difference

    assert low == -1.0
    assert high == pytest.approx(-1 + sqrt(2) * q, abs=1e-12)
    assert high < 0


@pytest.mark.parametrize("empty_side", ["baseline", "current"])
def test_difference_is_none_and_mcnemar_is_one_when_a_run_has_no_cases(empty_side):
    # Witness: in compare.py _statistics, change `if before.cases and after.cases` to `if before.cases or
    # after.cases`; newcombe_difference_interval then raises on the empty side.
    full = run_of(a={"passed": True, "latency_s": 1.0})
    baseline, current = (make_run(), full) if empty_side == "baseline" else (full, make_run())

    stats = statistics_of(baseline, current)
    empty = stats.baseline if empty_side == "baseline" else stats.current

    assert stats.difference is None
    assert empty == RateInterval(0, 0, 0.0, 1.0)
    assert empty.rate == 0.0
    assert (stats.paired, stats.passed_to_failed, stats.failed_to_passed, stats.mcnemar_p) == (0, 0, 0, 1.0)
    assert stats.latency_s is None


# McNemar


def test_mcnemar_counts_transitions_over_shared_cases_only():
    # Witness: in compare.py _statistics, change `passed_to_failed=b` to `passed_to_failed=c`; the counts swap.
    # Shared: p1, p2, p3 passed -> failed; f1 failed -> passed; same passed -> passed; still failed -> failed.
    # "gone" (baseline only, passing) and "new" (current only, failing) are not paired and must not count.
    baseline = run_of(
        p1={}, p2={}, p3={}, f1={"passed": False}, same={}, still={"passed": False}, gone={"passed": True}
    )
    current = run_of(
        p1={"passed": False},
        p2={"passed": False},
        p3={"passed": False},
        f1={},
        same={},
        still={"passed": False},
        new={"passed": False},
    )

    stats = statistics_of(baseline, current)

    assert (stats.paired, stats.passed_to_failed, stats.failed_to_passed) == (6, 3, 1)
    assert stats.mcnemar_p == pytest.approx(float(two_sided_exact(3, 1)))  # 2 * (1 + 4) / 16 = 0.625
    assert stats.mcnemar_p == pytest.approx(0.625)


# Latency and tokens


def test_latency_change_is_the_median_of_paired_differences_skipping_missing_latencies():
    # Witness: in compare.py _statistics, change `new.latency_s - old.latency_s` to `old.latency_s - new.latency_s`;
    # the median becomes -2.0 and this test fails.
    # Paired differences in case id order: a +1, b +10, c +2. d lacks a baseline latency, e a current one, and
    # "extra" is unpaired, so none of them count. Median of (1, 10, 2) is 2.
    baseline = run_of(a={"latency_s": 1.0}, b={"latency_s": 2.0}, c={"latency_s": 3.0}, d={}, e={"latency_s": 1.0})
    current = run_of(
        a={"latency_s": 2.0},
        b={"latency_s": 12.0},
        c={"latency_s": 5.0},
        d={"latency_s": 99.0},
        e={},
        extra={"latency_s": 50.0},
    )

    change = statistics_of(baseline, current).latency_s

    assert change.median == 2.0
    assert change.pairs == 3
    # The interval comes from the same deterministic bootstrap, default seed, over the differences in id order.
    _, low, high = bootstrap_median_interval([1.0, 10.0, 2.0])
    assert (change.low, change.high) == (low, high)
    assert 1.0 <= change.low <= change.high <= 10.0


def test_token_change_uses_input_plus_output_only_when_both_runs_report_both():
    # Witness: in compare.py _case_tokens, change `return case.input_tokens + case.output_tokens` to
    # `return case.input_tokens`; y then pairs on input alone, giving four pairs (-5, -100, 0, 0) and median -2.5.
    # Per case totals (baseline -> current): x 150 -> 200 (+50), w 200 -> 120 (-80), v 40 -> 45 (+5).
    # y misses baseline output, z misses current input: both skipped. Median of (+5, -80, +50) is 5.
    baseline = run_of(
        v={"input_tokens": 30, "output_tokens": 10},
        w={"input_tokens": 200, "output_tokens": 0},
        x={"input_tokens": 100, "output_tokens": 50},
        y={"input_tokens": 10},
        z={"input_tokens": 10, "output_tokens": 10},
    )
    current = run_of(
        v={"input_tokens": 25, "output_tokens": 20},
        w={"input_tokens": 100, "output_tokens": 20},
        x={"input_tokens": 100, "output_tokens": 100},
        y={"input_tokens": 10, "output_tokens": 10},
        z={"output_tokens": 10},
    )

    change = statistics_of(baseline, current).tokens

    assert change.pairs == 3
    assert change.median == 5.0
    _, low, high = bootstrap_median_interval([5.0, -80.0, 50.0])
    assert (change.low, change.high) == (low, high)


def test_median_change_intervals_use_seed_zero_and_2000_resamples_over_differences_in_case_id_order():
    # Witness: in compare.py, change `BOOTSTRAP_SEED = 0` to `BOOTSTRAP_SEED = 1`; the latency and token intervals then
    # match the seed-1 reference and this test fails. Control: on these 30 distinct differences seed 1 disagrees.
    # Cases are inserted in reverse id order; differences are taken in sorted id order, c00 first.
    ids = [f"c{i:02d}" for i in reversed(range(30))]
    latency = {case_id: (int(case_id[1:]) * 7) % 31 / 4 for case_id in ids}
    baseline = run_of(**{c: {"latency_s": 1.0, "input_tokens": 100, "output_tokens": 0} for c in ids})
    current = run_of(
        **{c: {"latency_s": 1.0 + latency[c], "input_tokens": 100, "output_tokens": int(latency[c] * 4)} for c in ids}
    )
    differences = [latency[c] for c in sorted(ids)]
    expected = bootstrap_median_interval(differences, 2000, 0)

    stats = statistics_of(baseline, current)

    assert bootstrap_median_interval(differences, 2000, 1) != expected
    assert (stats.latency_s.median, stats.latency_s.low, stats.latency_s.high) == pytest.approx(expected, abs=1e-12)
    tokens = bootstrap_median_interval([d * 4 for d in differences], 2000, 0)
    assert (stats.tokens.median, stats.tokens.low, stats.tokens.high) == tokens
    assert stats.latency_s.pairs == stats.tokens.pairs == 30


def test_latency_and_tokens_are_none_when_no_pair_has_data():
    # Witness: in compare.py _median_change, change `if not differences:` to `if False:`; bootstrap_median_interval
    # then raises on the empty list.
    baseline = run_of(a={"latency_s": 1.0, "input_tokens": 5}, b={})
    current = run_of(a={"output_tokens": 5}, b={"latency_s": 2.0, "input_tokens": 1, "output_tokens": 1})

    stats = statistics_of(baseline, current)

    assert stats.paired == 2
    assert stats.latency_s is None
    assert stats.tokens is None


def test_statistics_never_add_regressions_or_warnings():
    # Witness: in compare.py compare, change `    result.statistics = _statistics(baseline, current)\n` to also
    # append a regression when `result.statistics.mcnemar_p < 0.05`; this test then fails.
    # Ten cases all passing to all failing: McNemar p = 2 / 1024 and the Newcombe interval excludes 0, yet with
    # thresholds that allow the drop nothing gates and nothing warns.
    baseline = run_of(**{f"c{i}": {} for i in range(10)})
    current = run_of(**{f"c{i}": {"passed": False} for i in range(10)})

    result = compare(baseline, current, Thresholds(max_new_failures=10, max_pass_rate_drop=1.0))

    assert result.statistics.mcnemar_p == pytest.approx(2 / 1024)
    assert result.statistics.difference[1] < 0
    assert result.regressions == []
    assert result.warnings == []


# Rendering


def demo_comparison():
    """A ten-case paired experiment with two deliberately changed outcomes, no archived logs."""
    case_ids = [f"c{i}" for i in range(10)]
    baseline = run_of(**{case_id: {} for case_id in case_ids})
    current = run_of(**{case_id: {"passed": case_id not in {"c2", "c7"}} for case_id in case_ids})
    return compare(baseline, current, Thresholds())


def statistics_block(text):
    lines = text.splitlines()
    return lines[lines.index(HEADER) :]


def test_demo_statistics_match_hand_derived_values():
    # Witness: in report.py _statistics_lines, change `[low * 100:+.1f]` / `[high * 100:+.1f]` to
    # `[high * 100:+.1f]` / `[low * 100:+.1f]`; the change line then reads [+11.2, -51.0] and this test fails.
    # 10/10: Wilson low 10 / (10 + z^2) = 72.2%. 8/10: [49.0%, 94.3%]. Newcombe 8/10 - 10/10: [-51.0, +11.2] points.
    # McNemar (2, 0): 2 * P(X <= 0 | n = 2) = 0.5.
    block = "\n".join(statistics_block(render_comparison(demo_comparison())))

    assert "baseline 100.0% [72.2%, 100.0%] (10/10), current 80.0% [49.0%, 94.3%] (8/10)" in block
    assert "Pass rate change: -20.0 points [-51.0, +11.2] (95% Newcombe)" in block
    assert "McNemar exact p = 0.500 over 10 paired cases (2 passed->failed, 0 failed->passed)" in block


def test_statistics_block_is_the_last_section_before_the_glossary_and_appears_once():
    # Witnesses: s26 comparison statistics rendered twice inserts the block above "## Newly failing" too; s26
    # comparison glossary before statistics swaps the last two headings.
    lines = render_comparison(demo_comparison()).splitlines()
    headers = [line for line in lines if line.startswith("## ")]

    assert lines.count(HEADER) == 1
    assert headers[-2:] == [HEADER, "## How to read this report"]  # the glossary alone follows it
    assert "## Newly failing" in headers


def test_statistics_block_is_absent_when_the_comparison_has_no_statistics():
    # Witness: in report.py render_comparison, change `if cmp.statistics is not None:` to `if True:`;
    # _statistics_lines then fails on None.
    assert HEADER not in render_comparison(Comparison(baseline=make_run(), current=make_run()))


def stats_with(**fields):
    defaults = {
        "baseline": RateInterval(2, 4, 0.25, 0.75),
        "current": RateInterval(3, 4, 0.3, 0.9),
        "difference": (-0.2, 0.6),
        "paired": 4,
        "passed_to_failed": 0,
        "failed_to_passed": 1,
        "mcnemar_p": 1.0,
    }
    return Statistics(**{**defaults, **fields})


def render_stats(stats):
    return statistics_block(render_comparison(Comparison(baseline=make_run(), current=make_run(), statistics=stats)))


def test_change_lines_render_signed_medians_and_bounds_with_their_pair_counts():
    # Witness: in report.py _change_text, change `{change.median:+.{digits}f}` to `{change.median:.{digits}f}`; the
    # positive medians lose their sign and this test fails. Also: change `if stats.latency_s is not None:` to
    # `if stats.tokens is not None:` and the latency line goes missing.
    block = render_stats(
        stats_with(latency_s=MedianChange(2.0, 1.0, 10.0, 3), tokens=MedianChange(5.0, -80.0, 50.0, 3))
    )

    latency = [line for line in block if line.startswith("- Median latency change per case:")]
    tokens = [line for line in block if line.startswith("- Median token change per case:")]
    assert latency == [
        "- Median latency change per case: +2.000s [+1.000, +10.000] over 3 cases (95% bootstrap). "
        "Positive means slower."
    ]
    assert tokens == [
        "- Median token change per case: +5 [-80, +50] over 3 cases (95% bootstrap). Positive means more tokens."
    ]


@pytest.mark.parametrize(
    ("present", "prefix"),
    [("latency_s", "- Median latency change per case"), ("tokens", "- Median token change per case")],
    ids=["latency-only", "tokens-only"],
)
def test_each_change_line_follows_its_own_statistic(present, prefix):
    # Witness: in report.py _statistics_lines, change `if stats.latency_s is not None:` to
    # `if stats.tokens is not None:`; latency-only then loses its line and tokens-only raises on None.
    block = render_stats(stats_with(**{present: MedianChange(1.0, 0.0, 2.0, 2)}))

    changes = [line.split(":")[0] for line in block if line.startswith("- Median")]
    assert changes == [prefix]


def test_optional_lines_are_omitted_when_their_statistic_is_none():
    # Witness: in report.py _statistics_lines, change `if stats.difference is not None:` to `if True:`; unpacking
    # None then raises. Likewise `if stats.tokens is not None:` to `if True:` raises on the token line.
    block = render_stats(stats_with(difference=None))

    assert block[0] == HEADER
    assert [line.split(":")[0] for line in block if line.startswith("- ")] == [
        "- Pass rate over cases (95% Wilson)",
        "- McNemar exact p = 1.000 over 4 paired cases (0 passed->failed, 1 failed->passed). The chance of a split at "
        "least this uneven if nothing changed.",
    ]


def test_pass_rate_change_line_is_current_minus_baseline_in_points():
    # Witness: in report.py _statistics_lines, change `stats.current.rate - stats.baseline.rate` to
    # `stats.baseline.rate - stats.current.rate`; the line then reads -25.0 points.
    # 3/4 - 2/4 = +25.0 points; the bounds are the difference tuple times 100.
    block = render_stats(stats_with())

    assert [line for line in block if line.startswith("- Pass rate change:")] == [
        "- Pass rate change: +25.0 points [-20.0, +60.0] (95% Newcombe). An interval that excludes 0 suggests a real "
        "change."
    ]


@pytest.mark.parametrize(
    ("p", "shown"),
    [(0.0004, "<0.001"), (0.000999, "<0.001"), (0.001, "0.001"), (0.0625, "0.062"), (1.0, "1.000")],
    ids=["tiny", "just-below", "boundary", "rounded", "one"],
)
def test_mcnemar_p_prints_three_decimals_or_below_one_thousandth(p, shown):
    # Witness: in report.py _statistics_lines, change `if stats.mcnemar_p >= 0.001` to `if stats.mcnemar_p > 0.001`;
    # the boundary case then prints <0.001. Change `else "<0.001"` to `else "0.000"` for the tiny cases.
    block = render_stats(stats_with(mcnemar_p=p))

    assert [line for line in block if line.startswith("- McNemar")][0].startswith(f"- McNemar exact p = {shown} over")

