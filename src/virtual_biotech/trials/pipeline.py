"""End-to-end feature/outcome association pipeline.

Joins each trial's single-cell target features (aggregated across the trial's targets with the
paper's MIN rule) to a binary outcome, fits univariate logistic regression per feature/outcome, and
applies Benjamini-Hochberg across the tested associations. The feature lookup is a simple
gene -> value mapping (in production sourced from the Tabula Sapiens MCP server; in tests a dict).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np

from . import regression, stats
from .schema import ClinicalTrialData

FeatureLookup = Mapping[str, float]            # gene symbol -> feature value
OutcomeFn = Callable[[ClinicalTrialData], int | None]
RateFn = Callable[[ClinicalTrialData], float | None]


def trial_feature(t: ClinicalTrialData, lookup: FeatureLookup, how: str = "min") -> float | None:
    """Aggregate a single-cell feature across a trial's targets (default: min across targets)."""
    vals = [lookup[g] for g in t.targets if g in lookup]
    return stats.aggregate_target_features(vals, how=how)


def build_xy(records: list[ClinicalTrialData], lookup: FeatureLookup, outcome_fn: OutcomeFn,
             how: str = "min") -> tuple[np.ndarray, np.ndarray]:
    """Build aligned (feature, outcome) arrays, dropping trials with a missing feature or outcome."""
    fs, ys = [], []
    for t in records:
        f = trial_feature(t, lookup, how=how)
        y = outcome_fn(t)
        if f is not None and y is not None:
            fs.append(f)
            ys.append(y)
    return np.array(fs, dtype=float), np.array(ys, dtype=float)


@dataclass
class Association:
    feature: str
    outcome: str
    result: stats.LogisticResult
    perm_p: float | None = None
    q_value: float | None = None


def associate(records: list[ClinicalTrialData], *, feature_name: str, lookup: FeatureLookup,
              outcome_name: str, outcome_fn: OutcomeFn, permutations: int = 0,
              standardize: bool = True, how: str = "min") -> Association:
    """Run one feature x outcome univariate logistic association."""
    x, y = build_xy(records, lookup, outcome_fn, how=how)
    if len(np.unique(y)) < 2 or len(y) < 3:
        raise ValueError(f"insufficient variation to fit {feature_name} ~ {outcome_name} (n={len(y)})")
    res = stats.univariate_logistic(x, y, standardize=standardize)
    perm_p = (stats.permutation_test(x, y, n_iter=permutations, standardize=standardize)
              if permutations else None)
    return Association(feature_name, outcome_name, res, perm_p)


def build_rate_xy(records: list[ClinicalTrialData], lookup: FeatureLookup, rate_fn: RateFn,
                  how: str = "min") -> tuple[np.ndarray, np.ndarray]:
    """Aligned (feature, rate) arrays for beta regression, dropping missing feature/rate."""
    fs, rs = [], []
    for t in records:
        f = trial_feature(t, lookup, how=how)
        r = rate_fn(t)
        if f is not None and r is not None:
            fs.append(f)
            rs.append(r)
    return np.array(fs, dtype=float), np.array(rs, dtype=float)


def associate_rate(records: list[ClinicalTrialData], *, feature_name: str, lookup: FeatureLookup,
                   rate_name: str, rate_fn: RateFn, standardize: bool = True,
                   how: str = "min") -> regression.RegressionResult:
    """Beta regression of an AE rate (continuous [0,1]) on a single-cell feature (Python, no R)."""
    x, r = build_rate_xy(records, lookup, rate_fn, how=how)
    if len(r) < 5:
        raise ValueError(f"insufficient data for beta regression {feature_name} ~ {rate_name}")
    return regression.beta_regression(r, x, standardize=standardize)


def associate_adjusted(records: list[ClinicalTrialData], *, feature_name: str, lookup: FeatureLookup,
                       outcome_name: str, outcome_fn: OutcomeFn,
                       covariate_lookups: Mapping[str, FeatureLookup],
                       standardize: bool = True, how: str = "min") -> regression.RegressionResult:
    """Multivariable logistic adjusting for covariates (e.g. genetic evidence) — bivariate model."""
    fs, ys, covs = [], [], {k: [] for k in covariate_lookups}
    for t in records:
        f = trial_feature(t, lookup, how=how)
        y = outcome_fn(t)
        cvals = {k: trial_feature(t, cl, how=how) for k, cl in covariate_lookups.items()}
        if f is None or y is None or any(v is None for v in cvals.values()):
            continue
        fs.append(f)
        ys.append(y)
        for k in covariate_lookups:
            covs[k].append(cvals[k])
    if len(np.unique(ys)) < 2 or len(ys) < 5:
        raise ValueError(f"insufficient variation for adjusted {feature_name} ~ {outcome_name}")
    return regression.multivariable_logistic(
        np.array(ys, float), np.array(fs, float),
        {k: np.array(v, float) for k, v in covs.items()}, standardize=standardize)


def run_grid(records: list[ClinicalTrialData],
             features: Mapping[str, FeatureLookup],
             outcomes: Mapping[str, OutcomeFn],
             *, permutations: int = 0, standardize: bool = True, how: str = "min") -> list[Association]:
    """Run all feature x outcome associations and attach BH q-values across the grid."""
    assocs: list[Association] = []
    for fname, lookup in features.items():
        for oname, ofn in outcomes.items():
            try:
                assocs.append(associate(
                    records, feature_name=fname, lookup=lookup, outcome_name=oname,
                    outcome_fn=ofn, permutations=permutations, standardize=standardize, how=how))
            except ValueError:
                continue
    qs = stats.benjamini_hochberg([a.result.p_value for a in assocs])
    for a, q in zip(assocs, qs):
        a.q_value = q
    return assocs
