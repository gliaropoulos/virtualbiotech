"""Load the Open Targets clinical-trial cohort (the 55,984-trial dataset the paper enriched).

The Open Targets "known drugs" dataset links each drug→target→disease record to its clinical trials
(NCT IDs), the trial phase, and status. We explode it to one stub per NCT ID, attach the trial's
target gene symbol(s), and filter to Phase II/III — the cohort the clinical-trialist agents annotate.

The parsing is pure (operates on a list of row dicts) so it is unit-testable without the dataset; the
lazy `load_cohort()` reads the local parquet only when present (see scripts/setup_data.py).
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Open Targets encodes phase as a number; the paper analyzes Phase II and III.
PHASE_II = 2
PHASE_III = 3


@dataclass(frozen=True)
class TrialStub:
    nct_id: str
    targets: tuple[str, ...]
    phase: int | None
    conditions: tuple[str, ...] = ()
    drugs: tuple[str, ...] = ()


def _normalize_nct(value: str) -> str | None:
    v = str(value).strip().upper()
    return v if v.startswith("NCT") and len(v) == 11 and v[3:].isdigit() else None


def iter_nct_rows(record: dict) -> list[dict]:
    """Explode one known-drugs record (which may list several NCT IDs in `ctIds`) into per-NCT rows.

    Accepts either `ctIds` (a list) or a single `nctId`. Carries the target symbol, phase, disease,
    and drug through to each row.
    """
    cts = record.get("ctIds")
    if cts is None and record.get("nctId"):
        cts = [record["nctId"]]
    rows = []
    for raw in cts or []:
        nct = _normalize_nct(raw)
        if not nct:
            continue
        rows.append({
            "nctId": nct,
            "target": record.get("approvedSymbol") or record.get("target"),
            "phase": record.get("phase"),
            "disease": record.get("label") or record.get("disease"),
            "drug": record.get("prefName") or record.get("drug"),
        })
    return rows


def build_cohort(records: list[dict]) -> list[TrialStub]:
    """Aggregate exploded rows into one TrialStub per NCT ID (de-duplicating targets/conditions)."""
    targets: dict[str, set[str]] = defaultdict(set)
    conditions: dict[str, set[str]] = defaultdict(set)
    drugs: dict[str, set[str]] = defaultdict(set)
    phase: dict[str, int | None] = {}
    for rec in records:
        for row in iter_nct_rows(rec):
            nct = row["nctId"]
            if row["target"]:
                targets[nct].add(str(row["target"]))
            if row["disease"]:
                conditions[nct].add(str(row["disease"]))
            if row["drug"]:
                drugs[nct].add(str(row["drug"]))
            p = row["phase"]
            if p is not None:
                # keep the highest phase seen for the trial
                phase[nct] = max(phase.get(nct, 0) or 0, int(p))
    return [
        TrialStub(nct, tuple(sorted(targets[nct])), phase.get(nct),
                  tuple(sorted(conditions[nct])), tuple(sorted(drugs[nct])))
        for nct in sorted(targets.keys() | phase.keys())
    ]


def filter_phases(stubs: list[TrialStub], phases=(PHASE_II, PHASE_III)) -> list[TrialStub]:
    return [s for s in stubs if s.phase in phases]


def target_lookup(stubs: list[TrialStub]) -> dict[str, list[str]]:
    """nct_id -> list of target symbols (what the extractor injects into each record)."""
    return {s.nct_id: list(s.targets) for s in stubs}


# ---- lazy loader -------------------------------------------------------------

def data_path() -> Path:
    base = Path(os.getenv("VB_DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
    return base / "open_targets" / "known_drugs.parquet"


def is_available() -> bool:
    return data_path().exists()


def load_cohort(phase_filter=(PHASE_II, PHASE_III)) -> list[TrialStub] | None:
    """Load and build the Phase II/III cohort from the local Open Targets parquet, or None if absent."""
    if not is_available():
        return None
    import pandas as pd

    df = pd.read_parquet(data_path())
    stubs = build_cohort(df.to_dict("records"))
    return filter_phases(stubs, phase_filter) if phase_filter else stubs
