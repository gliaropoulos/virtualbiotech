"""Offline tests for the ClinicalTrials.gov response-shaping logic.

Uses a trimmed copy of the real NCT06137183 (vixarelimab / OSMRbeta UC) v2 record so the
parsing is validated without network access.
"""
from mcp_servers.clinicaltrials import client

# Trimmed but structurally faithful slice of the live v2 response.
STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT06137183",
            "briefTitle": "A Study to Evaluate ... Vixarelimab ... Ulcerative Colitis (UC)",
        },
        "statusModule": {
            "overallStatus": "TERMINATED",
            "whyStopped": "Based on a futility analysis ... unlikely to meet its primary endpoint.",
            "startDateStruct": {"date": "2024-05-01"},
        },
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE2"],
            "enrollmentInfo": {"count": 79},
        },
        "conditionsModule": {"conditions": ["Ulcerative Colitis"]},
        "armsInterventionsModule": {
            "interventions": [
                {"type": "DRUG", "name": "Vixarelimab"},
                {"type": "DRUG", "name": "Placebo"},
            ]
        },
        "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria: ... JAK inhibitor ..."},
        "outcomesModule": {
            "primaryOutcomes": [{"measure": "Clinical Remission at Week 12"}],
            "secondaryOutcomes": [{"measure": "Clinical Response at Week 12"}],
        },
    },
    # no resultsSection in this slice -> hasResults False, no AE
}


def test_summarize_study_core_fields():
    s = client.summarize_study(STUDY)
    assert s["nctId"] == "NCT06137183"
    assert s["overallStatus"] == "TERMINATED"
    assert s["phases"] == ["PHASE2"]
    assert s["enrollment"] == 79
    assert s["conditions"] == ["Ulcerative Colitis"]
    assert {i["name"] for i in s["interventions"]} == {"Vixarelimab", "Placebo"}
    assert "futility" in s["whyStopped"]
    assert s["hasResults"] is False


def test_extract_adverse_events_absent():
    assert client.extract_adverse_events(STUDY) is None


def test_extract_adverse_events_present():
    study = {"resultsSection": {"adverseEventsModule": {
        "frequencyThreshold": "5",
        "seriousEvents": [{"term": "X"}],
        "otherEvents": [],
        "eventGroups": [],
    }}}
    ae = client.extract_adverse_events(study)
    assert ae is not None
    assert ae["frequencyThreshold"] == "5"
    assert len(ae["seriousEventGroups"]) == 1
