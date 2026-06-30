"""Offline tests for DepMap parsing + essentiality summary."""
import pytest

from mcp_servers.depmap import data


def test_gene_from_column():
    assert data.gene_from_column("OSMR (9180)") == "OSMR"
    assert data.gene_from_column("TP53") == "TP53"
    assert data.gene_from_column(" KRAS  (3845) ") == "KRAS"


def test_find_gene_column():
    cols = ["A1BG (1)", "OSMR (9180)", "TP53 (7157)"]
    assert data.find_gene_column(cols, "osmr") == "OSMR (9180)"
    assert data.find_gene_column(cols, "MYC") is None


def test_summarize_gene_effect_exact():
    s = data.summarize_gene_effect([-1.5, -0.8, 0.1, -0.2])
    assert s["nCellLines"] == 4
    assert s["meanEffect"] == pytest.approx(-0.6)
    assert s["medianEffect"] == pytest.approx(-0.5)
    assert s["minEffect"] == pytest.approx(-1.5)
    assert s["fractionDependent"] == pytest.approx(0.5)        # < -0.5: -1.5, -0.8
    assert s["fractionStronglyDependent"] == pytest.approx(0.25)  # < -1.0: -1.5
    assert s["commonEssential"] is True                          # median -0.5 <= -0.5


def test_summarize_handles_nan_and_empty():
    s = data.summarize_gene_effect([float("nan"), -2.0])
    assert s["nCellLines"] == 1
    empty = data.summarize_gene_effect([])
    assert empty["nCellLines"] == 0
    assert empty["commonEssential"] is None


def test_non_essential_gene():
    s = data.summarize_gene_effect([0.05, -0.1, 0.2, -0.05])
    assert s["commonEssential"] is False
    assert s["fractionDependent"] == 0.0
