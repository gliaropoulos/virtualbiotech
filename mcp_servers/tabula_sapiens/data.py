"""Tabula Sapiens v2 access + cell-type-specificity / heterogeneity feature computation.

The pure functions take already-summarized per-tissue structures and produce global tau and
bimodality scores via `virtual_biotech.science.sc_features`, so they are unit-testable without the
12 GB atlas. The lazy AnnData loader does the heavy per-gene grouping only when the .h5ad is present.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from virtual_biotech.science import sc_features as scf


def tau_from_tissue_celltype_means(
    per_tissue: dict[str, dict[str, tuple[float, int]]],
    min_cells: int = scf.MIN_CELLS_PER_TYPE,
) -> dict:
    """Compute the global tau index from per-tissue cell-type means.

    per_tissue maps tissue -> {cell_type: (mean_expression, n_cells)}. Cell types with fewer than
    `min_cells` cells are dropped before tau; tissues where the gene is unexpressed are dropped
    before the cross-tissue mean.
    """
    per_tissue_tau: list[float] = []
    detail: dict[str, float | None] = {}
    for tissue, cts in per_tissue.items():
        means = [m for (m, n) in cts.values() if n >= min_cells]
        t = scf.tau_index(np.array(means)) if means else None
        detail[tissue] = t
        if t is not None:
            per_tissue_tau.append(t)
    global_tau = scf.aggregate_across_tissues(per_tissue_tau)
    return {
        "tau": global_tau,
        "specificity": scf.classify_specificity(global_tau),
        "perTissue": detail,
        "nTissues": len(per_tissue_tau),
    }


def bimodality_from_tissue_values(per_tissue_values: dict[str, list[float]]) -> dict:
    """Compute the global bimodality coefficient from per-tissue expressing-cell value arrays."""
    per_tissue_bc: list[float] = []
    detail: dict[str, float | None] = {}
    for tissue, values in per_tissue_values.items():
        bc = scf.bimodality_coefficient(np.array(values))
        detail[tissue] = bc
        if bc is not None:
            per_tissue_bc.append(bc)
    global_bc = scf.aggregate_across_tissues(per_tissue_bc)
    return {
        "bimodalityCoefficient": global_bc,
        "bimodal": (global_bc is not None and global_bc > scf.BIMODALITY_THRESHOLD),
        "perTissue": detail,
        "nTissues": len(per_tissue_bc),
    }


# ---- lazy loader -------------------------------------------------------------

def data_path() -> Path:
    base = Path(os.getenv("VB_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    return base / "tabula_sapiens" / "tabula_sapiens_v2.h5ad"


def is_available() -> bool:
    return data_path().exists()


def _summarize_gene(adata, gene: str, tissue_key: str = "tissue",
                    celltype_key: str = "cell_ontology_class"):
    """Build the per-tissue summaries needed by the pure functions for one gene."""
    if gene not in adata.var_names:
        return None
    x = adata[:, gene].X
    x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
    obs = adata.obs
    per_tissue_means: dict[str, dict[str, tuple[float, int]]] = {}
    per_tissue_values: dict[str, list[float]] = {}
    for tissue in obs[tissue_key].unique():
        tmask = (obs[tissue_key] == tissue).to_numpy()
        cts: dict[str, tuple[float, int]] = {}
        for ct in obs.loc[tmask, celltype_key].unique():
            cmask = tmask & (obs[celltype_key] == ct).to_numpy()
            vals = x[cmask]
            cts[str(ct)] = (float(vals.mean()), int(cmask.sum()))
        per_tissue_means[str(tissue)] = cts
        expressing = x[tmask]
        per_tissue_values[str(tissue)] = expressing[expressing > 0].tolist()
    return per_tissue_means, per_tissue_values


def compute_gene_features(gene: str) -> dict | None:
    """Full pipeline for one gene from the local atlas, or None if data/anndata is absent."""
    if not is_available():
        return None
    try:
        import anndata as ad
    except ImportError:
        return None
    adata = ad.read_h5ad(data_path())
    summ = _summarize_gene(adata, gene)
    if summ is None:
        return {"gene": gene, "found": False}
    per_tissue_means, per_tissue_values = summ
    tau = tau_from_tissue_celltype_means(per_tissue_means)
    bimod = bimodality_from_tissue_values(per_tissue_values)
    return {"gene": gene, "found": True, **tau, **bimod}
