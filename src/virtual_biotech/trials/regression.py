"""Pure-Python replacements for the paper's R regression analyses (statsmodels only — no R).

The paper used three R models alongside the univariate logistic core:

| Paper (R)                              | Here (Python / statsmodels)                        |
|----------------------------------------|----------------------------------------------------|
| AE-rate beta regression (`betareg`)    | `beta_regression` via `statsmodels …BetaModel`     |
| genetic-adjusted bivariate logistic    | `multivariable_logistic` via `statsmodels GLM`     |
| confounder GLMM (`lme4::glmer`,         | `mixed_effects_logistic` via                        |
|  `glmmTMB`, crossed random effects)    | `statsmodels …BinomialBayesMixedGLM`               |

All features are z-scored by default so coefficients are per one-standard-deviation increase, exactly
as in the paper. AE rates (continuous in [0,1]) are squeezed off the {0,1} boundary with the standard
Smithson–Verkuilen transform before beta regression.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .stats import zscore


@dataclass
class RegressionResult:
    term: str
    coef: float
    std_err: float | None
    ci_low: float
    ci_high: float
    p_value: float | None
    n: int
    effect: str                 # human label for exp(coef): "odds ratio" or "logit-mean shift"
    effect_size: float          # exp(coef) for logistic; coef for beta (already a logit shift)


# ---- AE-rate beta regression -------------------------------------------------

def squeeze_proportions(y: np.ndarray) -> np.ndarray:
    """Map a proportion in [0,1] into the open interval (0,1) (Smithson & Verkuilen 2006)."""
    y = np.asarray(y, dtype=float)
    n = y.size
    return (y * (n - 1) + 0.5) / n


def beta_regression(rate: np.ndarray, feature: np.ndarray, *, standardize: bool = True
                    ) -> RegressionResult:
    """Beta regression of an adverse-event rate in [0,1] on a (z-scored) feature.

    The coefficient is the change in the logit of the mean AE proportion per one-SD increase in the
    predictor — the exact quantity the paper reports for AE-rate associations.
    """
    from statsmodels.othermod.betareg import BetaModel
    import statsmodels.api as sm

    f = zscore(feature) if standardize else np.asarray(feature, dtype=float)
    y = squeeze_proportions(rate)
    X = sm.add_constant(f)
    res = BetaModel(y, X).fit(disp=0)
    coef = float(res.params[1])
    ci = res.conf_int()
    lo, hi = float(ci[1][0]), float(ci[1][1])
    return RegressionResult(
        term="feature", coef=coef, std_err=float(res.bse[1]),
        ci_low=lo, ci_high=hi, p_value=float(res.pvalues[1]),
        n=len(y), effect="logit-mean shift", effect_size=coef,
    )


# ---- genetic-evidence-adjusted bivariate logistic ----------------------------

def multivariable_logistic(outcome: np.ndarray, feature: np.ndarray,
                           covariates: dict[str, np.ndarray], *, standardize: bool = True
                           ) -> RegressionResult:
    """Logistic regression of a binary outcome on a feature adjusting for covariates.

    Use with covariates={'genetic_evidence': <0/1 array>} to reproduce the paper's bivariate model
    showing single-cell features are informative independent of genetic support. Returns the OR for
    the feature (per SD), adjusted for the covariates.
    """
    import statsmodels.api as sm

    f = zscore(feature) if standardize else np.asarray(feature, dtype=float)
    cols = {"feature": f}
    cols.update({k: np.asarray(v, dtype=float) for k, v in covariates.items()})
    X = sm.add_constant(pd.DataFrame(cols))
    res = sm.GLM(np.asarray(outcome, dtype=float), X, family=sm.families.Binomial()).fit()
    coef = float(res.params["feature"])
    ci = res.conf_int().loc["feature"]
    return RegressionResult(
        term="feature", coef=coef, std_err=float(res.bse["feature"]),
        ci_low=float(np.exp(ci[0])), ci_high=float(np.exp(ci[1])),
        p_value=float(res.pvalues["feature"]), n=len(outcome),
        effect="odds ratio", effect_size=float(np.exp(coef)),
    )


# ---- confounder-adjusted GLMM (crossed random effects) -----------------------

def mixed_effects_logistic(outcome: np.ndarray, feature: np.ndarray,
                           groups: dict[str, np.ndarray], *, standardize: bool = True
                           ) -> RegressionResult:
    """Mixed-effects logistic regression with crossed random intercepts (variational Bayes).

    Replaces the paper's `lme4::glmer` confounder model: pass groups like
    {'drug_type': <labels>, 'therapeutic_area': <labels>} to add a crossed random intercept for
    each. Returns the feature's fixed-effect coefficient and posterior SD (the VB posterior, so no
    frequentist p-value — significance is read from whether the CI excludes 0).
    """
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    f = zscore(feature) if standardize else np.asarray(feature, dtype=float)
    data = pd.DataFrame({"y": np.asarray(outcome, dtype=float), "feature": f})
    vc = {}
    for name, labels in groups.items():
        data[name] = pd.Categorical(labels)
        vc[name] = f"0 + C({name})"
    model = BinomialBayesMixedGLM.from_formula("y ~ feature", vc, data)
    res = model.fit_vb(verbose=False)
    names = list(res.model.exog_names)
    idx = names.index("feature")
    mean = float(res.fe_mean[idx])
    sd = float(res.fe_sd[idx])
    return RegressionResult(
        term="feature", coef=mean, std_err=sd,
        ci_low=float(np.exp(mean - 1.96 * sd)), ci_high=float(np.exp(mean + 1.96 * sd)),
        p_value=None, n=len(outcome), effect="odds ratio", effect_size=float(np.exp(mean)),
    )
