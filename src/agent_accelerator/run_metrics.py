"""Per-epoch performance, cost, failure and consistency metrics for the run report.

Percentiles use the nearest-rank method: the p-th percentile of n sorted values is the value at
rank ceil(p * n / 100), so it is always an observed value. All metrics are informational; none is gated.
"""

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from inspect_ai.log import EvalSample

from agent_accelerator.scorers import CASE_CHECKS

if TYPE_CHECKING:
    from agent_accelerator.compare import RunResults

LEAST_CONSISTENT_SHOWN = 5  # cases listed under Consistency


@dataclass(frozen=True)
class EpochMetrics:
    latency_s: float | None
    input_tokens: int | None
    output_tokens: int | None
    failed_checks: tuple[str, ...]  # case_checks check names and other scorer names that failed; empty when passed
    output_digest: str | None  # keyed hash of the final output from case_checks; None for logs without it


def epoch_metrics(sample: EvalSample, failures: dict[str, str]) -> EpochMetrics:
    """failures is the epoch's {scorer name: explanation} for failing scorers, as compare builds it."""
    usage = sample.metadata.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    checks_score = (sample.scores or {}).get(CASE_CHECKS)
    score_metadata = (checks_score.metadata if checks_score else None) or {}
    digest = score_metadata.get("output_digest")
    return EpochMetrics(
        latency_s=sample.total_time,
        input_tokens=_int_or_none(usage.get("inputTokens")),
        output_tokens=_int_or_none(usage.get("outputTokens")),
        failed_checks=_failed_checks(failures, score_metadata.get("checks")),
        output_digest=digest if isinstance(digest, str) else None,
    )


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _failed_checks(failures: dict[str, str], checks: object) -> tuple[str, ...]:
    """case_checks is broken down into its own check names when its score metadata names them."""
    names: list[str] = []
    for scorer_name in failures:
        failed = [n for n, ok in checks.items() if ok is False] if isinstance(checks, dict) else []
        names += failed if scorer_name == CASE_CHECKS and failed else [scorer_name]
    return tuple(names)


def percentile(values: list[float], p: int) -> float:
    """Nearest-rank percentile, 0 < p <= 100, of a non-empty list."""
    if not values:
        raise ValueError("percentile of no values")
    if not 0 < p <= 100:
        raise ValueError(f"percentile must be in (0, 100], got {p}")
    ordered = sorted(values)
    rank = (p * len(ordered) + 99) // 100  # ceil(p * n / 100) in integers, so no float rounding
    return ordered[rank - 1]


def estimated_cost(run: "RunResults", input_price: float | None, output_price: float | None) -> float | None:
    """USD for one pass over the dataset (per-epoch average tokens), as the report's Estimated cost line."""
    if input_price is None or output_price is None or run.input_tokens is None or run.output_tokens is None:
        return None
    return (run.input_tokens * input_price + run.output_tokens * output_price) / 1_000_000


def _epochs(run: "RunResults") -> list[EpochMetrics]:
    return [e for case in run.cases.values() for e in case.epochs]


def _seconds(value: float) -> str:
    return f"{value:.3f}s"


def _tokens(value: float) -> str:
    return f"{int(value):,}"


def _performance_lines(run: "RunResults", input_price: float | None, output_price: float | None) -> list[str]:
    epochs = _epochs(run)
    bullets = []
    latencies = [e.latency_s for e in epochs if e.latency_s is not None]
    if latencies:
        spread = ", ".join(f"p{p} {_seconds(percentile(latencies, p))}" for p in (50, 90, 95))
        bullets.append(f"- Latency per case-epoch (n={len(latencies)}): {spread}, max {_seconds(max(latencies))}")
    for label, values in (
        ("Input tokens", [e.input_tokens for e in epochs if e.input_tokens is not None]),
        ("Output tokens", [e.output_tokens for e in epochs if e.output_tokens is not None]),
    ):
        if values:
            spread = ", ".join(f"p{p} {_tokens(percentile([float(v) for v in values], p))}" for p in (50, 95))
            bullets.append(f"- {label} per case-epoch (n={len(values)}): {spread}")
    cost = estimated_cost(run, input_price, output_price)
    if cost is not None and run.cases:
        passing = sum(c.passed for c in run.cases.values())
        per_pass = f"${cost / passing:.4f}" if passing else "n/a (no case passed)"
        bullets.append(f"- Cost per case: ${cost / len(run.cases):.4f}; per passing case: {per_pass}")
    if not bullets:
        return []
    return ["", "## Performance and cost", "", *bullets]


def check_failures(run: "RunResults") -> list[tuple[str, int, int]]:
    """(check, failing case-epochs, cases) for every check that failed, most failing epochs first, ties by name."""
    epoch_counts: Counter[str] = Counter()
    case_sets: dict[str, set[str]] = {}
    for case in run.cases.values():
        for epoch in case.epochs:
            for name in dict.fromkeys(epoch.failed_checks):
                epoch_counts[name] += 1
                case_sets.setdefault(name, set()).add(case.id)
    ranked = sorted(epoch_counts.items(), key=lambda item: (-item[1], item[0]))
    return [(name, count, len(case_sets[name])) for name, count in ranked]


def _failure_lines(run: "RunResults") -> list[str]:
    epochs = _epochs(run)
    failing = sum(bool(e.failed_checks) for e in epochs)
    if not failing:
        return []
    lines = [
        "",
        "## Failures",
        "",
        f"- Failing case-epochs: {failing}/{len(epochs)}",
        "",
        "| Check | Failing epochs | Cases |",
        "|-------|----------------|-------|",
    ]
    for name, count, cases in check_failures(run):
        cell = name.replace("|", "\\|")  # custom scorer names are free text
        lines.append(f"| {cell} | {count} | {cases} |")
    return lines


def output_consistency(run: "RunResults") -> dict[str, float]:
    """Share of a case's epochs whose output digest equals its most common one; cases with one digest are skipped."""
    shares: dict[str, float] = {}
    for case in run.cases.values():
        digests = [e.output_digest for e in case.epochs if e.output_digest is not None]
        if len(digests) > 1:
            shares[case.id] = Counter(digests).most_common(1)[0][1] / len(digests)
    return shares


def _consistency_lines(run: "RunResults") -> list[str]:
    shares = output_consistency(run)
    if not shares:
        return []
    mean = sum(shares.values()) / len(shares)
    lines = ["", "## Consistency", "", f"- Mean output consistency across epochs: {mean:.1%}"]
    varied = sorted((share, case_id) for case_id, share in shares.items() if share < 1)
    if varied:
        listed = ", ".join(f"{case_id} ({share:.0%})" for share, case_id in varied[:LEAST_CONSISTENT_SHOWN])
        more = f" and {len(varied) - LEAST_CONSISTENT_SHOWN} more" if len(varied) > LEAST_CONSISTENT_SHOWN else ""
        lines.append(f"- Least consistent: {listed}{more}")
    else:
        lines.append("- Every case gave the same output in every epoch.")
    return lines


def run_metric_lines(run: "RunResults", input_price: float | None, output_price: float | None) -> list[str]:
    """Report sections, each present only when the run has data for it."""
    return [
        *_performance_lines(run, input_price, output_price),
        *_failure_lines(run),
        *_consistency_lines(run),
    ]
