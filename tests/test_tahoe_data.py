"""Offline tests for the Tahoe records->hallmark-scores bridge."""
import pytest
from mcp_servers.tahoe import data

RECORDS = [
    {"drug": "DrugX", "cell_line": "L1", "gene": "BAX", "lfc": 1.0, "padj": 0.01},
    {"drug": "DrugX", "cell_line": "L1", "gene": "CASP3", "lfc": 2.0, "padj": 0.01},
    {"drug": "DrugX", "cell_line": "L2", "gene": "BAX", "lfc": 2.0, "padj": 0.01},
]


def test_records_to_profiles_groups_by_drug_cellline():
    profiles = data.records_to_profiles(RECORDS)
    assert set(profiles) == {("DrugX", "L1"), ("DrugX", "L2")}
    assert profiles[("DrugX", "L1")]["lfc"] == {"BAX": 1.0, "CASP3": 2.0}


def test_score_drug_apoptosis_exact():
    result = data.score_drug(RECORDS)
    assert result["nProfiles"] == 2
    # L1: (1+2)/11 ; L2: 2/11 ; mean across lines = (3/11 + 2/11)/2 = 2.5/11
    assert result["perCellLine"]["DrugX|L1"]["apoptosis"] == pytest.approx(3 / 11)
    assert result["meanAcrossLines"]["apoptosis"] == pytest.approx(round(2.5 / 11, 4))


def test_significance_zeroing_in_bridge():
    recs = [{"drug": "D", "cell_line": "L", "gene": "BAX", "lfc": 5.0, "padj": 0.9}]
    out = data.score_drug(recs)
    assert out["perCellLine"]["D|L"]["apoptosis"] == pytest.approx(0.0)
