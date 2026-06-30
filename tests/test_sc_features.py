"""Exact-value tests for the single-cell feature math (tau, bimodality, aggregation)."""
import math

import numpy as np
import pytest

from virtual_biotech.science import sc_features as scf


# ---- tau index (hand-computed) ----------------------------------------------

@pytest.mark.parametrize("expr,expected", [
    ([1.0, 0.0, 0.0], 1.0),                 # expressed in one cell type only -> perfectly specific
    ([1.0, 1.0, 1.0], 0.0),                 # uniform -> ubiquitous
    ([1.0, 0.5, 0.0], 0.75),                # (0 + 0.5 + 1) / 2
    ([2.0, 1.0], 0.5),                      # (0 + 0.5) / 1
    ([4.0, 2.0, 0.0], 0.75),               # (0 + 0.5 + 1) / 2 -> scale invariant
])
def test_tau_exact(expr, expected):
    assert scf.tau_index(np.array(expr)) == pytest.approx(expected)


def test_tau_undefined_cases():
    assert scf.tau_index([5.0]) is None           # < 2 cell types
    assert scf.tau_index([0.0, 0.0, 0.0]) is None  # all-zero expression
    assert scf.tau_index([]) is None


def test_tau_is_scale_invariant():
    a = scf.tau_index([3.0, 1.0, 0.0])
    b = scf.tau_index([30.0, 10.0, 0.0])
    assert a == pytest.approx(b)


# ---- bimodality coefficient (asymptotic properties) -------------------------

def test_bimodality_balanced_two_point_is_one():
    # Balanced two-point distribution: skew=0, excess kurtosis=-2, large-n correction -> 3,
    # BC = (0 + 1) / (-2 + 3) = 1.0
    x = np.array([0.0] * 5000 + [1.0] * 5000)
    # values must be > 0 to be "expressing"; shift to keep both modes positive
    x = x + 1.0
    assert scf.bimodality_coefficient(x) == pytest.approx(1.0, abs=1e-3)


def test_bimodality_normal_is_low():
    rng = np.random.default_rng(0)
    x = np.abs(rng.normal(5.0, 1.0, size=20000))  # unimodal, positive
    # Normal: skew~0, excess kurt~0 -> BC ~ 1/3
    assert scf.bimodality_coefficient(x) < scf.BIMODALITY_THRESHOLD
    assert scf.bimodality_coefficient(x) == pytest.approx(1 / 3, abs=0.03)


def test_bimodality_uniform_near_threshold():
    rng = np.random.default_rng(1)
    x = rng.uniform(0.1, 1.0, size=50000)
    # Uniform: excess kurtosis = -1.2 -> BC = 1 / 1.8 ~ 0.556 (the classic boundary)
    assert scf.bimodality_coefficient(x) == pytest.approx(0.556, abs=0.02)


def test_bimodality_undefined_cases():
    assert scf.bimodality_coefficient([1.0, 2.0, 3.0]) is None      # n < 4
    assert scf.bimodality_coefficient([2.0, 2.0, 2.0, 2.0]) is None  # zero variance


def test_bimodality_only_expressing_cells_counted():
    # zeros are dropped; the remaining 4 positive values define n
    assert scf.bimodality_coefficient([0, 0, 1.0, 2.0, 3.0, 8.0]) is not None


# ---- aggregation + classification -------------------------------------------

def test_aggregate_skips_none():
    assert scf.aggregate_across_tissues([0.2, None, 0.8]) == pytest.approx(0.5)
    assert scf.aggregate_across_tissues([None, None]) is None


def test_classify_specificity_threshold():
    assert scf.classify_specificity(0.70) == "cell-type-specific"
    assert scf.classify_specificity(0.69) == "cell-type-specific"
    assert scf.classify_specificity(0.68) == "broadly expressed"
    assert scf.classify_specificity(None) is None
