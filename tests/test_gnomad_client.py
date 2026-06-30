"""Offline tests for gnomAD constraint parsing + LOEUF interpretation."""
import pytest
from mcp_servers.gnomad import client

DATA = {"gene": {
    "gene_id": "ENSG00000145623", "symbol": "OSMR", "chrom": "5",
    "gnomad_constraint": {"pli": 0.0, "oe_lof": 0.82, "oe_lof_lower": 0.65, "oe_lof_upper": 1.02,
                          "oe_mis": 0.95, "mis_z": 0.4, "lof_z": 0.1, "obs_lof": 45, "exp_lof": 55},
    "variants": [
        {"variant_id": "5-1-A-T", "consequence": "stop_gained"},
        {"variant_id": "5-2-G-C", "consequence": "missense_variant"},
        {"variant_id": "5-3-C-CA", "consequence": "frameshift_variant"},
    ],
}}


def test_summarize_constraint():
    s = client.summarize_constraint(DATA)
    assert s["symbol"] == "OSMR"
    assert s["pLI"] == 0.0
    assert s["LOEUF"] == 1.02
    assert s["lofInterpretation"] == "LoF-tolerant"


@pytest.mark.parametrize("loeuf,expected", [
    (0.20, "highly LoF-intolerant (likely haploinsufficient / essential)"),
    (0.50, "LoF-intolerant"),
    (0.90, "LoF-tolerant"),
    (None, "unknown"),
])
def test_loeuf_interpretation(loeuf, expected):
    assert client._loeuf_interpretation(loeuf) == expected


def test_count_lof_variants():
    # stop_gained + frameshift = 2; missense excluded
    assert client.count_lof_variants(DATA) == 2


def test_handles_missing_constraint():
    s = client.summarize_constraint({"gene": {"symbol": "X", "gnomad_constraint": None}})
    assert s["LOEUF"] is None
    assert s["lofInterpretation"] == "unknown"
