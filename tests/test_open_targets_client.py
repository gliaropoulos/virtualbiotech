"""Offline tests for Open Targets response shaping (fixtures match the documented v4 schema)."""
from mcp_servers.open_targets import client

SEARCH = {"search": {"hits": [
    {"id": "ENSG00000145623", "name": "OSMR", "entity": "target",
     "object": {"__typename": "Target", "approvedSymbol": "OSMR",
                "approvedName": "oncostatin M receptor", "biotype": "protein_coding"}},
    {"id": "EFO_0000729", "name": "ulcerative colitis", "entity": "disease",
     "object": {"__typename": "Disease", "name": "ulcerative colitis"}},
]}}

TARGET = {"target": {
    "id": "ENSG00000145623", "approvedSymbol": "OSMR", "approvedName": "oncostatin M receptor",
    "biotype": "protein_coding",
    "subcellularLocations": [{"location": "Cell membrane", "source": "uniprot"}],
    "tractability": [
        {"label": "Approved Drug", "modality": "AB", "value": True},
        {"label": "High-Quality Pocket", "modality": "SM", "value": False},
    ],
    "safetyLiabilities": [{"event": "skin toxicity", "eventId": None, "datasource": "x"}],
}}

ASSOC = {"target": {"id": "ENSG00000145623", "approvedSymbol": "OSMR", "associatedDiseases": {
    "count": 2, "rows": [
        {"disease": {"id": "EFO_0000729", "name": "ulcerative colitis"}, "score": 0.71,
         "datatypeScores": [{"id": "genetic_association", "score": 0.55},
                            {"id": "known_drug", "score": 0.4}]},
        {"disease": {"id": "EFO_0003767", "name": "inflammatory bowel disease"}, "score": 0.6,
         "datatypeScores": [{"id": "known_drug", "score": 0.6}]},
    ]}}}

DRUGS = {"target": {"approvedSymbol": "OSMR", "knownDrugs": {"count": 1, "rows": [
    {"drug": {"id": "CHEMBL1", "name": "Vixarelimab", "drugType": "Antibody", "isApproved": False},
     "mechanismOfAction": "OSMR antagonist", "phase": 2, "status": "Terminated",
     "disease": {"id": "EFO_0000729", "name": "ulcerative colitis"}}]}}}


def test_first_target_hit_skips_non_targets():
    hit = client.first_target_hit(SEARCH)
    assert hit == {"ensemblId": "ENSG00000145623", "symbol": "OSMR", "name": "OSMR"}


def test_summarize_target_modalities_and_safety():
    s = client.summarize_target(TARGET)
    assert s["symbol"] == "OSMR"
    assert s["tractableModalities"] == ["AB"]            # only value=True modalities
    assert s["subcellularLocations"] == ["Cell membrane"]
    assert s["safetyLiabilities"] == ["skin toxicity"]


def test_genetic_evidence_flag_and_filter():
    ge = client.genetic_evidence(ASSOC)
    assert ge["hasGeneticEvidence"] is True
    uc = client.genetic_evidence(ASSOC, disease_id="EFO_0000729")
    assert len(uc["diseases"]) == 1
    assert uc["diseases"][0]["geneticAssociationScore"] == 0.55
    ibd = client.genetic_evidence(ASSOC, disease_id="EFO_0003767")
    assert ibd["hasGeneticEvidence"] is False           # no genetic_association datatype


def test_summarize_known_drugs():
    kd = client.summarize_known_drugs(DRUGS)
    assert kd["count"] == 1
    assert kd["drugs"][0]["drug"] == "Vixarelimab"
    assert kd["drugs"][0]["maxPhase"] == 2
