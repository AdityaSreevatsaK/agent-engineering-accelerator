"""Reliability statistics: confidence intervals, pass@k, pass^k, Fisher, Newcombe, McNemar, bootstrap and kappa.

Standard library only. For the epoch functions, counts are per case: `passes` successful epochs out of `runs`.
"""

from collections import Counter
from collections.abc import Hashable, Sequence
from math import ceil, comb, floor, sqrt
from random import Random
from statistics import median

Z_95 = 1.959963984540054  # two-sided 95% normal quantile


def wilson_interval(passes: int, runs: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a pass rate; stays inside [0, 1] and is sensible at 0/n and n/n."""
    _check_counts(passes, runs)
    if runs == 0:
        return (0.0, 1.0)
    p = passes / runs
    denominator = 1 + z * z / runs
    centre = (p + z * z / (2 * runs)) / denominator
    half = z * sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs)) / denominator
    # At 0/n and n/n the bound is exactly 0 or 1; the formula leaves float noise there.
    low = 0.0 if passes == 0 else max(0.0, centre - half)
    high = 1.0 if passes == runs else min(1.0, centre + half)
    return (low, high)


def pass_at_k(passes: int, runs: int, k: int) -> float:
    """Unbiased estimate of P(at least one of k attempts passes), from passes out of runs (Chen et al., 2021)."""
    _check_k(passes, runs, k)
    if runs - passes < k:
        return 1.0
    return 1.0 - comb(runs - passes, k) / comb(runs, k)


def pass_hat_k(passes: int, runs: int, k: int) -> float:
    """Unbiased estimate of P(all k attempts pass), pass^k (Yao et al., 2024): the reliability a user sees."""
    _check_k(passes, runs, k)
    return comb(passes, k) / comb(runs, k)


def fisher_worse_p(baseline_passes: int, baseline_runs: int, current_passes: int, current_runs: int) -> float:
    """One-sided Fisher's exact p-value that the current pass rate is lower than the baseline's.

    The probability, under equal rates and fixed margins, of the current run passing this few times or fewer.
    """
    _check_counts(baseline_passes, baseline_runs)
    _check_counts(current_passes, current_runs)
    total_passes = baseline_passes + current_passes
    total_runs = baseline_runs + current_runs
    lowest = max(0, total_passes - baseline_runs)
    tail = sum(
        comb(total_passes, x) * comb(total_runs - total_passes, current_runs - x)
        for x in range(lowest, current_passes + 1)
    )
    return tail / comb(total_runs, current_runs)


def _check_counts(passes: int, runs: int) -> None:
    if not 0 <= passes <= runs:
        raise ValueError(f"need 0 <= passes <= runs, got passes={passes} runs={runs}")


def _check_k(passes: int, runs: int, k: int) -> None:
    _check_counts(passes, runs)
    if not 1 <= k <= runs:
        raise ValueError(f"need 1 <= k <= runs, got k={k} runs={runs}")


def newcombe_difference_interval(
    passes_a: int, runs_a: int, passes_b: int, runs_b: int, z: float = Z_95
) -> tuple[float, float]:
    """Hybrid score interval for the difference of two independent pass rates, p_a - p_b (Newcombe 1998, method 10).

    With Wilson intervals (l_a, u_a) and (l_b, u_b) and d = p_a - p_b:
    lower = d - sqrt((p_a - l_a)^2 + (u_b - p_b)^2), upper = d + sqrt((u_a - p_a)^2 + (p_b - l_b)^2).
    Reference: Newcombe, R. G. (1998), Statistics in Medicine 17(8), 873-890.
    """
    _check_counts(passes_a, runs_a)
    _check_counts(passes_b, runs_b)
    if runs_a == 0 or runs_b == 0:
        raise ValueError(f"need runs > 0 on both sides, got runs_a={runs_a} runs_b={runs_b}")
    p_a, p_b = passes_a / runs_a, passes_b / runs_b
    low_a, high_a = wilson_interval(passes_a, runs_a, z)
    low_b, high_b = wilson_interval(passes_b, runs_b, z)
    d = p_a - p_b
    low = d - sqrt((p_a - low_a) ** 2 + (high_b - p_b) ** 2)
    high = d + sqrt((high_a - p_a) ** 2 + (p_b - low_b) ** 2)
    return (max(-1.0, low), min(1.0, high))


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pair counts b and c of a paired before/after table.

    Under no change each discordant pair is a fair coin, so min(b, c) ~ Binomial(b + c, 1/2):
    p = min(1, 2 * sum_{i=0}^{min(b, c)} C(b + c, i) / 2^(b + c)); p = 1 when there are no discordant pairs.
    Reference: McNemar, Q. (1947), Psychometrika 12(2), 153-157; exact form in Agresti, Categorical Data Analysis.
    """
    if b < 0 or c < 0:
        raise ValueError(f"need b >= 0 and c >= 0, got b={b} c={c}")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2**n)


def bootstrap_median_interval(
    values: Sequence[float], resamples: int = 2000, seed: int = 0, confidence: float = 0.95
) -> tuple[float, float, float]:
    """Median of values with a percentile bootstrap interval: (median, low, high).

    Draws `resamples` samples of len(values) with replacement from random.Random(seed), so results are deterministic;
    low and high are the (1 - confidence) / 2 and (1 + confidence) / 2 empirical quantiles of the resampled medians.
    For paired comparisons pass the per-pair differences. Reference: Efron & Tibshirani (1993),
    An Introduction to the Bootstrap, ch. 13.
    """
    if not values:
        raise ValueError("need at least one value")
    if resamples < 1:
        raise ValueError(f"need resamples >= 1, got {resamples}")
    if not 0 < confidence < 1:
        raise ValueError(f"need 0 < confidence < 1, got {confidence}")
    rng = Random(seed)
    data = list(values)
    medians = sorted(median(rng.choices(data, k=len(data))) for _ in range(resamples))
    tail = (1 - confidence) / 2
    # Round before floor/ceil: float error in tail (0.0499... at 90%) would otherwise shift an index by one.
    low_index = min(resamples - 1, floor(round(tail * resamples, 9)))
    high_index = max(0, ceil(round((1 - tail) * resamples, 9)) - 1)
    return (median(data), medians[low_index], medians[high_index])


def cohen_kappa(rater_a: Sequence[Hashable], rater_b: Sequence[Hashable]) -> float | None:
    """Cohen's kappa for two raters' labels on the same items, paired by position.

    With n items, observed agreement p_o and chance agreement p_e = sum_k (a_k / n) * (b_k / n), where a_k and b_k
    are how often each rater gave label k: kappa = (p_o - p_e) / (1 - p_e), computed exactly in integers.
    Degenerate cases: p_e = 1 happens only when both raters gave every item the same single label, so agreement
    beyond chance is undefined and the result is None. Raters each constant on different labels give 0.0, as do
    raters who agree no more than chance. Reference: Cohen, J. (1960), Educational and Psychological Measurement
    20(1), 37-46.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(f"need the same number of labels from each rater, got {len(rater_a)} and {len(rater_b)}")
    n = len(rater_a)
    if n == 0:
        raise ValueError("need at least one labelled item")
    agree = sum(a == b for a, b in zip(rater_a, rater_b, strict=True))
    counts_a, counts_b = Counter(rater_a), Counter(rater_b)
    chance = sum(count * counts_b[label] for label, count in counts_a.items())  # n * n * p_e
    if chance == n * n:
        return None
    return (n * agree - chance) / (n * n - chance)
