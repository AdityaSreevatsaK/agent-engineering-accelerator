from fractions import Fraction
from itertools import combinations

import pytest

from agent_accelerator.stats import Z_95, fisher_worse_p, pass_at_k, pass_hat_k, wilson_interval

COUNT_ERROR = "need 0 <= passes <= runs"
K_ERROR = "need 1 <= k <= runs"

# Test parameters say `epochs`, not `runs`: tests/conftest.py marks any test with a `runs` argument as slow.


def subset_fraction(passes, epochs, k, accept):
    """Exact share of the k-subsets of `epochs` epochs (the first `passes` of them passing) that `accept` takes."""
    subsets = list(combinations(range(epochs), k))
    return Fraction(sum(accept(sum(1 for i in s if i < passes)) for s in subsets), len(subsets))


def enumerated_fisher(baseline_passes, baseline_runs, current_passes, current_runs):
    """P(current passes <= observed) by enumerating every placement of the pooled passes over the pooled epochs.

    Epochs 0..current_runs-1 are the current run's; each placement of the passes is equally likely with fixed margins.
    """
    total_runs = baseline_runs + current_runs
    placements = list(combinations(range(total_runs), baseline_passes + current_passes))
    hits = sum(sum(1 for i in s if i < current_runs) <= current_passes for s in placements)
    return Fraction(hits, len(placements))


def all_counts(max_runs):
    return [(c, n) for n in range(max_runs + 1) for c in range(n + 1)]


# wilson_interval


@pytest.mark.parametrize(
    ("passes", "epochs", "low", "high"),
    [
        (5, 10, 0.2366, 0.7634),
        (3, 3, 0.4385, 1.0),
        (0, 3, 0.0, 0.5615),
        (1, 4, 0.0456, 0.6994),
    ],
    ids=["half", "all_pass", "none_pass", "one_of_four"],
)
def test_wilson_interval_matches_published_95_percent_bounds(passes, epochs, low, high):
    # Witnesses (s18): denominator without z squared; centre shift z^2/n; half-width p(1-p) not over n;
    # half-width z^2/(4n) not over n; Z_95 = 1.645.
    assert wilson_interval(passes, epochs) == pytest.approx((low, high), abs=1e-4)


@pytest.mark.parametrize(("passes", "epochs"), [(c, n) for c, n in all_counts(12) if 0 < c < n])
def test_wilson_interval_bounds_are_the_roots_of_the_score_equation(passes, epochs):
    # The Wilson bounds are the two rates pi with n (p - pi)^2 = z^2 pi (1 - pi); check each against that
    # equation directly, independently of the closed form.
    # Witnesses (s18): any change to the closed form (denominator, centre, half-width terms).
    p = passes / epochs
    low, high = wilson_interval(passes, epochs)

    assert 0.0 < low < p < high < 1.0
    for bound in (low, high):
        assert epochs * (p - bound) ** 2 == pytest.approx(Z_95 * Z_95 * bound * (1 - bound), abs=1e-9)


@pytest.mark.parametrize("epochs", range(1, 41))
def test_wilson_interval_is_exactly_zero_below_at_none_and_exactly_one_above_at_all(epochs):
    # Witnesses (s18): drop the `passes == 0` or `passes == runs` special case; the formula then leaves float
    # noise for some n.
    assert wilson_interval(0, epochs)[0] == 0.0
    assert wilson_interval(epochs, epochs)[1] == 1.0
    assert wilson_interval(0, epochs)[1] == pytest.approx(1 - wilson_interval(epochs, epochs)[0])


def test_wilson_interval_with_no_runs_is_the_whole_unit_interval():
    # Witness (s18): return (0.0, 0.0) for runs == 0.
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_narrows_with_a_smaller_z_and_collapses_to_the_rate_at_z_zero():
    # Witnesses (s18): centre shift z^2/n, or a half-width p(1-p) not over n, breaks the z=0 collapse.
    assert wilson_interval(3, 10, z=0.0) == pytest.approx((0.3, 0.3))
    narrow, wide = wilson_interval(3, 10, z=1.0), wilson_interval(3, 10)
    assert wide[0] < narrow[0] < 0.3 < narrow[1] < wide[1]


@pytest.mark.parametrize(
    ("passes", "epochs"),
    [(-1, 3), (4, 3), (0, -1)],
    ids=["negative_passes", "passes_over_runs", "negative_runs"],
)
def test_wilson_interval_rejects_impossible_counts(passes, epochs):
    # Witnesses (s18): wilson skips the count check; negative passes accepted.
    with pytest.raises(ValueError, match=COUNT_ERROR):
        wilson_interval(passes, epochs)


# pass_at_k and pass_hat_k


@pytest.mark.parametrize(
    ("passes", "epochs", "k", "expected"),
    [(1, 3, 1, Fraction(1, 3)), (1, 3, 3, Fraction(1)), (0, 5, 2, Fraction(0)), (2, 4, 2, Fraction(5, 6))],
    ids=["one_of_three_k1", "one_of_three_k3", "none_pass", "fail_count_equals_k"],
)
def test_pass_at_k_known_values(passes, epochs, k, expected):
    # Witnesses (s18): `<=` in the n - c < k guard (2/4 k=2 becomes 1.0); naive passes / epochs.
    assert pass_at_k(passes, epochs, k) == pytest.approx(float(expected))


@pytest.mark.parametrize(("passes", "epochs", "k"), [(c, n, k) for c, n in all_counts(7) for k in range(1, n + 1)])
def test_pass_at_k_is_the_share_of_k_subsets_with_at_least_one_pass(passes, epochs, k):
    # Witnesses (s18): `<=` guard; naive passes / epochs.
    expected = subset_fraction(passes, epochs, k, lambda hits: hits >= 1)

    assert pass_at_k(passes, epochs, k) == pytest.approx(float(expected))


@pytest.mark.parametrize(
    ("passes", "epochs", "k", "expected"),
    [(2, 3, 2, Fraction(1, 3)), (3, 3, 3, Fraction(1)), (2, 3, 3, Fraction(0)), (2, 3, 1, Fraction(2, 3))],
    ids=["two_of_three_k2", "all_pass", "k_over_passes", "k1_is_rate"],
)
def test_pass_hat_k_known_values(passes, epochs, k, expected):
    # Witness (s18): biased (passes / epochs) ** k gives 4/9 for 2/3 at k=2.
    assert pass_hat_k(passes, epochs, k) == pytest.approx(float(expected))


@pytest.mark.parametrize(("passes", "epochs", "k"), [(c, n, k) for c, n in all_counts(7) for k in range(1, n + 1)])
def test_pass_hat_k_is_the_share_of_k_subsets_that_all_pass(passes, epochs, k):
    # Witness (s18): biased (passes / epochs) ** k.
    expected = subset_fraction(passes, epochs, k, lambda hits: hits == k)

    assert pass_hat_k(passes, epochs, k) == pytest.approx(float(expected))


@pytest.mark.parametrize("estimator", [pass_at_k, pass_hat_k], ids=["pass_at_k", "pass_hat_k"])
@pytest.mark.parametrize(
    ("passes", "epochs", "k", "message"),
    [
        (-1, 3, 1, COUNT_ERROR),
        (4, 3, 1, COUNT_ERROR),
        (0, -1, 1, COUNT_ERROR),
        (1, 3, 0, K_ERROR),
        (1, 3, 4, K_ERROR),
        (0, 0, 1, K_ERROR),
    ],
    ids=["negative_passes", "passes_over_runs", "negative_runs", "k_zero", "k_over_runs", "no_runs"],
)
def test_k_estimators_reject_impossible_counts_and_k(estimator, passes, epochs, k, message):
    # Witnesses (s18): k lower bound 0; k upper bound runs + 1; passes upper bound runs + 1; negative passes.
    with pytest.raises(ValueError, match=message):
        estimator(passes, epochs, k)


# fisher_worse_p


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((3, 3, 0, 3), Fraction(1, 20)),
        ((5, 5, 0, 5), Fraction(1, 252)),
        ((3, 3, 3, 3), Fraction(1)),
        ((0, 3, 3, 3), Fraction(1)),
        # Hand-computed: pooled 4 passes in 8 epochs, current draws 4, C(8,4) = 70.
        # P(X=0) = C(4,0)C(4,4)/70 = 1/70 and P(X=1) = C(4,1)C(4,3)/70 = 16/70.
        ((3, 4, 1, 4), Fraction(1 + 16, 70)),
        # Hand-computed, unequal sizes: baseline 4/4, current 1/2. Pooled 5 of 6, current draws 2.
        # P(X=1) = C(5,1)C(1,1)/C(6,2) = 5/15; X=0 needs 2 failures from 1, impossible.
        ((4, 4, 1, 2), Fraction(5, 15)),
    ],
    ids=["three_to_zero", "five_to_zero", "no_change_all_pass", "improved", "three_of_four_to_one", "unequal_sizes"],
)
def test_fisher_worse_p_known_values(counts, expected):
    # Witnesses (s18): drop the x = lowest term (`max(1, ...)`); strict `< current_passes`; upper tail.
    assert fisher_worse_p(*counts) == pytest.approx(float(expected))


@pytest.mark.parametrize(
    "counts",
    [(bp, bn, cp, cn) for bp, bn in all_counts(4) for cp, cn in all_counts(4)],
)
def test_fisher_worse_p_matches_an_enumeration_of_every_placement_of_the_passes(counts):
    # Witnesses (s18): any of the tail and denominator mutants, including comb(total, total_passes) which only
    # differs from the right denominator when the current run's size differs from the pooled passes.
    assert fisher_worse_p(*counts) == pytest.approx(float(enumerated_fisher(*counts)))


def test_fisher_worse_p_never_rises_as_current_passes_fall():
    # Witnesses (s18): upper tail reverses the direction; a wrong denominator or fixed pass or fail term breaks it.
    checked = 0
    for bp, bn in all_counts(6):
        for cn in range(1, 7):
            ps = [fisher_worse_p(bp, bn, cp, cn) for cp in range(cn + 1)]
            assert ps == sorted(ps), (bp, bn, cn, ps)
            checked += 1

    assert checked == 28 * 6


def test_fisher_worse_p_with_no_current_runs_is_one():
    # Witnesses (s18): drop the x = lowest term; strict tail; denominator comb(total, total_passes).
    assert fisher_worse_p(3, 5, 0, 0) == 1.0
    assert fisher_worse_p(0, 0, 0, 0) == 1.0


@pytest.mark.parametrize(
    "counts",
    [(4, 3, 0, 3), (-1, 3, 0, 3), (0, -1, 0, 3), (3, 3, 4, 3), (3, 3, -1, 3), (3, 3, 0, -1)],
    ids=[
        "baseline_passes_over_runs",
        "baseline_negative_passes",
        "baseline_negative_runs",
        "current_passes_over_runs",
        "current_negative_passes",
        "current_negative_runs",
    ],
)
def test_fisher_worse_p_rejects_impossible_counts_on_either_side(counts):
    # Witnesses (s18): drop the baseline or the current count check (math.comb's own ValueError has another message).
    with pytest.raises(ValueError, match=COUNT_ERROR):
        fisher_worse_p(*counts)
