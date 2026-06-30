"""Single-cell expression features from the Virtual Biotech methods (Zhang et al. 2026).

Two cell-type-level features derived from the Tabula Sapiens atlas:

* **Tau cell-type specificity index** (Kryuchkova-Mostacci & Robinson-Rechavi 2017): how restricted
  a gene's expression is across cell types within a tissue, in [0, 1].
* **Bimodality coefficient** (Pfister et al. 2013): whether a gene's expression across expressing
  cells suggests two subpopulations, in [0, 1] (BC > 0.555 ≈ bimodal).

Both are computed per tissue and then aggregated across tissues as the arithmetic mean over tissues
in which the gene is expressed. These are pure functions over numpy arrays so they are exactly
unit-testable, independent of any atlas I/O.
"""
from __future__ import annotations

from statistics import mean

import numpy as np
from scipy import stats

MIN_CELLS_PER_TYPE = 20          # cell types with fewer cells are excluded from tau (paper)
BIMODALITY_THRESHOLD = 0.555     # BC above this suggests bimodality


def tau_index(mean_expression_by_celltype: np.ndarray) -> float | None:
    """Tau specificity for one tissue.

        tau = sum_j (1 - xbar_j / xbar_max) / (n - 1)

    Args:
        mean_expression_by_celltype: per-cell-type mean expression (log-normalized counts),
            one value per cell type that passed the >= MIN_CELLS_PER_TYPE filter.

    Returns:
        Tau in [0, 1] (0 = ubiquitous, 1 = perfectly specific), or None if undefined
        (fewer than 2 cell types, or all-zero expression).
    """
    x = np.asarray(mean_expression_by_celltype, dtype=float)
    x = x[~np.isnan(x)]
    n = x.size
    if n < 2:
        return None
    xmax = x.max()
    if xmax <= 0:
        return None
    return float(np.sum(1.0 - x / xmax) / (n - 1))


def bimodality_coefficient(expressing_values: np.ndarray) -> float | None:
    """Sample bimodality coefficient (Pfister et al. 2013) over expressing cells in one tissue.

        BC = (g^2 + 1) / (k + 3 (n-1)^2 / ((n-2)(n-3)))

    where g is the bias-corrected sample skewness and k is the bias-corrected sample excess
    kurtosis. Only cells with expression > 0 should be passed in (the paper restricts to expressing
    cells to focus on heterogeneity among transcribing cells).

    Returns:
        BC in (0, 1], or None if n < 4 (the finite-sample correction needs n > 3).
    """
    x = np.asarray(expressing_values, dtype=float)
    x = x[x > 0]
    n = x.size
    if n < 4:
        return None
    if np.allclose(x, x[0]):  # zero variance -> undefined skew/kurtosis
        return None
    g = stats.skew(x, bias=False)                     # G1
    k = stats.kurtosis(x, fisher=True, bias=False)    # G2 (excess)
    correction = 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return float((g ** 2 + 1.0) / (k + correction))


def aggregate_across_tissues(per_tissue_values: list[float | None]) -> float | None:
    """Global gene score = arithmetic mean of per-tissue values over tissues where it is defined."""
    vals = [v for v in per_tissue_values if v is not None]
    return float(mean(vals)) if vals else None


def classify_specificity(tau: float | None, threshold: float = 0.69) -> str | None:
    """Binarize tau into the paper's categories (K-means midpoint threshold tau = 0.69)."""
    if tau is None:
        return None
    return "cell-type-specific" if tau >= threshold else "broadly expressed"
