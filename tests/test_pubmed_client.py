"""Offline tests for PubMed E-utilities parsing + NCT verification."""
from mcp_servers.pubmed import client

ESEARCH = {"header": {"type": "esearch"}, "esearchresult": {
    "count": "2", "retmax": "2", "idlist": ["39438660", "38782901"]}}

ESUMMARY = {"result": {
    "uids": ["39438660"],
    "39438660": {
        "uid": "39438660",
        "title": "A longitudinal single-cell atlas of anti-TNF treatment in IBD",
        "fulljournalname": "Nature Immunology",
        "source": "Nat Immunol",
        "pubdate": "2024 Nov",
        "authors": [{"name": "Thomas T"}, {"name": "Friedrich M"}],
        "articleids": [{"idtype": "pubmed", "value": "39438660"},
                       {"idtype": "doi", "value": "10.1038/s41590-024-01994-8"}],
    }}}


def test_parse_pmids():
    assert client.parse_pmids(ESEARCH) == ["39438660", "38782901"]
    assert client.parse_pmids({"esearchresult": {}}) == []


def test_parse_summaries():
    s = client.parse_summaries(ESUMMARY)
    assert len(s) == 1
    rec = s[0]
    assert rec["pmid"] == "39438660"
    assert rec["journal"] == "Nature Immunology"
    assert rec["doi"] == "10.1038/s41590-024-01994-8"
    assert rec["url"].endswith("/39438660/")
    assert rec["authors"] == ["Thomas T", "Friedrich M"]


def test_find_and_verify_nct():
    text = "This trial (NCT06137183) and a related study nct04205643 were analyzed."
    found = client.find_nct_ids(text)
    assert found == ["NCT04205643", "NCT06137183"]   # de-duped, upper, sorted
    assert client.verify_nct(text, "NCT06137183") is True
    assert client.verify_nct(text, "nct06137183") is True   # case-insensitive
    assert client.verify_nct(text, "NCT99999999") is False


def test_find_nct_handles_empty():
    assert client.find_nct_ids("") == []
    assert client.find_nct_ids(None) == []
