"""Markdown reports for a single run and for a comparison."""

from statistics import median

from agent_accelerator import readings
from agent_accelerator.compare import CaseResult, Comparison, MedianChange, RateInterval, RunResults, Statistics
from agent_accelerator.judge import BASELINE_GAPS, INTERRUPTED, JudgedEpoch
from agent_accelerator.run_metrics import run_metric_lines
from agent_accelerator.stats import cohen_kappa, pass_at_k, pass_hat_k, wilson_interval
from agent_accelerator.tool_metrics import tool_use_lines
from agent_accelerator.trace_summary import TraceSummary


def _latency(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}s"


def _tokens(input_tokens: int | None, output_tokens: int | None) -> str:
    if input_tokens is None and output_tokens is None:
        return "n/a"
    return f"{_count(input_tokens)}/{_count(output_tokens)}"


def _count(value: int | None) -> str:
    return "n/a" if value is None else f"{value:,}"


def _tool_call_count(value: float | None) -> str:
    if value is None:
        return "n/a"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def validate_prices(input_price: float | None, output_price: float | None) -> None:
    """Prices are USD per million tokens, supplied by the user; none are stored here."""
    if (input_price is None) != (output_price is None):
        raise ValueError("give both --input-price and --output-price, or neither")
    for name, price in (("input", input_price), ("output", output_price)):
        if price is not None and not price >= 0:
            raise ValueError(f"--{name}-price must be >= 0, got {price}")


def _cost_line(run: RunResults, input_price: float | None, output_price: float | None) -> list[str]:
    if input_price is None or output_price is None or run.input_tokens is None or run.output_tokens is None:
        return []
    cost = (run.input_tokens * input_price + run.output_tokens * output_price) / 1_000_000
    return [f"- Estimated cost: ${cost:.4f} (at ${input_price:g}/${output_price:g} per million tokens)"]


def _failure_text(case: CaseResult) -> str:
    return "; ".join(case.failures.values())


def _reason(case: CaseResult) -> str:
    """Failure text escaped for a Markdown table cell."""
    return _failure_text(case).replace("|", "\\|")


def _result(case: CaseResult) -> str:
    verdict = "pass" if case.passed else "FAIL"
    return verdict if case.runs == 1 else f"{verdict} ({case.passes}/{case.runs})"


def render_run(
    run: RunResults,
    traces: list[TraceSummary] | None = None,
    input_price: float | None = None,
    output_price: float | None = None,
) -> str:
    validate_prices(input_price, output_price)
    tokens = "n/a"
    if run.input_tokens is not None or run.output_tokens is not None:
        tokens = f"{_count(run.input_tokens)} in / {_count(run.output_tokens)} out per run"
    passed = sum(c.passed for c in run.cases.values())
    lines = [
        f"# Run {run.run_id}",
        "",
        f"- Status: {run.status}",
        f"- Passed: {passed}/{len(run.cases)} ({run.pass_rate:.1%})",
        f"- Error rate: {run.error_rate:.1%}",
        f"- Median latency: {_latency(run.median_latency_s)} (informational)",
        f"- Tokens: {tokens} (informational)",
        *_cost_line(run, input_price, output_price),
        f"- Dataset sha256: `{run.dataset_sha256}`",
        f"- Log: `{run.log_path.as_posix()}`",
        "",
        *readings.summary_lines(run),
        "| Case | Result | Latency | Tokens (in/out) | Tool calls | Failure |",
        "|------|--------|---------|-----------------|------------|---------|",
    ]
    for case in _ordered(run):
        tokens = _tokens(case.input_tokens, case.output_tokens)
        calls = _tool_call_count(case.tool_calls)
        failure = _reason(case)
        # An empty Markdown table cell is "| |", not "|  |"; keep existing failure text unchanged.
        failure_cell = f" {failure}" if failure else ""
        lines.append(
            f"| {case.id} | {_result(case)} | {_latency(case.latency_s)} | {tokens} | {calls} |{failure_cell} |"
        )
    reliability = _reliability_lines(run)
    lines += reliability
    tool_use = tool_use_lines(c.tool_use for c in _ordered(run))
    lines += _explained(tool_use, "tool_use", readings.tool_use_readings(_ordered(run)))
    metrics = _sections(run_metric_lines(run, input_price, output_price))
    for section in metrics:
        key, found = _METRIC_SECTIONS[section[1]]
        lines += _explained(section, key, found(run))
    judge, has_calibration = _judge_lines(run.judge)
    lines += judge
    if traces:
        lines += _trace_lines(traces)
    has_performance = any(section[1] == "## Performance and cost" for section in metrics)
    keys = readings.run_glossary_keys(bool(reliability), has_performance)
    lines += readings.glossary_lines(keys + readings.judge_glossary_keys(run.judge, has_calibration), lines)
    return "\n".join(lines) + "\n"


_METRIC_SECTIONS = {
    "## Performance and cost": ("performance", readings.performance_readings),
    "## Failures": ("failures", readings.failure_readings),
    "## Consistency": ("consistency", readings.consistency_readings),
}


def _sections(lines: list[str]) -> list[list[str]]:
    """Split report lines into sections, each starting with the blank line before its "## " heading."""
    starts = [i - 1 for i, line in enumerate(lines) if line.startswith("## ")]
    return [lines[a:b] for a, b in zip(starts, [*starts[1:], len(lines)], strict=False)]  # no headings: no sections


def _explained(section: list[str], key: str, found: list[str]) -> list[str]:
    """A section with its plain-English note under the heading and its readings at the end."""
    if not section:
        return []
    return [*section[:3], readings.note(key), "", *section[3:], *readings.reading_lines(found)]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _reliability_lines(run: RunResults) -> list[str]:
    """Only for multi-epoch runs. k is the fewest epochs any case ran, so every case supports it."""
    cases = _ordered(run)
    if not any(c.runs > 1 for c in cases):
        return []
    k = min(c.runs for c in cases)
    pass_at_1 = _mean([c.passes / c.runs for c in cases])
    at_k = _mean([pass_at_k(c.passes, c.runs, k) for c in cases])
    hat_k = _mean([pass_hat_k(c.passes, c.runs, k) for c in cases])
    lines = [
        "",
        f"## Reliability (k = {k})",
        "",
        readings.note("reliability"),
        "",
        f"- Mean pass@1: {pass_at_1:.1%}",
    ]
    if k > 1:  # at k = 1, pass@k and pass^k are both pass@1
        lines += [
            f"- Mean pass@{k}: {at_k:.1%} (at least one of {k} tries passes)",
            f"- Mean pass^{k}: {hat_k:.1%} (all {k} tries pass)",
        ]
    if k < 5:
        lines.append(
            f"- Intervals are wide at {readings.counted(k, 'epoch', 'epochs')}; run more for a tighter estimate."
        )
    lines += ["", "| Case | Passes | Pass rate [95% CI] |", "|------|--------|--------------------|"]
    for case in cases:
        low, high = wilson_interval(case.passes, case.runs)
        rate = f"{case.passes / case.runs:.0%} [{low:.0%}, {high:.0%}]"
        lines.append(f"| {case.id} | {case.passes}/{case.runs} | {rate} |")
    return lines + readings.reading_lines(readings.reliability_readings(cases, k, at_k, hat_k))


_JUDGE_MODES = {"golden": "golden", "reference_free": "reference-free", "pairwise": "pairwise"}


def _judge_modes(epochs: tuple[JudgedEpoch, ...]) -> str:
    """The mode, or each mode with its case count when cases were judged in more than one."""
    by_case: dict[str, str] = {}
    for epoch in epochs:
        if epoch.mode is not None:
            by_case.setdefault(epoch.case_id, epoch.mode)
    counts: dict[str, int] = {}
    for mode in by_case.values():
        counts[mode] = counts.get(mode, 0) + 1
    order = [m for m in _JUDGE_MODES if m in counts] + sorted(m for m in counts if m not in _JUDGE_MODES)
    if not order:
        return "n/a"
    if len(order) == 1:
        return _JUDGE_MODES.get(order[0], order[0])
    return ", ".join(f"{_JUDGE_MODES.get(m, m)} ({readings.counted(counts[m], 'case', 'cases')})" for m in order)


def _criteria_lines(epochs: tuple[JudgedEpoch, ...], unit: tuple[str, str]) -> list[str]:
    """Reference-free criteria in rubric order, each with its failing epochs and the cases they hit."""
    judged = [e for e in epochs if e.mode == "reference_free" and e.outcome in ("pass", "fail") and e.criteria]
    if not judged:
        return []
    failing: dict[str, list[str]] = {}
    for epoch in judged:
        for name, passed in epoch.criteria:
            failing.setdefault(name, [])
            if not passed:
                failing[name].append(epoch.case_id)
    lines = [
        "",
        f"Reference-free criteria, over {readings.counted(len(judged), *unit)} judged:",
        "",
        "| Criterion | Failing epochs | Cases |",
        "|-----------|----------------|-------|",
    ]
    return lines + [f"| {name} | {len(ids)} | {len(set(ids))} |" for name, ids in failing.items()]


def _calibration(epochs: tuple[JudgedEpoch, ...]) -> tuple[list[tuple[str, str, str]], int, int]:
    """(case id, judge verdict, human label) per judged epoch of a labelled golden case, the labelled case count, and
    how many of those cases have a verdict to compare, which is the count the kappa minimum applies to."""
    labelled = [e for e in epochs if e.mode == "golden" and e.human_label is not None]
    pairs = [(e.case_id, e.outcome, e.human_label) for e in labelled if e.outcome in ("pass", "fail") and e.human_label]
    return pairs, len({e.case_id for e in labelled}), len({case_id for case_id, _, _ in pairs})


def _calibration_lines(
    pairs: list[tuple[str, str, str]], labelled: int, comparable: int, kappa: float | None
) -> list[str]:
    compared = readings.counted(len(pairs), "verdict", "verdicts")
    lines = [f"- Human-labelled golden cases: {labelled} ({compared} compared)"]
    if not pairs:
        return lines
    agreed = sum(verdict == label for _, verdict, label in pairs)
    lines.append(f"- Agreement with human labels: {agreed}/{len(pairs)} ({agreed / len(pairs):.1%})")
    if comparable < readings.MIN_KAPPA_LABELS:
        kappa_text = f"needs at least {readings.MIN_KAPPA_LABELS} labelled cases (have {comparable})"
    elif kappa is None:
        kappa_text = "undefined (every labelled case got the same verdict from both)"
    else:
        kappa_text = f"{kappa:.2f}"
    return [*lines, f"- Cohen's kappa: {kappa_text}"]


def _pairwise_lines(epochs: tuple[JudgedEpoch, ...]) -> list[str]:
    """Pairwise verdict counts against the baseline; nothing when no case was judged pairwise."""
    if not any(e.mode == "pairwise" for e in epochs):
        return []
    counts = {v: sum(e.pairwise == v for e in epochs) for v in ("better", "same", "worse")}
    gaps = sum(e.outcome == "not_judged" and e.not_judged in BASELINE_GAPS for e in epochs)
    return [
        f"- Not judged (no baseline answer): {gaps}",
        f"- Against the baseline: {counts['better']} better, {counts['same']} same, {counts['worse']} worse",
        f"- Order disagreements (counted as same): {sum(e.order_disagreed for e in epochs)}",
    ]


def _judge_lines(epochs: tuple[JudgedEpoch, ...]) -> tuple[list[str], bool]:
    """The Judge section and whether it has calibration; nothing when no judge ran.

    Reads only verdict structure, never reasons or answers, so a --capture-content log renders the same.
    """
    if not epochs:
        return [], False
    several = len(epochs) > len({e.case_id for e in epochs})
    unit = ("try", "tries") if several else ("case", "cases")
    verdicts = [e for e in epochs if e.outcome in ("pass", "fail")]
    passed = sum(e.outcome == "pass" for e in verdicts)
    rate = f" ({passed / len(verdicts):.1%})" if verdicts else ""
    models = sorted({e.model for e in epochs if e.model is not None})
    agent_skipped = sum(e.outcome == "not_judged" and e.not_judged not in (*BASELINE_GAPS, INTERRUPTED) for e in epochs)
    interrupted = sum(e.outcome == "not_judged" and e.not_judged == INTERRUPTED for e in epochs)
    lines = [
        "",
        "## Judge",
        "",
        readings.note("judge"),
        "",
        f"- Mode: {_judge_modes(epochs)}",
        f"- Judge model: {', '.join(f'`{m}`' for m in models) or 'n/a'}",
        f"- Judged: {len(verdicts)} of {readings.counted(len(epochs), *unit)}",
        f"- Judge passed: {passed}/{len(verdicts)}{rate}",
        f"- Judge errors: {sum(e.outcome == 'error' for e in epochs)}",
        f"- Not judged (agent error): {agent_skipped}",
    ]
    if interrupted:
        lines.append(f"- Not judged (interrupted): {interrupted}")
    lines += _pairwise_lines(epochs)
    pairs, labelled, comparable = _calibration(epochs)
    kappa = None
    if pairs and comparable >= readings.MIN_KAPPA_LABELS:
        kappa = cohen_kappa([verdict for _, verdict, _ in pairs], [label for _, _, label in pairs])
    if labelled:
        lines += _calibration_lines(pairs, labelled, comparable, kappa)
    lines += _criteria_lines(epochs, unit)
    return lines + readings.reading_lines(readings.judge_readings(epochs, pairs, comparable, kappa)), bool(labelled)


def _ordered(run: RunResults) -> list[CaseResult]:
    """Failing cases first, then by id."""
    return sorted(run.cases.values(), key=lambda c: (c.passed, c.id))


def render_case_lines(run: RunResults) -> list[str]:
    """Plain-text per-case results for the terminal: the Result and Failure columns of report.md, nothing more."""
    cases = _ordered(run)
    width = max((len(c.id) for c in cases), default=0)
    result_width = max((len(_result(c)) for c in cases), default=0)
    lines = []
    for case in cases:
        line = f"  {case.id:<{width}}  {_result(case):<{result_width}}"
        if not case.passed:
            line += f"  {_failure_text(case)}"
        lines.append(line.rstrip())
    return lines


def _per_epoch(total: int, runs: int) -> str:
    return str(total // runs) if total % runs == 0 else f"{total / runs:.1f}"


def _trace_lines(traces: list[TraceSummary]) -> list[str]:
    """One row per case: counts are averaged per epoch, times are medians across epochs."""
    by_case: dict[str, list[TraceSummary]] = {}
    for summary in traces:
        by_case.setdefault(summary.sample_id, []).append(summary)
    lines = [
        "",
        "## Trace summary (informational)",
        "",
        "| Case | Model calls | Tool calls | Tool errors | Model time | Tool time |",
        "|------|-------------|------------|-------------|------------|-----------|",
    ]
    for case_id, epochs in sorted(by_case.items()):
        runs = len(epochs)
        tools = ", ".join(dict.fromkeys(name for e in epochs for name in e.tool_calls))
        tool_calls = _per_epoch(sum(len(e.tool_calls) for e in epochs), runs) + (f" ({tools})" if tools else "")
        model_calls = _per_epoch(sum(e.model_calls for e in epochs), runs)
        tool_errors = _per_epoch(sum(e.tool_errors for e in epochs), runs)
        model_time = _latency(median(e.model_time_s for e in epochs))
        tool_time = _latency(median(e.tool_time_s for e in epochs))
        lines.append(f"| {case_id} | {model_calls} | {tool_calls} | {tool_errors} | {model_time} | {tool_time} |")
    return lines


def render_comparison(cmp: Comparison) -> str:
    base, cur = cmp.baseline, cmp.current
    lines = [
        f"# Comparison: {cur.run_id} vs baseline {base.run_id}",
        "",
        f"**{'REGRESSION' if cmp.regressed else 'OK'}**",
        "",
    ]
    epochs = readings.comparison_epochs(cmp)
    shown: set[str] = set()  # a Fisher regression and its warning share one reading; give it once
    for label, texts in (("Regression", cmp.regressions), ("Warning", cmp.warnings)):
        for text in texts:
            lines.append(f"- {label}: {text}")
            reading = readings.warning_reading(text, epochs)
            if reading and reading not in shown:
                lines.append(f"  - {reading}")
                shown.add(reading)
    lines += [
        "",
        "| Metric | Baseline | Current |",
        "|--------|----------|---------|",
        f"| Pass rate | {base.pass_rate:.1%} | {cur.pass_rate:.1%} |",
        f"| Error rate | {base.error_rate:.1%} | {cur.error_rate:.1%} |",
        f"| Median latency (informational) | {_latency(base.median_latency_s)} | {_latency(cur.median_latency_s)} |",
        f"| Tokens per run (informational) | {_tokens(base.input_tokens, base.output_tokens)} |"
        f" {_tokens(cur.input_tokens, cur.output_tokens)} |",
        "",
    ]
    for title, ids in (
        ("Newly failing", cmp.newly_failing),
        ("Newly passing", cmp.newly_passing),
        ("Still failing", cmp.still_failing),
        ("Added", cmp.added),
        ("Removed", cmp.removed),
    ):
        if not ids:
            continue
        lines += [f"## {title}", ""]
        for case_id in ids:
            case = cur.cases.get(case_id)
            detail = f" ({_result(case)}): {_reason(case)}" if case and not case.passed else ""
            lines.append(f"- {case_id}{detail}")
        lines.append("")
    if cmp.statistics is not None:
        lines += _statistics_lines(cmp.statistics, epochs)
    lines += readings.glossary_lines(readings.comparison_glossary_keys(cmp), lines)
    return "\n".join(lines)


def _rate_text(rate: RateInterval) -> str:
    return f"{rate.rate:.1%} [{rate.low:.1%}, {rate.high:.1%}] ({rate.passes}/{rate.cases})"


def _change_text(change: MedianChange, unit: str, digits: int) -> str:
    bounds = f"[{change.low:+.{digits}f}, {change.high:+.{digits}f}]"
    return f"{change.median:+.{digits}f}{unit} {bounds} over {change.pairs} cases"


def _statistics_lines(stats: Statistics, epochs: int = 1) -> list[str]:
    """Compact informational block; intervals are 95%, changes are current minus baseline.

    Each statistic is followed by an indented plain-English verdict. epochs is per case on the side with fewer,
    and decides with the paired count whether the block opens by saying its evidence is weak.
    """
    lines = [
        "## Statistics (informational)",
        "",
        readings.note("statistics"),
        "",
        *readings.evidence_line(stats, epochs),
        f"- Pass rate over cases (95% Wilson): baseline {_rate_text(stats.baseline)}, "
        f"current {_rate_text(stats.current)}. The true rate plausibly lies in the brackets.",
        f"  - {readings.wilson_verdict(stats)}",
    ]
    if stats.difference is not None:
        delta = stats.current.rate - stats.baseline.rate
        low, high = stats.difference
        lines.append(
            f"- Pass rate change: {delta * 100:+.1f} points [{low * 100:+.1f}, {high * 100:+.1f}] (95% Newcombe). "
            "An interval that excludes 0 suggests a real change."
        )
        lines.append(f"  - {readings.newcombe_verdict(delta, low, high)}")
    p = f"{stats.mcnemar_p:.3f}" if stats.mcnemar_p >= 0.001 else "<0.001"
    lines.append(
        f"- McNemar exact p = {p} over {stats.paired} paired cases ({stats.passed_to_failed} passed->failed, "
        f"{stats.failed_to_passed} failed->passed). The chance of a split at least this uneven if nothing changed."
    )
    lines.append(f"  - {readings.mcnemar_verdict(stats)}")
    if stats.latency_s is not None:
        lines.append(
            f"- Median latency change per case: {_change_text(stats.latency_s, 's', 3)} (95% bootstrap). "
            "Positive means slower."
        )
        amount = f"{abs(stats.latency_s.median):.3f}s"
        verdict = readings.bootstrap_verdict(
            stats.latency_s, ("slower", f"took {amount} longer"), ("faster", f"took {amount} less")
        )
        lines.append(f"  - {verdict}")
    if stats.tokens is not None:
        lines.append(
            f"- Median token change per case: {_change_text(stats.tokens, '', 0)} (95% bootstrap). "
            "Positive means more tokens."
        )
        amount = f"{abs(stats.tokens.median):,.0f}"
        verdict = readings.bootstrap_verdict(
            stats.tokens,
            ("heavier on tokens", f"used {amount} more tokens"),
            ("lighter on tokens", f"used {amount} fewer tokens"),
        )
        lines.append(f"  - {verdict}")
    lines.append("")
    return lines
