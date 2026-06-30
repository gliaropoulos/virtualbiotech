"""Offline tests for OpenFDA FAERS parsing."""
from mcp_servers.openfda import client

COUNTS = {"meta": {"results": {"total": 3}}, "results": [
    {"term": "INJECTION SITE PAIN", "count": 5123},
    {"term": "DRUG INEFFECTIVE", "count": 4011},
    {"term": "HEADACHE", "count": 2000},
]}
REPORT = {"meta": {"results": {"skip": 0, "limit": 1, "total": 88421}}, "results": [{"safetyreportid": "x"}]}


def test_parse_counts():
    rows = client.parse_counts(COUNTS)
    assert rows[0] == {"term": "INJECTION SITE PAIN", "count": 5123}
    assert len(rows) == 3


def test_total_reports():
    assert client.total_reports(REPORT) == 88421
    assert client.total_reports({}) == 0


def test_drug_filter_matches_generic_and_brand():
    f = client._drug_filter("Adalimumab")
    assert "generic_name:\"adalimumab\"" in f
    assert "brand_name:\"adalimumab\"" in f
