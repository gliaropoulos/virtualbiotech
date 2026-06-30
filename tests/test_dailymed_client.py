"""Offline tests for DailyMed / FDA structured-label parsing."""
from mcp_servers.dailymed import client

LABEL = {"meta": {"results": {"total": 1}}, "results": [{
    "boxed_warning": ["WARNING: SERIOUS INFECTIONS\nIncreased risk of serious infections..."],
    "warnings_and_cautions": ["Serious infections", "Malignancies"],
    "contraindications": ["None."],
    "adverse_reactions": ["Most common (>10%): infections, injection site reactions."],
    "indications_and_usage": ["Rheumatoid arthritis ..."],
    "openfda": {"generic_name": ["ADALIMUMAB"], "brand_name": ["HUMIRA"],
                "manufacturer_name": ["AbbVie Inc."]},
}]}

NO_BOX = {"results": [{"warnings": ["Use with caution."],
                      "openfda": {"generic_name": ["DRUGX"]}}]}

SPLS = {"data": [
    {"setid": "abc-123", "title": "HUMIRA (adalimumab) injection", "published_date": "Jan 1, 2024"},
    {"setid": "def-456", "title": "ADALIMUMAB-ADBM", "published_date": "Feb 2, 2024"},
]}


def test_first_label_and_boxed_warning():
    label = client.first_label(LABEL)
    assert label is not None
    assert client.has_boxed_warning(label) is True
    assert client.first_label({"results": []}) is None


def test_extract_sections_flattens_lists():
    sec = client.extract_sections(client.first_label(LABEL))
    assert "boxed_warning" in sec
    assert "Serious infections\nMalignancies" == sec["warnings_and_cautions"]
    # indications is not a safety section -> excluded by default
    assert "indications_and_usage" not in sec


def test_no_boxed_warning():
    label = client.first_label(NO_BOX)
    assert client.has_boxed_warning(label) is False
    assert "boxed_warning" not in client.extract_sections(label)


def test_openfda_names():
    names = client.label_openfda_names(client.first_label(LABEL))
    assert names["generic_name"] == ["ADALIMUMAB"]
    assert names["brand_name"] == ["HUMIRA"]


def test_parse_spl_setids():
    rows = client.parse_spl_setids(SPLS)
    assert len(rows) == 2
    assert rows[0]["setid"] == "abc-123"
    assert rows[0]["title"].startswith("HUMIRA")
