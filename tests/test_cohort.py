"""Tests for the Open Targets clinical-trial cohort loader (pure parsing)."""
from virtual_biotech.trials import cohort
from virtual_biotech.trials.cohort import TrialStub

# Mimics Open Targets knownDrugsAggregated rows: one drug-target-disease record can list many NCTs.
RECORDS = [
    {"approvedSymbol": "OSMR", "phase": 2, "status": "Terminated", "label": "ulcerative colitis",
     "prefName": "vixarelimab", "ctIds": ["NCT06137183"]},
    {"approvedSymbol": "EGFR", "phase": 3, "status": "Completed", "label": "NSCLC",
     "prefName": "gefitinib", "ctIds": ["NCT00000111", "NCT00000222"]},
    {"approvedSymbol": "ERBB2", "phase": 3, "status": "Completed", "label": "NSCLC",
     "prefName": "afatinib", "ctIds": ["NCT00000111"]},   # same NCT, second target
    {"approvedSymbol": "VEGFA", "phase": 1, "status": "Completed", "label": "x",
     "prefName": "y", "ctIds": ["NCT00000999"]},          # phase I -> filtered out
    {"approvedSymbol": "BADROW", "phase": 2, "ctIds": ["not-an-nct", ""]},  # invalid NCTs dropped
]


def test_iter_nct_rows_explodes_ctids():
    rows = cohort.iter_nct_rows(RECORDS[1])
    assert {r["nctId"] for r in rows} == {"NCT00000111", "NCT00000222"}
    assert all(r["target"] == "EGFR" for r in rows)


def test_iter_nct_rows_drops_invalid():
    assert cohort.iter_nct_rows(RECORDS[4]) == []


def test_build_cohort_merges_targets_per_nct():
    stubs = {s.nct_id: s for s in cohort.build_cohort(RECORDS)}
    # NCT00000111 appears for both EGFR and ERBB2 -> targets merged
    assert stubs["NCT00000111"].targets == ("EGFR", "ERBB2")
    assert stubs["NCT06137183"].targets == ("OSMR",)
    assert stubs["NCT06137183"].phase == 2


def test_filter_phases_keeps_ii_and_iii():
    stubs = cohort.build_cohort(RECORDS)
    kept = cohort.filter_phases(stubs)
    ncts = {s.nct_id for s in kept}
    assert "NCT00000999" not in ncts        # phase I excluded
    assert {"NCT06137183", "NCT00000111", "NCT00000222"} <= ncts


def test_target_lookup():
    stubs = cohort.filter_phases(cohort.build_cohort(RECORDS))
    lut = cohort.target_lookup(stubs)
    assert lut["NCT00000111"] == ["EGFR", "ERBB2"]
    assert lut["NCT06137183"] == ["OSMR"]


def test_single_nctid_field_supported():
    rows = cohort.iter_nct_rows({"approvedSymbol": "TP53", "phase": 2, "nctId": "NCT01234567"})
    assert rows[0]["nctId"] == "NCT01234567"
