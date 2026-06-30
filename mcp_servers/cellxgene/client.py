"""CELLxGENE Census access for cell-type expression and disease-vs-healthy comparison.

The Census is queried live through the `cellxgene-census` package (no local download). To keep the
logic testable, the value-filter construction and the per-cell-type summarization are pure functions
that don't import the package; only `query_celltype_expression` touches the network.
"""
from __future__ import annotations

import os
from statistics import mean

CENSUS_VERSION = os.getenv("VB_CENSUS_VERSION", "stable")


def build_obs_filter(*, tissue: str | None = None, disease: str | None = None,
                     cell_type: str | None = None, is_primary: bool = True) -> str:
    """Build a Census obs `value_filter` expression from optional constraints.

    Quotes are doubled defensively; clauses are AND-joined. `is_primary_data == True` avoids double
    counting cells aggregated from multiple datasets.
    """
    clauses: list[str] = []
    if is_primary:
        clauses.append("is_primary_data == True")
    for field, val in (("tissue_general", tissue), ("disease", disease), ("cell_type", cell_type)):
        if val:
            safe = val.replace("'", "")
            clauses.append(f"{field} == '{safe}'")
    return " and ".join(clauses)


def summarize_by_celltype(rows: list[dict], expr_key: str = "expression",
                          celltype_key: str = "cell_type") -> list[dict]:
    """Mean expression + cell count per cell type from per-cell rows. Pure; sorted high→low."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(r[celltype_key], []).append(float(r[expr_key]))
    out = [
        {"cellType": ct, "meanExpression": round(mean(v), 4), "nCells": len(v)}
        for ct, v in groups.items()
    ]
    return sorted(out, key=lambda d: d["meanExpression"], reverse=True)


def compare_disease_vs_healthy(disease_rows: list[dict], healthy_rows: list[dict],
                               celltype_key: str = "cell_type", expr_key: str = "expression") -> list[dict]:
    """Per-cell-type mean expression in disease vs healthy with a simple log2 fold-change."""
    import math

    d = {r["cellType"]: r for r in summarize_by_celltype(disease_rows, expr_key, celltype_key)}
    h = {r["cellType"]: r for r in summarize_by_celltype(healthy_rows, expr_key, celltype_key)}
    out = []
    for ct in sorted(set(d) | set(h)):
        dm = d.get(ct, {}).get("meanExpression", 0.0)
        hm = h.get(ct, {}).get("meanExpression", 0.0)
        lfc = math.log2((dm + 1e-9) / (hm + 1e-9))
        out.append({"cellType": ct, "diseaseMean": dm, "healthyMean": hm, "log2FC": round(lfc, 3)})
    return out


# ---- live query (package-gated) ----------------------------------------------

def is_available() -> bool:
    try:
        import cellxgene_census  # noqa: F401
        return True
    except ImportError:
        return False


def query_celltype_expression(gene: str, *, tissue: str | None = None,
                              disease: str | None = None, organism: str = "homo_sapiens") -> list[dict] | None:
    """Query mean expression of a gene per cell type from the Census, or None if unavailable.

    Returns a list of per-cell rows [{cell_type, expression}] suitable for summarize_by_celltype.
    """
    if not is_available():
        return None
    import cellxgene_census

    obs_filter = build_obs_filter(tissue=tissue, disease=disease)
    with cellxgene_census.open_soma(census_version=CENSUS_VERSION) as census:
        adata = cellxgene_census.get_anndata(
            census, organism=organism,
            var_value_filter=f"feature_name == '{gene}'",
            obs_value_filter=obs_filter,
            column_names={"obs": ["cell_type", "tissue_general", "disease"]},
        )
    if adata.n_vars == 0:
        return []
    import numpy as np
    x = adata.X
    x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
    return [{"cell_type": ct, "expression": float(v)}
            for ct, v in zip(adata.obs["cell_type"].tolist(), x)]
