"""DepMap CRISPR gene-effect parsing + essentiality summaries.

Pure compute functions operate on in-memory structures (no file/pandas dependency) so they are
unit-testable; the lazy `load_gene_effect()` reads the CSV only when present.

Chronos gene-effect convention: more negative = stronger dependency; ~0 = no effect; the DepMap
'common essential' guide value is roughly <= -0.5 median across lines.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from statistics import mean, median

DEPENDENT_THRESHOLD = -0.5     # gene-effect below this => the line depends on the gene
STRONG_THRESHOLD = -1.0        # ~ median of known common-essential genes

_COL_RE = re.compile(r"^\s*([A-Za-z0-9\-\.]+)\s*(\(\d+\))?\s*$")


def gene_from_column(col: str) -> str:
    """Extract the gene symbol from a DepMap column header like 'OSMR (9180)'."""
    m = _COL_RE.match(col)
    return (m.group(1) if m else col).upper()


def find_gene_column(columns: list[str], gene: str) -> str | None:
    """Match a gene symbol to its column header, ignoring the trailing '(entrez)'."""
    g = gene.upper()
    for c in columns:
        if gene_from_column(c) == g:
            return c
    return None


def summarize_gene_effect(values: list[float]) -> dict:
    """Summarize a gene's effect distribution across cell lines.

    Returns counts, central tendency, the fraction of lines dependent / strongly dependent, and a
    coarse 'common essential' flag (median effect <= DEPENDENT_THRESHOLD).
    """
    vals = [float(v) for v in values if v is not None and not _isnan(v)]
    n = len(vals)
    if n == 0:
        return {"nCellLines": 0, "meanEffect": None, "medianEffect": None,
                "fractionDependent": None, "fractionStronglyDependent": None, "commonEssential": None}
    med = median(vals)
    dep = sum(1 for v in vals if v < DEPENDENT_THRESHOLD)
    strong = sum(1 for v in vals if v < STRONG_THRESHOLD)
    return {
        "nCellLines": n,
        "meanEffect": round(mean(vals), 4),
        "medianEffect": round(med, 4),
        "minEffect": round(min(vals), 4),
        "fractionDependent": round(dep / n, 4),
        "fractionStronglyDependent": round(strong / n, 4),
        "commonEssential": med <= DEPENDENT_THRESHOLD,
    }


def _isnan(v) -> bool:
    return isinstance(v, float) and v != v


# ---- lazy loader -------------------------------------------------------------

def data_path() -> Path:
    base = Path(os.getenv("VB_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    return base / "depmap" / "CRISPRGeneEffect.csv"


def is_available() -> bool:
    return data_path().exists()


def load_gene_effect(gene: str) -> list[float] | None:
    """Return the gene-effect values across cell lines for one gene, or None if data is absent."""
    if not is_available():
        return None
    import pandas as pd  # local import keeps the module importable without pandas

    df = pd.read_csv(data_path(), index_col=0)
    col = find_gene_column(list(df.columns), gene)
    if col is None:
        return []
    return [v for v in df[col].tolist()]
