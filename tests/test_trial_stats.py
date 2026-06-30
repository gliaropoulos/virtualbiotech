"""Tests for trial-outcome statistics (logistic OR, permutation, BH FDR, feature aggregation)."""
import numpy as np
import pytest

from virtual_biotech.trials import stats


def _or3_dataset():
    # feature=0: 10 successes / 10 failures (odds 1); feature=1: 30/10 (odds 3) -> OR = 3
    feature = np.array([0] * 20 + [1] * 40, dtype=float)
    outcome = np.array([1] * 10 + [0] * 10 + [1] * 30 + [0] * 10, dtype=float)
    return feature, outcome


def test_logistic_recovers_known_odds_ratio():
    feature, outcome = _or3_dataset()
    res = stats.univariate_logistic(feature, outcome, standardize=False)
    assert res.odds_ratio == pytest.approx(3.0, rel=1e-3)
    assert res.ci_low < 3.0 < res.ci_high
    assert res.n == 60


def test_zscore_properties():
    z = stats.zscore(np.array([1.0, 2.0, 3.0, 4.0]))
    assert z.mean() == pytest.approx(0.0, abs=1e-9)
    assert z.std(ddof=0) == pytest.approx(1.0)
    # constant input -> all zeros, no divide-by-zero
    assert np.allclose(stats.zscore(np.array([5.0, 5.0, 5.0])), 0.0)


def test_standardized_or_is_per_sd():
    feature = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    outcome = np.array([0, 0, 0, 1, 0, 1, 1, 1], dtype=float)
    res = stats.univariate_logistic(feature, outcome, standardize=True)
    assert res.standardized is True
    assert res.odds_ratio > 1.0           # positive association


def test_benjamini_hochberg_hand_example():
    q = stats.benjamini_hochberg([0.005, 0.01, 0.03, 0.04])
    assert q == pytest.approx([0.02, 0.02, 0.04, 0.04])


def test_benjamini_hochberg_preserves_order():
    q = stats.benjamini_hochberg([0.04, 0.005, 0.03, 0.01])
    assert q == pytest.approx([0.04, 0.02, 0.04, 0.02])


def test_benjamini_hochberg_clipped_to_one():
    q = stats.benjamini_hochberg([0.9, 0.95])
    assert all(0.0 <= v <= 1.0 for v in q)


def test_permutation_test_strong_association_is_significant():
    feature, outcome = _or3_dataset()
    p = stats.permutation_test(feature, outcome, n_iter=300, seed=1, standardize=False)
    assert p < 0.05


def test_permutation_test_null_is_not_significant():
    rng = np.random.default_rng(7)
    feature = rng.normal(size=120)
    outcome = rng.integers(0, 2, size=120).astype(float)   # independent of feature
    p = stats.permutation_test(feature, outcome, n_iter=300, seed=3)
    assert p > 0.05


@pytest.mark.parametrize("how,expected", [("min", 0.2), ("max", 0.8), ("mean", 0.5)])
def test_aggregate_target_features(how, expected):
    assert stats.aggregate_target_features([0.2, 0.5, 0.8], how=how) == pytest.approx(expected)


def test_aggregate_target_features_skips_none():
    assert stats.aggregate_target_features([None, 0.4], how="min") == pytest.approx(0.4)
    assert stats.aggregate_target_features([None, None]) is None
