from fractions import Fraction
from itertools import product
from math import ceil, floor, sqrt
from random import Random
from statistics import median

import pytest

from agent_accelerator.stats import (
    Z_95,
    bootstrap_median_interval,
    cohen_kappa,
    mcnemar_exact_p,
    newcombe_difference_interval,
)

COUNT_ERROR = "need 0 <= passes <= runs"

# Test parameters say `epochs`, not `runs`: tests/conftest.py marks any test with a `runs` argument as slow.


def score_bounds(passes, epochs, z):
    """Wilson bounds as the two roots of (p - x)^2 = z^2 x (1 - x) / n, solved as a quadratic in x."""
    p, k = passes / epochs, z * z / epochs
    a, b, c = 1 + k, -(2 * p + k), p * p
    root = sqrt(b * b - 4 * a * c)
    return ((-b - root) / (2 * a), (-b + root) / (2 * a))


def hybrid_difference(passes_a, epochs_a, passes_b, epochs_b, z=Z_95):
    """Newcombe's method 10 for p_a - p_b, written out from the paper's definition."""
    p_a, p_b = passes_a / epochs_a, passes_b / epochs_b
    (l_a, u_a), (l_b, u_b) = score_bounds(passes_a, epochs_a, z), score_bounds(passes_b, epochs_b, z)
    delta = p_a - p_b
    return (delta - sqrt((p_a - l_a) ** 2 + (u_b - p_b) ** 2), delta + sqrt((u_a - p_a) ** 2 + (p_b - l_b) ** 2))


def enumerated_mcnemar(b, c):
    """Share of the 2^(b + c) equally likely sign patterns of the discordant pairs that split at least as unevenly."""
    n = b + c
    observed = abs(b - c)
    patterns = list(product((0, 1), repeat=n))
    return Fraction(sum(abs(2 * sum(s) - n) >= observed for s in patterns), len(patterns))


# newcombe_difference_interval


def test_newcombe_matches_the_published_worked_example():
    # Witness: in stats.py newcombe_difference_interval, change `(high_b - p_b) ** 2` in the lower bound to
    # `(p_b - low_b) ** 2`; the lower bound moves off 0.0524 and this test fails.
    # Newcombe (1998) Table II, example (a): 56/70 - 48/80, method 10 gives 0.0524 to 0.3339.
    low, high = newcombe_difference_interval(56, 70, 48, 80)

    assert low == pytest.approx(0.0524, abs=5e-5)
    assert high == pytest.approx(0.3339, abs=5e-5)


@pytest.mark.parametrize(
    ("passes_a", "epochs_a", "passes_b", "epochs_b"),
    [(56, 70, 48, 80), (8, 10, 10, 10), (3, 7, 5, 6), (1, 20, 19, 20), (5, 5, 0, 3)],
    ids=["published", "demo", "small-uneven", "far-apart", "extremes"],
)
def test_newcombe_matches_the_hybrid_score_definition(passes_a, epochs_a, passes_b, epochs_b):
    # Witness: in stats.py, change `high = d + sqrt((high_a - p_a) ** 2 + (p_b - low_b) ** 2)` to use
    # `(high_b - p_b) ** 2`; the upper bound departs from the definition and every case except extremes fails.
    expected = hybrid_difference(passes_a, epochs_a, passes_b, epochs_b)

    assert newcombe_difference_interval(passes_a, epochs_a, passes_b, epochs_b) == pytest.approx(expected, abs=1e-12)


def test_newcombe_is_a_minus_b_so_swapping_the_runs_negates_and_flips_it():
    # Witness: in stats.py, change `d = p_a - p_b` to `d = p_b - p_a`; both orderings then give the wrong sign.
    # By hand, 8/10 - 10/10: Wilson 8/10 is [0.49016, 0.94331] and 10/10 is [0.72247, 1], so the interval is
    # -0.2 - 0.30984 to -0.2 + sqrt(0.14331^2 + 0.27753^2) = -0.50984 to 0.11235.
    forward = newcombe_difference_interval(8, 10, 10, 10)
    backward = newcombe_difference_interval(10, 10, 8, 10)

    assert forward == pytest.approx((-0.5098, 0.1124), abs=1e-4)
    assert backward == pytest.approx((-forward[1], -forward[0]), abs=1e-12)


def test_newcombe_honours_a_custom_z():
    # Witness: in stats.py, drop `, z` from `wilson_interval(passes_a, runs_a, z)`; side a then uses 95% bounds.
    z_99 = 2.5758293035489004

    assert newcombe_difference_interval(56, 70, 48, 80, z=z_99) == pytest.approx(
        hybrid_difference(56, 70, 48, 80, z=z_99), abs=1e-12
    )


def test_newcombe_is_exact_at_zero_and_all_passes():
    # Witness: in stats.py newcombe_difference_interval, change `(high_b - p_b) ** 2` in the lower bound to
    # `(p_b - low_b) ** 2`; at 0/10 vs 0/10 the lower bound becomes 0 and this test fails.
    q = Z_95 * Z_95 / (10 + Z_95 * Z_95)  # Wilson upper bound at 0/10, and 1 minus the lower bound at 10/10

    none_vs_none = newcombe_difference_interval(0, 10, 0, 10)
    all_vs_none = newcombe_difference_interval(10, 10, 0, 10)

    assert none_vs_none == pytest.approx((-q, q), abs=1e-12)
    assert all_vs_none == pytest.approx((1 - sqrt(2) * q, 1.0), abs=1e-12)
    assert -1.0 <= all_vs_none[0] <= all_vs_none[1] <= 1.0
    assert newcombe_difference_interval(0, 10, 10, 10) == pytest.approx((-1.0, -(1 - sqrt(2) * q)), abs=1e-12)


@pytest.mark.parametrize(
    ("passes_a", "epochs_a", "passes_b", "epochs_b", "message"),
    [
        (11, 10, 5, 10, COUNT_ERROR),
        (5, 10, 11, 10, COUNT_ERROR),
        (-1, 10, 5, 10, COUNT_ERROR),
        (5, 10, -1, 10, COUNT_ERROR),
        (0, 0, 5, 10, "need runs > 0"),
        (5, 10, 0, 0, "need runs > 0"),
    ],
    ids=["a-over", "b-over", "a-negative", "b-negative", "a-no-epochs", "b-no-epochs"],
)
def test_newcombe_rejects_invalid_counts_and_empty_runs(passes_a, epochs_a, passes_b, epochs_b, message):
    # Witness: in stats.py, delete `if runs_a == 0 or runs_b == 0:` and its raise; the no-epochs cases then hit
    # ZeroDivisionError rather than ValueError and fail.
    with pytest.raises(ValueError, match=message):
        newcombe_difference_interval(passes_a, epochs_a, passes_b, epochs_b)


# mcnemar_exact_p


@pytest.mark.parametrize(
    ("b", "c", "expected"),
    [(1, 6, Fraction(1, 8)), (6, 1, Fraction(1, 8)), (2, 0, Fraction(1, 2)), (0, 10, Fraction(1, 512))],
    ids=["one-six", "six-one", "demo", "all-one-way"],
)
def test_mcnemar_matches_hand_derived_values(b, c, expected):
    # Witness: in stats.py, change `2 * tail / 2**n` to `tail / 2**n` (one-sided); every value halves and fails.
    # (1, 6): n = 7, P(X <= 1) = (1 + 7) / 128, doubled = 1/8. (0, 10): 2 / 1024.
    assert mcnemar_exact_p(b, c) == pytest.approx(float(expected), abs=1e-15)


def test_mcnemar_equals_the_enumerated_two_sided_split_probability():
    # Witness: in stats.py, change `range(min(b, c) + 1)` to `range(min(b, c))`; the observed split is dropped from
    # the tail and most pairs below disagree with the enumeration.
    pairs = [(b, c) for b in range(9) for c in range(9)]
    mismatched = [(b, c) for b, c in pairs if mcnemar_exact_p(b, c) != pytest.approx(float(enumerated_mcnemar(b, c)))]

    assert len(pairs) == 81
    assert mismatched == []


@pytest.mark.parametrize(
    ("b", "c"), [(0, 0), (3, 3), (4, 5), (1, 1)], ids=["no-discordant", "equal", "near-even", "one-each"]
)
def test_mcnemar_is_capped_at_one(b, c):
    # Witness: in stats.py, change `return min(1.0, 2 * tail / 2**n)` to `return 2 * tail / 2**n`; (3, 3) then gives
    # 2 * 42 / 64 and fails. For (0, 0), change `return 1.0` to `return 0.0`.
    assert mcnemar_exact_p(b, c) == 1.0


@pytest.mark.parametrize(("b", "c"), [(-1, 3), (3, -1)], ids=["b-negative", "c-negative"])
def test_mcnemar_rejects_negative_counts(b, c):
    # Witness: in stats.py, change `if b < 0 or c < 0:` to `if b < 0:`; the c-negative case returns a value.
    with pytest.raises(ValueError, match="need b >= 0 and c >= 0"):
        mcnemar_exact_p(b, c)


# bootstrap_median_interval

SPREAD = [4.0, -1.5, 9.0, 0.25, 3.0, 12.0, -6.0]


@pytest.mark.parametrize(
    ("values", "expected"), [([5.0, 1.0, 3.0], 3.0), ([1.0, 2.0, 3.0, 10.0], 2.5)], ids=["odd", "even"]
)
def test_bootstrap_estimate_is_the_median_of_the_values(values, expected):
    # Witness: in stats.py, change `return (median(data), ...` to `return (medians[resamples // 2], ...`; the
    # estimate becomes the middle resample median and the even case fails.
    assert bootstrap_median_interval(values)[0] == expected


def test_bootstrap_is_deterministic_and_defaults_to_seed_zero_2000_resamples_95_percent():
    # Witness: in stats.py, change `seed: int = 0` to `seed: int = 1`; the default call then differs from seed 0.
    # A second witness: change `resamples: int = 2000` to `resamples: int = 1000`.
    first = bootstrap_median_interval(SPREAD)

    assert bootstrap_median_interval(SPREAD) == first
    assert bootstrap_median_interval(SPREAD, resamples=2000, seed=0, confidence=0.95) == first


def test_bootstrap_draws_from_random_with_the_given_seed():
    # Witness: in stats.py, change `rng = Random(seed)` to `rng = Random()`; the resamples are no longer the
    # seeded draws the docstring promises, so the bounds stop matching.
    # With 40 resamples at 50%, the tail is 10 resamples each side, so the bounds are the 11th smallest and largest.
    rng = Random(7)
    medians = sorted(median(rng.choices(SPREAD, k=len(SPREAD))) for _ in range(40))

    assert bootstrap_median_interval(SPREAD, resamples=40, seed=7, confidence=0.5) == (3.0, medians[10], medians[-11])


# 40 distinct square roots: an even count makes each resample median the mean of two draws, so the 2.5% and 97.5%
# resample medians move with the seed and the resample count rather than snapping to the same data value.
CONTINUOUS = [sqrt(i) for i in range(1, 41)]


def seeded_interval(values, resamples, seed):
    """The 2.5% and 97.5% resample medians written out from the docstring: Random(seed), len(values) draws each."""
    rng = Random(seed)
    medians = sorted(median(rng.choices(values, k=len(values))) for _ in range(resamples))
    return (medians[floor(0.025 * resamples)], medians[ceil(0.975 * resamples) - 1])


def test_bootstrap_defaults_are_seed_zero_and_2000_resamples_on_seed_sensitive_data():
    # Witness: in stats.py, change `seed: int = 0` to `seed: int = 1`, or `resamples: int = 2000` to
    # `resamples: int = 1000`; the default call then matches the other reference and this test fails.
    # Control: on this data seed 1 and 1000 resamples give different bounds, so the check can tell them apart.
    expected = seeded_interval(CONTINUOUS, 2000, 0)

    assert seeded_interval(CONTINUOUS, 2000, 1) != expected
    assert seeded_interval(CONTINUOUS, 1000, 0) != expected
    assert bootstrap_median_interval(CONTINUOUS) == (median(CONTINUOUS), *expected)


def test_bootstrap_estimate_is_the_data_median_even_when_the_resamples_disagree():
    # Witness: in stats.py, change `return (median(data), ...` to `return (medians[resamples // 2], ...`; with one
    # resample the estimate becomes that resample's median and this test fails.
    # The first seed whose single resample median is not the data median; with one resample both bounds are it.
    values = [0.0, 1.0, 2.0, 100.0]
    lone = {s: median(Random(s).choices(values, k=4)) for s in range(50)}
    seed = next(s for s, m in lone.items() if m != median(values))

    assert bootstrap_median_interval(values, resamples=1, seed=seed) == (1.5, lone[seed], lone[seed])
    assert lone[seed] != 1.5


@pytest.mark.parametrize(
    ("resamples", "confidence"),
    [(2000, 0.95), (40, 0.5), (37, 0.8), (1, 0.95), (501, 0.5)],
    ids=["default", "integer-tail", "fractional-tail", "single", "half"],
)
def test_bootstrap_interval_is_symmetric_under_negating_the_values(resamples, confidence):
    # Witness: in stats.py, change `ceil(round((1 - tail) * resamples, 9)) - 1` to `ceil(round((1 - tail) * resamples,
    # 9))`; the upper index is one past the mirror of the lower one and the non-single cases fail.
    # Negating the values negates each seeded resample median, so the lower bound must mirror the upper one.
    estimate, low, high = bootstrap_median_interval(SPREAD, resamples, 3, confidence)

    assert bootstrap_median_interval([-v for v in SPREAD], resamples, 3, confidence) == (-estimate, -high, -low)
    assert low <= high


@pytest.mark.parametrize(
    ("resamples", "seed", "confidence", "tail_count"),
    [(40, 1, 0.9, 2), (150, 28, 0.64, 27)],
    ids=["lower-90-of-40", "upper-64-of-150"],
)
def test_bootstrap_tail_index_is_not_shifted_by_float_rounding_of_the_confidence(
    resamples, seed, confidence, tail_count
):
    # Witnesses: in stats.py, drop the round in the lower index (`floor(tail * resamples)`); the float tail 0.0499...
    # gives index 1 at 90% of 40 and lower-90-of-40 fails. Drop the round in the upper index (`ceil((1 - tail) *
    # resamples) - 1`); (1 - 0.18) * 150 comes out as 123.00000000000001, giving index 123, and upper-64-of-150 fails.
    # s23 bootstrap lower index off by one (`floor(round(tail * resamples, 9)) + 1`) fails both.
    # The exact tails are 0.05 * 40 = 2 and 0.18 * 150 = 27 resamples each side, so the bounds are the
    # (tail_count + 1)th smallest and largest resample medians. Any of those shifts moves a bound (directly, or
    # mirrored in the negated run) one step outward or inward, onto a median the first assertion shows is different.
    values = [float(i) for i in range(51)]
    rng = Random(seed)
    medians = sorted(median(rng.choices(values, k=len(values))) for _ in range(resamples))
    estimate, low, high = bootstrap_median_interval(values, resamples, seed, confidence)

    assert medians[tail_count] != medians[tail_count + 1] and medians[-tail_count - 1] != medians[-tail_count]
    assert (low, high) == (medians[tail_count], medians[-tail_count - 1])
    assert bootstrap_median_interval([-v for v in values], resamples, seed, confidence) == (-estimate, -high, -low)


def test_bootstrap_quantiles_follow_the_confidence_on_a_known_distribution():
    # Witness: in stats.py, change `tail = (1 - confidence) / 2` to `tail = 1 - confidence`; the 20% interval then
    # comes back as (1, 0) and this test fails.
    # Resampling [0, 1] twice gives a median of 0, 0.5 or 1 with chances 1/4, 1/2, 1/4. Of 2000 resamples the 2.5%
    # and 97.5% points sit inside the 0s and the 1s; the 40% and 60% points both sit inside the 0.5s.
    values = [0.0, 1.0]

    assert bootstrap_median_interval(values) == (0.5, 0.0, 1.0)
    assert bootstrap_median_interval(values, confidence=0.2) == (0.5, 0.5, 0.5)


@pytest.mark.parametrize("seed", range(20))
def test_bootstrap_interval_is_ordered_and_inside_the_value_range(seed):
    # Witness: in stats.py, change `medians[low_index], medians[high_index]` to `medians[high_index],
    # medians[low_index]`; the bounds come back reversed for every seed.
    _, low, high = bootstrap_median_interval(SPREAD, 300, seed)

    assert min(SPREAD) <= low < high <= max(SPREAD)


@pytest.mark.parametrize(
    ("values", "resamples", "confidence", "message"),
    [
        ([], 2000, 0.95, "need at least one value"),
        ([1.0], 0, 0.95, "need resamples >= 1"),
        ([1.0], -5, 0.95, "need resamples >= 1"),
        ([1.0], 2000, 0.0, "need 0 < confidence < 1"),
        ([1.0], 2000, 1.0, "need 0 < confidence < 1"),
        ([1.0], 2000, 1.5, "need 0 < confidence < 1"),
    ],
    ids=["empty", "zero-resamples", "negative-resamples", "confidence-zero", "confidence-one", "confidence-over"],
)
def test_bootstrap_rejects_invalid_arguments(values, resamples, confidence, message):
    # Witness: in stats.py, change `if not 0 < confidence < 1:` to `if not 0 <= confidence < 1:`; confidence 0 then
    # returns an interval and that case fails. Change `if resamples < 1:` to `if resamples < 0:` for zero-resamples.
    with pytest.raises(ValueError, match=message):
        bootstrap_median_interval(values, resamples, 0, confidence)


# cohen_kappa


def defined_kappa(rater_a, rater_b):
    """Kappa from Cohen's definition, (p_o - p_e) / (1 - p_e), in exact fractions over the union of labels."""
    n = len(rater_a)
    p_o = Fraction(sum(a == b for a, b in zip(rater_a, rater_b, strict=True)), n)
    labels = set(rater_a) | set(rater_b)
    p_e = sum(Fraction(list(rater_a).count(k), n) * Fraction(list(rater_b).count(k), n) for k in labels)
    return (p_o - p_e) / (1 - p_e)


@pytest.mark.parametrize(
    ("rater_a", "rater_b", "expected"),
    [
        (["pass", "fail", "pass", "fail"], ["pass", "fail", "pass", "fail"], 1.0),
        (["pass", "pass", "fail", "fail"], ["fail", "fail", "pass", "pass"], -1.0),
        (["pass", "pass", "fail", "fail"], ["pass", "fail", "pass", "fail"], 0.0),
        (["pass", "pass", "pass"], ["fail", "fail", "fail"], 0.0),
        (["pass"] * 4, ["pass", "pass", "pass", "fail"], 0.0),
        # 50 items: both pass 20, a pass b fail 5, a fail b pass 10, both fail 15. p_o = 35/50 = 0.7; a passes 25 and
        # b 30, so p_e = 0.5 * 0.6 + 0.5 * 0.4 = 0.5 and kappa = (0.7 - 0.5) / 0.5 = 0.4.
        (
            ["pass"] * 25 + ["fail"] * 25,
            ["pass"] * 20 + ["fail"] * 5 + ["pass"] * 10 + ["fail"] * 15,
            0.4,
        ),
    ],
    ids=["perfect", "perfect-inverse", "chance", "constant-but-different", "one-constant", "two-by-two"],
)
def test_cohen_kappa_matches_hand_derived_values(rater_a, rater_b, expected):
    # perfect-inverse: p_o = 0, p_e = 1/2, so -1. chance: p_o = p_e = 1/2. constant-but-different: p_o = p_e = 0.
    # one-constant: p_o = 3/4 and p_e = 1 * 3/4, so 0 and not undefined, since only one rater is constant.
    # Witnesses: "s32 kappa agree inverted" (a != b); "s32 kappa observed not scaled" (agree for n * agree);
    # "s32 kappa chance squares a" (count * count) fails constant-but-different and one-constant. The balanced
    # cases have equal marginal products either way, so the next test carries that mutant too.
    assert cohen_kappa(rater_a, rater_b) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize(
    ("rater_a", "rater_b"),
    [
        (["x", "x", "y", "z"], ["x", "y", "y", "z"]),
        ([1, 2, 3, 1, 2, 3, 1], [1, 3, 3, 1, 2, 2, 2]),
        (["pass", "fail", "pass"], ["pass", "pass", "maybe"]),
    ],
    ids=["three-strings", "integers", "label-only-one-rater-used"],
)
def test_cohen_kappa_takes_any_hashable_labels_and_follows_the_definition(rater_a, rater_b):
    # three-strings: p_o = 3/4, p_e = (2 + 2 + 1) / 16, so kappa = (12 - 5) / (16 - 5) = 7/11.
    # Witnesses: "s32 kappa chance squares a"; "s32 kappa observed not scaled".
    assert cohen_kappa(rater_a, rater_b) == pytest.approx(float(defined_kappa(rater_a, rater_b)), abs=1e-12)
    assert cohen_kappa(["x", "x", "y", "z"], ["x", "y", "y", "z"]) == pytest.approx(7 / 11, abs=1e-12)


@pytest.mark.parametrize(
    ("rater_a", "rater_b"),
    [(["pass"] * 3, ["pass"] * 3), (["fail"], ["fail"])],
    ids=["three-pass", "one-fail"],
)
def test_cohen_kappa_is_none_when_both_raters_give_every_item_the_same_label(rater_a, rater_b):
    # Witness: "s32 kappa undefined guard dropped" divides by zero instead.
    assert cohen_kappa(rater_a, rater_b) is None


@pytest.mark.parametrize(
    ("rater_a", "rater_b", "message"),
    [
        (["pass", "fail"], ["pass"], "need the same number of labels from each rater, got 2 and 1"),
        ([], ["pass"], "need the same number of labels from each rater, got 0 and 1"),
        ([], [], "need at least one labelled item"),
    ],
    ids=["unequal", "one-empty", "both-empty"],
)
def test_cohen_kappa_rejects_unequal_lengths_and_no_items(rater_a, rater_b, message):
    # Witnesses: "s32 kappa length check dropped" leaves zip(strict=True)'s own message; "s32 kappa empty check
    # dropped" returns None for no items.
    with pytest.raises(ValueError, match=message):
        cohen_kappa(rater_a, rater_b)