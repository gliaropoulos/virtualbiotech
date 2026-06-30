"""Tests for the pure-Python (statsmodels) replacements for the paper's R regressions."""
import numpy as np
import pytest

from virtual_biotech.trials import regression as reg


def test_squeeze_proportions_opens_interval():
    y = reg.squeeze_proportions(np.array([0.0, 0.5, 1.0]))
    assert (y > 0).all() and (y < 1).all()
    assert y[1] == pytest.approx(0.5, abs=1e-6)   # midpoint barely moves


# ---- beta regression (AE rate) ----------------------------------------------

def _ae_rate_data(slope, n=400, seed=0):
    rng = np.random.default_rng(seed)
    feat = rng.normal(size=n)
    logit = -2.0 + slope * feat
    rate = 1 / (1 + np.exp(-logit)) * rng.uniform(0.85, 1.15, n)
    return feat, np.clip(rate, 0.0, 1.0)


def test_beta_regression_recovers_positive_slope():
    feat, rate = _ae_rate_data(slope=1.0)
    res = reg.beta_regression(rate, feat)
    assert res.effect == "logit-mean shift"
    assert res.coef == pytest.approx(1.0, abs=0.25)   # near the true logit slope
    assert res.p_value < 0.01
    assert res.ci_low < res.coef < res.ci_high


def test_beta_regression_detects_negative_association():
    feat, rate = _ae_rate_data(slope=-1.2, seed=3)
    res = reg.beta_regression(rate, feat)
    assert res.coef < 0
    assert res.ci_high < 0                              # CI excludes 0 on the negative side


# ---- genetic-adjusted bivariate logistic ------------------------------------

def _binary_with_covariate(n=400, seed=1):
    rng = np.random.default_rng(seed)
    feat = rng.normal(size=n)
    gen = rng.integers(0, 2, n).astype(float)
    logit = -0.5 + 1.2 * feat + 0.4 * gen
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    return y, feat, gen


def test_multivariable_logistic_adjusts_for_genetic_evidence():
    y, feat, gen = _binary_with_covariate()
    res = reg.multivariable_logistic(y, feat, {"genetic_evidence": gen})
    assert res.effect == "odds ratio"
    assert res.effect_size > 1.0                        # feature still positively associated
    assert res.p_value < 0.01
    assert res.ci_low > 1.0                             # adjusted OR CI excludes 1


def test_feature_significant_when_no_genetic_evidence_subset():
    # restricting to genetic_evidence == 0 still shows the feature effect (paper's robustness check)
    y, feat, gen = _binary_with_covariate(seed=5)
    mask = gen == 0
    res = reg.multivariable_logistic(y[mask], feat[mask], {})
    assert res.effect_size > 1.0


# ---- mixed-effects logistic (crossed random effects) ------------------------

def _grouped_binary(slope, n=300, seed=2):
    rng = np.random.default_rng(seed)
    feat = rng.normal(size=n)
    drug = rng.integers(0, 4, n)
    ta = rng.integers(0, 3, n)
    logit = -0.3 + slope * feat
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    return y, feat, drug, ta


def test_mixed_effects_logistic_positive_association():
    y, feat, drug, ta = _grouped_binary(slope=1.2)
    res = reg.mixed_effects_logistic(
        y, feat, {"drug_type": drug, "therapeutic_area": ta})
    assert res.effect == "odds ratio"
    assert res.effect_size > 1.0
    assert res.ci_low > 1.0                             # 95% CI excludes OR=1
    assert res.p_value is None                          # VB posterior: no frequentist p


def test_mixed_effects_logistic_null_includes_one():
    y, feat, drug, ta = _grouped_binary(slope=0.0, seed=11)
    res = reg.mixed_effects_logistic(
        y, feat, {"drug_type": drug, "therapeutic_area": ta})
    assert res.ci_low < 1.0 < res.ci_high               # null: CI spans 1
