"""Trial-outcome association statistics (Zhang et al. 2026, Methods).

Univariate logistic regression of binary trial outcomes (phase progression, termination, endpoint
success) on z-scored single-cell features, reporting odds ratios with 95% CIs; permutation tests for
empirical significance; and Benjamini-Hochberg FDR control. Adverse-event rate (continuous in [0,1])
analyses use beta regression in the paper's R pipeline — see analysis/trial_outcomes for that bridge;
here we provide the logistic core in pure Python so it is unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LogisticResult:
    coef: float
    odds_ratio: float
    ci_low: float
    ci_high: float
    p_value: float
    n: int
    standardized: bool


def zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    sd = x.std(ddof=0)
    return (x - x.mean()) / sd if sd > 0 else x - x.mean()


def univariate_logistic(feature: np.ndarray, outcome: np.ndarray,
                        *, standardize: bool = True) -> LogisticResult:
    """Fit outcome ~ feature via a binomial GLM (logit). Returns the OR for the feature.

    When standardize=True (the paper's default for continuous features), the OR is per
    one-standard-deviation increase, enabling comparison across features with different scales.
    """
    import statsmodels.api as sm

    f = np.asarray(feature, dtype=float)
    y = np.asarray(outcome, dtype=float)
    if standardize:
        f = zscore(f)
    X = sm.add_constant(f)
    model = sm.GLM(y, X, family=sm.families.Binomial())
    res = model.fit()
    coef = float(res.params[1])
    ci = res.conf_int()[1]
    return LogisticResult(
        coef=coef,
        odds_ratio=float(np.exp(coef)),
        ci_low=float(np.exp(ci[0])),
        ci_high=float(np.exp(ci[1])),
        p_value=float(res.pvalues[1]),
        n=len(y),
        standardized=standardize,
    )


def permutation_test(feature: np.ndarray, outcome: np.ndarray, *, n_iter: int = 1000,
                     seed: int = 0, standardize: bool = True) -> float:
    """Empirical two-sided p: fraction of shuffled-outcome coefficients with |coef| >= observed."""
    rng = np.random.default_rng(seed)
    observed = abs(univariate_logistic(feature, outcome, standardize=standardize).coef)
    y = np.asarray(outcome, dtype=float).copy()
    count = 0
    for _ in range(n_iter):
        rng.shuffle(y)
        try:
            null = abs(univariate_logistic(feature, y, standardize=standardize).coef)
        except Exception:
            continue
        if null >= observed:
            count += 1
    return (count + 1) / (n_iter + 1)   # +1 smoothing avoids p=0


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """BH-adjusted q-values controlling FDR. Preserves input order."""
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / (np.arange(n) + 1)
    # enforce monotonic non-decreasing q from the largest p downward
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    out = np.empty(n)
    out[order] = q
    return out.tolist()


def aggregate_target_features(per_target_values: list[float], how: str = "min") -> float | None:
    """Collapse a feature across a trial's multiple targets.

    The paper used the MINIMUM tau / bimodality across a trial's targets, reasoning that the least
    specific target likely drives the overall safety profile.
    """
    vals = [v for v in per_target_values if v is not None]
    if not vals:
        return None
    if how == "min":
        return float(min(vals))
    if how == "max":
        return float(max(vals))
    if how == "mean":
        return float(sum(vals) / len(vals))
    raise ValueError(f"unknown aggregation '{how}'")
