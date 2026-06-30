"""Tahoe-100M pseudobulk access + hallmark scoring bridge.

Pure functions turn per-(drug, cell-line) LFC records into the six hallmark scores using the
already-tested `virtual_biotech.science.perturbation` math. The lazy loader reads the Parquet only
when present.
"""
from __future__ import annotations

import os
from pathlib import Path
from statistics import mean

from virtual_biotech.science import perturbation as pert


def records_to_profiles(records: list[dict]) -> dict[tuple[str, str], dict]:
    """Group flat records [{drug, cell_line, gene, lfc, padj}] into per-(drug, cell_line) profiles
    of {lfc: {gene: lfc}, padj: {gene: padj}}."""
    profiles: dict[tuple[str, str], dict] = {}
    for r in records:
        key = (r["drug"], r["cell_line"])
        prof = profiles.setdefault(key, {"lfc": {}, "padj": {}})
        prof["lfc"][r["gene"]] = float(r["lfc"])
        if r.get("padj") is not None:
            prof["padj"][r["gene"]] = float(r["padj"])
    return profiles


def hallmark_scores_for_profile(profile: dict) -> dict[str, float | None]:
    return pert.all_hallmark_scores(profile["lfc"], profile.get("padj") or None)


def aggregate_scores(per_line_scores: list[dict[str, float | None]]) -> dict[str, float | None]:
    """Mean hallmark score across cell lines (ignoring None)."""
    out: dict[str, float | None] = {}
    for hm in pert.HALLMARKS:
        vals = [s[hm] for s in per_line_scores if s.get(hm) is not None]
        out[hm] = round(mean(vals), 4) if vals else None
    return out


def score_drug(records: list[dict]) -> dict:
    """Full pipeline: records -> per-line hallmark scores + cross-line means."""
    profiles = records_to_profiles(records)
    per_line = {f"{d}|{cl}": hallmark_scores_for_profile(p) for (d, cl), p in profiles.items()}
    aggregated = aggregate_scores(list(per_line.values()))
    return {"nProfiles": len(profiles), "perCellLine": per_line, "meanAcrossLines": aggregated}


# ---- lazy loader -------------------------------------------------------------

def data_path() -> Path:
    base = Path(os.getenv("VB_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    return base / "tahoe" / "tahoe100m_pseudobulk_lfc.parquet"


def is_available() -> bool:
    return data_path().exists()


def load_drug_records(drug: str, cell_line: str | None = None) -> list[dict] | None:
    """Load flat LFC records for a drug (optionally one cell line), or None if data is absent."""
    if not is_available():
        return None
    import pandas as pd

    df = pd.read_parquet(data_path())
    sel = df[df["drug"].str.lower() == drug.lower()]
    if cell_line:
        sel = sel[sel["cell_line"].str.lower() == cell_line.lower()]
    return sel.to_dict("records")
