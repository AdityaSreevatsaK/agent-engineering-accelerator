from pathlib import Path

import pytest
from inspect_ai.log import EvalSample
from inspect_ai.scorer import CORRECT, INCORRECT, Score

from agent_accelerator.compare import CaseResult, RunResults
from agent_accelerator.run_metrics import EpochMetrics, epoch_metrics, estimated_cost, percentile, run_metric_lines

# Expected values below are worked by hand from the brief, never pasted from a run.


def sample(*, usage=None, scores=None, total_time=None):
    return EvalSample(
        id="case",
        epoch=1,
        input="x",
        target="",
        metadata={} if usage is None else {"usage": usage},
        scores=scores,
        total_time=total_time,
    )


def checks_score(*, passed=True, metadata=None):
    return Score(value=CORRECT if passed else INCORRECT, metadata=metadata)


def epoch(*, latency=None, tokens=(None, None), failed=(), digest=None):
    return EpochMetrics(
        latency_s=latency,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        failed_checks=tuple(failed),
        output_digest=digest,
    )


def case_of(case_id, epochs=(), *, passed=True, tokens=(None, None)):
    return CaseResult(
        id=case_id,
        passed=passed,
        error=None,
        latency_s=None,
        failures={},
        runs=max(len(epochs), 1),
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        epochs=tuple(epochs),
    )


def run_of(*cases):
    return RunResults(
        run_id="run",
        log_path=Path("run.json"),
        dataset_sha256=None,
        status="success",
        cases={c.id: c for c in cases},
    )


def section(lines, title):
    """The lines of one report section, from its heading to the next heading; [] when absent."""
    heading = f"## {title}"
    if heading not in lines:
        return []
    start = lines.index(heading)
    rest = lines[start + 1 :]
    end = next((i for i, line in enumerate(rest) if line.startswith("## ")), len(rest))
    return [line for line in rest[:end] if line]


def bullets(lines, title):
    return [line for line in section(lines, title) if line.startswith("- ")]


# percentile


@pytest.mark.parametrize(
    ("p", "expected"),
    [
        # n = 5: rank ceil(p * 5 / 100). 40 * 5 / 100 is exactly 2, so the rank is 2, not 3.
        (5, 15.0),
        (20, 15.0),
        (21, 20.0),
        (40, 20.0),
        (50, 35.0),
        (80, 40.0),
        (81, 50.0),
        (100, 50.0),
    ],
    ids=["p5-rank1", "p20-exact-rank1", "p21-rank2", "p40-exact-rank2", "p50-rank3", "p80-rank4", "p81-rank5", "p100"],
)
def test_percentile_is_the_observed_value_at_nearest_rank_of_the_sorted_list(p, expected):
    # Witness: s22 percentile rank rounds up past an exact rank (`+ 100`), s22 percentile rank floored (`// 100`
    # without `+ 99`), s22 percentile unsorted (`ordered = list(values)`).
    assert percentile([50.0, 15.0, 40.0, 20.0, 35.0], p) == expected


def test_percentile_of_one_value_is_that_value_at_every_rank():
    # Witness: s22 percentile rank rounds up past an exact rank (p100 of one value reads past the end).
    assert [percentile([7.5], p) for p in (1, 50, 100)] == [7.5, 7.5, 7.5]


def test_percentile_leaves_the_input_list_in_its_original_order():
    # Witness: s22 percentile sorts in place (`values.sort(); ordered = values`).
    values = [3.0, 1.0, 2.0]

    assert percentile(values, 50) == 2.0
    assert values == [3.0, 1.0, 2.0]


@pytest.mark.parametrize(
    ("values", "p"),
    [([], 50), ([1.0], 0), ([1.0], -5), ([1.0], 101)],
    ids=["empty", "p-zero", "p-negative", "p-over-100"],
)
def test_percentile_rejects_an_empty_list_and_p_outside_zero_exclusive_to_100(values, p):
    # Witness: s22 percentile empty unchecked, s22 percentile p zero accepted, s22 percentile p over 100 accepted.
    with pytest.raises(ValueError):
        percentile(values, p)


# epoch_metrics


def test_epoch_metrics_reads_latency_tokens_digest_and_failed_checks_from_one_sample():
    # Witness: s22 epoch latency dropped, s22 epoch tokens swapped, s22 epoch digest dropped.
    s = sample(
        usage={"inputTokens": 1200, "outputTokens": 340},
        scores={
            "case_checks": checks_score(
                passed=False,
                metadata={
                    "checks": {"expected_output": False, "tool_calls": True},
                    "output_digest": "0123456789abcdef",
                },
            )
        },
        total_time=2.5,
    )

    metrics = epoch_metrics(s, {"case_checks": "wrong answer"})

    assert metrics == EpochMetrics(
        latency_s=2.5,
        input_tokens=1200,
        output_tokens=340,
        failed_checks=("expected_output",),
        output_digest="0123456789abcdef",
    )


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ("1200 in", (None, None)),
        (["inputTokens", 1200], (None, None)),
        ({"inputTokens": True, "outputTokens": False}, (None, None)),
        ({"inputTokens": "1200", "outputTokens": 3.5}, (None, None)),
        ({"inputTokens": 0, "outputTokens": 9}, (0, 9)),
        ({"outputTokens": 9}, (None, 9)),
    ],
    ids=["string", "list", "bools", "str-and-float", "zero-is-kept", "one-field-missing"],
)
def test_epoch_metrics_keeps_only_non_bool_int_token_counts_from_a_usage_dict(usage, expected):
    # Witness: s22 epoch usage bool accepted, s22 epoch usage any type accepted, s22 epoch usage not dict crashes.
    metrics = epoch_metrics(sample(usage=usage), {})

    assert (metrics.input_tokens, metrics.output_tokens) == expected


@pytest.mark.parametrize(
    "scores",
    [
        {"case_checks": checks_score(metadata={"output_digest": 12345})},
        {"case_checks": checks_score(metadata={"output_digest": b"0123456789abcdef"})},
        {"case_checks": checks_score(metadata=None)},
        {"other": checks_score(metadata={"output_digest": "0123456789abcdef"})},
        None,
    ],
    ids=["int-digest", "bytes-digest", "no-score-metadata", "digest-on-another-scorer", "no-scores"],
)
def test_epoch_metrics_has_no_digest_unless_case_checks_recorded_a_string(scores):
    # Witness: s22 epoch digest any type accepted, s22 epoch digest from any scorer.
    assert epoch_metrics(sample(scores=scores), {}).output_digest is None


@pytest.mark.parametrize(
    ("failures", "checks", "expected"),
    [
        (
            {"case_checks": "x"},
            {"expected_output": False, "tool_calls": True, "max_tool_calls": False},
            ("expected_output", "max_tool_calls"),
        ),
        ({"case_checks": "x"}, None, ("case_checks",)),
        ({"case_checks": "x"}, ["expected_output"], ("case_checks",)),
        # A failing case_checks whose checks all passed still names something rather than vanishing.
        ({"case_checks": "x"}, {"expected_output": True}, ("case_checks",)),
        ({"extra": "x"}, {"expected_output": False}, ("extra",)),
        ({"case_checks": "x", "extra": "y"}, {"tool_calls": False}, ("tool_calls", "extra")),
        ({"unscored": "no score recorded"}, None, ("unscored",)),
        ({}, {"expected_output": False}, ()),
    ],
    ids=[
        "case-checks-split-into-false-checks",
        "no-checks-metadata-falls-back",
        "checks-not-a-dict-falls-back",
        "no-false-check-falls-back",
        "other-scorer-not-split",
        "both-scorers",
        "unscored",
        "passed-epoch",
    ],
)
def test_epoch_metrics_names_failed_case_checks_by_check_and_other_scorers_by_name(failures, checks, expected):
    # Witness: s22 failed checks no fallback, s22 failed checks split every scorer, s22 failed checks from metadata
    # on a passed epoch.
    metadata = {} if checks is None else {"checks": checks}
    s = sample(scores={"case_checks": checks_score(passed="case_checks" not in failures, metadata=metadata)})

    assert epoch_metrics(s, failures).failed_checks == expected


# estimated_cost


def test_estimated_cost_prices_one_pass_of_per_epoch_average_tokens_per_million():
    # Two cases at 1,000/500 and 3,000/1,500 tokens: 4,000 * $3 + 2,000 * $15 = $42,000 per million = $0.042.
    # Witness: s22 cost not per million, s22 cost prices swapped.
    run = run_of(case_of("a", tokens=(1000, 500)), case_of("b", tokens=(3000, 1500)))

    assert estimated_cost(run, 3.0, 15.0) == pytest.approx(0.042)


@pytest.mark.parametrize(
    ("prices", "tokens"),
    [((None, 15.0), (1000, 500)), ((3.0, None), (1000, 500)), ((3.0, 15.0), (None, 500)), ((3.0, 15.0), (1000, None))],
    ids=["no-input-price", "no-output-price", "no-input-tokens", "no-output-tokens"],
)
def test_estimated_cost_is_none_without_both_prices_and_both_token_totals(prices, tokens):
    # Witness: s22 cost needs only the input side.
    assert estimated_cost(run_of(case_of("a", tokens=tokens)), *prices) is None


def test_estimated_cost_of_free_tokens_is_zero_not_missing():
    # Witness: s22 cost zero price treated as missing.
    assert estimated_cost(run_of(case_of("a", tokens=(1000, 500))), 0.0, 0.0) == 0.0


# Performance and cost


def test_no_metric_sections_for_a_run_without_epoch_data_tokens_or_prices():
    # Witness: s22 performance heading always emitted.
    run = run_of(case_of("a", [epoch(), epoch()]), case_of("b", [epoch()]))

    assert run_metric_lines(run, 3.0, 15.0) == []


def test_latency_line_reports_nearest_rank_p50_p90_p95_and_max_over_case_epochs():
    # 20 latencies 1..20 s: ranks 10, 18 and 19. A None latency is left out of n.
    # Witness: s22 latency n counts missing, s22 latency p90 is p95.
    epochs = [epoch(latency=float(s)) for s in range(20, 0, -1)] + [epoch()]
    run = run_of(case_of("a", epochs[:7]), case_of("b", epochs[7:]))

    assert bullets(run_metric_lines(run, None, None), "Performance and cost") == [
        "- Latency per case-epoch (n=20): p50 10.000s, p90 18.000s, p95 19.000s, max 20.000s",
    ]


def test_token_lines_appear_independently_of_latency_and_of_each_other():
    # Input tokens 100, 200, 1500, 2500 (n=4): p50 rank 2, p95 rank ceil(3.8) = 4. Output tokens only twice: 7, 9.
    # Witness: s22 token lines need latency.
    run = run_of(
        case_of("a", [epoch(tokens=(1500, 7)), epoch(tokens=(100, None))]),
        case_of("b", [epoch(tokens=(2500, None)), epoch(tokens=(200, 9))]),
    )

    assert bullets(run_metric_lines(run, None, None), "Performance and cost") == [
        "- Input tokens per case-epoch (n=4): p50 200, p95 2,500",
        "- Output tokens per case-epoch (n=2): p50 7, p95 9",
    ]


def test_cost_line_divides_one_pass_cost_by_cases_and_by_passing_cases():
    # $0.042 as above over 2 cases is $0.0210 each; one case passed, so $0.0420 per passing case.
    # Witness: s22 cost per passing case over all cases.
    run = run_of(case_of("a", tokens=(1000, 500), passed=True), case_of("b", tokens=(3000, 1500), passed=False))

    assert bullets(run_metric_lines(run, 3.0, 15.0), "Performance and cost") == [
        "- Cost per case: $0.0210; per passing case: $0.0420",
    ]


def test_cost_line_uses_per_epoch_average_tokens_not_the_sum_over_epochs():
    # One case, two epochs of 1,000 and 3,000 input tokens: compare stores the 2,000 average, so one pass costs
    # 2,000 * $1 per million = $0.0020, not $0.0040 for both epochs. Witness: s22 cost sums epoch tokens.
    run = run_of(
        case_of("a", [epoch(tokens=(1000, 0)), epoch(tokens=(3000, 0))], tokens=(2000, 0), passed=True),
    )

    cost_lines = [b for b in bullets(run_metric_lines(run, 1.0, 1.0), "Performance and cost") if "Cost" in b]
    assert cost_lines == ["- Cost per case: $0.0020; per passing case: $0.0020"]


def test_cost_per_passing_case_is_not_applicable_when_no_case_passed():
    # Witness: s22 cost no passing case divides by zero.
    run = run_of(case_of("a", tokens=(1000, 500), passed=False), case_of("b", tokens=(3000, 1500), passed=False))

    assert bullets(run_metric_lines(run, 3.0, 15.0), "Performance and cost") == [
        "- Cost per case: $0.0210; per passing case: n/a (no case passed)",
    ]


@pytest.mark.parametrize(
    ("prices", "tokens"),
    [((None, 15.0), (1000, 500)), ((3.0, None), (1000, 500)), ((3.0, 15.0), (None, 500)), ((3.0, 15.0), (1000, None))],
    ids=["no-input-price", "no-output-price", "no-input-tokens", "no-output-tokens"],
)
def test_cost_line_is_omitted_without_both_prices_and_both_token_totals(prices, tokens):
    # Witness: s22 cost needs only the input side.
    lines = run_metric_lines(run_of(case_of("a", [epoch(latency=1.0)], tokens=tokens)), *prices)

    assert section(lines, "Performance and cost")
    assert not [b for b in bullets(lines, "Performance and cost") if b.startswith("- Cost")]


def test_cost_line_at_zero_prices_shows_zero_cost():
    # Witness: s22 cost line dropped when free (if cost and run.cases).
    run = run_of(case_of("a", tokens=(1000, 500), passed=True))

    assert bullets(run_metric_lines(run, 0.0, 0.0), "Performance and cost") == [
        "- Cost per case: $0.0000; per passing case: $0.0000",
    ]


# Failures


def test_failures_section_is_omitted_when_no_epoch_failed():
    # Witness: s22 failures section always emitted.
    run = run_of(case_of("a", [epoch(digest="d1"), epoch(digest="d1")]))

    assert section(run_metric_lines(run, None, None), "Failures") == []


def demo_run():
    """The calculator flaky agent at 5 epochs: subtract and subtract_large each fail two epochs on both checks
    and give a second output in those two epochs; every other case is uniform and passes."""
    ids = ["add", "divide", "multiply", "power", "sqrt", "modulo", "negate", "square", "subtract", "subtract_large"]
    cases = []
    for case_id in ids:
        flaky = case_id.startswith("subtract")
        epochs = [
            epoch(failed=("expected_output", "tool_calls"), digest="bad")
            if flaky and number < 2
            else epoch(digest="good")
            for number in range(5)
        ]
        cases.append(case_of(case_id, epochs, passed=not flaky))
    return run_of(*cases)


def test_failures_section_on_the_flaky_demo_counts_case_epochs_checks_and_cases():
    # Witness: s22 failing case-epochs counts checks, s22 failures total counts failing only.
    assert section(run_metric_lines(demo_run(), None, None), "Failures") == [
        "- Failing case-epochs: 4/50",
        "| Check | Failing epochs | Cases |",
        "|-------|----------------|-------|",
        "| expected_output | 4 | 2 |",
        "| tool_calls | 4 | 2 |",
    ]


def test_failure_rows_sort_by_failing_epochs_descending_then_name():
    # Witness: s22 failure rows by name only, s22 failure rows ascending count, s22 failure rows reversed name.
    run = run_of(
        case_of(
            "a", [epoch(failed=("zeta", "beta")), epoch(failed=("zeta", "beta", "alpha")), epoch(failed=("zeta",))]
        ),
        case_of("b", [epoch(failed=("beta",))]),
    )

    rows = [line for line in section(run_metric_lines(run, None, None), "Failures") if line.startswith("| ")][1:]
    assert rows == ["| beta | 3 | 2 |", "| zeta | 3 | 1 |", "| alpha | 1 | 1 |"]


def test_failure_cases_column_counts_distinct_cases_not_epochs():
    # Witness: s22 failure cases column counts epochs.
    run = run_of(
        case_of("a", [epoch(failed=("x",)), epoch(failed=("x",)), epoch(failed=("x",))]),
        case_of("b", [epoch(failed=("x",)), epoch()]),
    )

    lines = section(run_metric_lines(run, None, None), "Failures")
    assert lines[0] == "- Failing case-epochs: 4/5"
    assert lines[3:] == ["| x | 4 | 2 |"]


def test_failure_named_twice_in_one_epoch_counts_once():
    # Witness: s22 failure duplicates within an epoch counted.
    run = run_of(case_of("a", [epoch(failed=("extra", "extra")), epoch()]))

    lines = section(run_metric_lines(run, None, None), "Failures")
    assert lines[0] == "- Failing case-epochs: 1/2"
    assert lines[3:] == ["| extra | 1 | 1 |"]


def test_failure_check_names_escape_the_table_pipe():
    # Witness: s22 failure pipe unescaped.
    run = run_of(case_of("a", [epoch(failed=("judge|strict",))]))

    assert section(run_metric_lines(run, None, None), "Failures")[3:] == ["| judge\\|strict | 1 | 1 |"]


# Consistency


def test_consistency_section_is_omitted_when_no_case_has_two_digests():
    # A case whose second epoch recorded no digest has one digest only, so nothing is measured.
    # Witness: s22 consistency counts missing digests, s22 consistency single digest counted.
    run = run_of(case_of("a", [epoch(digest="d1"), epoch()]), case_of("b", [epoch(digest="d2")]))

    assert section(run_metric_lines(run, None, None), "Consistency") == []


def test_consistency_on_the_flaky_demo_is_92_percent_with_both_subtract_cases_least_consistent():
    # Eight cases at 5/5 and two at 3/5: (8 * 1.0 + 2 * 0.6) / 10 = 92.0%.
    # Witness: s22 consistency least common share.
    assert bullets(run_metric_lines(demo_run(), None, None), "Consistency") == [
        "- Mean output consistency across epochs: 92.0%",
        "- Least consistent: subtract (60%), subtract_large (60%)",
    ]


def test_consistency_share_is_the_most_common_digest_over_epochs_that_recorded_one():
    # c: d1 twice of 4 is 50%, not the 25% of either single digest. a: d1, d1 and a missing digest is 2/2.
    # b: 3 of 4 is 75%. d has one digest, so is not measured and not in the mean: (50 + 100 + 75) / 3 = 75.0%, where
    # dividing by all four cases would give 56.2%. Witness: s22 consistency mean denominator.
    run = run_of(
        case_of("c", [epoch(digest="d1"), epoch(digest="d1"), epoch(digest="d2"), epoch(digest="d3")]),
        case_of("a", [epoch(digest="d1"), epoch(digest="d1"), epoch()]),
        case_of("b", [epoch(digest="x"), epoch(digest="x"), epoch(digest="x"), epoch(digest="y")]),
        case_of("d", [epoch(digest="z"), epoch()]),
    )

    assert bullets(run_metric_lines(run, None, None), "Consistency") == [
        "- Mean output consistency across epochs: 75.0%",
        "- Least consistent: c (50%), b (75%)",
    ]


def test_least_consistent_orders_by_share_then_case_id():
    # Witness: s22 least consistent by id only, s22 least consistent highest first.
    two_way = [epoch(digest="d1"), epoch(digest="d2")]
    run = run_of(
        case_of("zulu", two_way),
        case_of("mike", [epoch(digest="d1"), epoch(digest="d1"), epoch(digest="d1"), epoch(digest="d2")]),
        case_of("alpha", two_way),
    )

    assert bullets(run_metric_lines(run, None, None), "Consistency")[1] == (
        "- Least consistent: alpha (50%), zulu (50%), mike (75%)"
    )


@pytest.mark.parametrize(
    ("varied", "expected"),
    [
        (5, "- Least consistent: c0 (50%), c1 (50%), c2 (50%), c3 (50%), c4 (50%)"),
        (7, "- Least consistent: c0 (50%), c1 (50%), c2 (50%), c3 (50%), c4 (50%) and 2 more"),
    ],
    ids=["exactly-five-no-tail", "seven-capped-at-five"],
)
def test_least_consistent_lists_at_most_five_cases_and_counts_the_rest(varied, expected):
    # Witness: s22 least consistent tail at five, s22 least consistent uncapped.
    run = run_of(*(case_of(f"c{i}", [epoch(digest="d1"), epoch(digest="d2")]) for i in range(varied)))

    assert bullets(run_metric_lines(run, None, None), "Consistency")[1] == expected


def test_consistency_reports_every_case_consistent_when_every_share_is_100_percent():
    # Witness: s22 all-consistent message dropped.
    run = run_of(
        case_of("a", [epoch(digest="d1"), epoch(digest="d1")]),
        case_of("b", [epoch(digest="d2"), epoch(digest="d2"), epoch(digest="d2")]),
    )

    assert bullets(run_metric_lines(run, None, None), "Consistency") == [
        "- Mean output consistency across epochs: 100.0%",
        "- Every case gave the same output in every epoch.",
    ]


def test_run_metric_sections_come_in_performance_failures_consistency_order():
    # Witness: s22 metric sections reordered.
    run = run_of(
        case_of("a", [epoch(latency=1.0, failed=("x",), digest="d1"), epoch(latency=2.0, digest="d2")]),
    )

    headings = [line for line in run_metric_lines(run, None, None) if line.startswith("## ")]
    assert headings == ["## Performance and cost", "## Failures", "## Consistency"]
