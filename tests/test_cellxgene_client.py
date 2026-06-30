"""Offline tests for CELLxGENE query-building and summarization."""
import pytest
from mcp_servers.cellxgene import client


def test_build_obs_filter():
    f = client.build_obs_filter(tissue="lung", disease="ulcerative colitis")
    assert f == ("is_primary_data == True and tissue_general == 'lung' "
                 "and disease == 'ulcerative colitis'")
    assert client.build_obs_filter() == "is_primary_data == True"
    assert "is_primary_data" not in client.build_obs_filter(is_primary=False, tissue="lung")


def test_summarize_by_celltype_sorted():
    rows = [{"cell_type": "A", "expression": 2.0}, {"cell_type": "A", "expression": 4.0},
            {"cell_type": "B", "expression": 1.0}]
    s = client.summarize_by_celltype(rows)
    assert s[0] == {"cellType": "A", "meanExpression": 3.0, "nCells": 2}
    assert s[1]["cellType"] == "B"


def test_compare_disease_vs_healthy_lfc():
    disease = [{"cell_type": "A", "expression": 4.0}]
    healthy = [{"cell_type": "A", "expression": 2.0}]
    cmp = client.compare_disease_vs_healthy(disease, healthy)
    assert cmp[0]["cellType"] == "A"
    assert cmp[0]["log2FC"] == pytest.approx(1.0, abs=1e-3)   # log2(4/2)
