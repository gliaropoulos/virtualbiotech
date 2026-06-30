"""Offline tests for cBioPortal parsing/filtering."""
from mcp_servers.cbioportal import client

STUDIES = [
    {"studyId": "luad_tcga_pan_can_atlas_2018", "name": "Lung Adenocarcinoma (TCGA, PanCancer Atlas)",
     "cancerTypeId": "luad", "allSampleCount": 566, "referenceGenome": "hg19"},
    {"studyId": "brca_tcga_pan_can_atlas_2018", "name": "Breast Invasive Carcinoma (TCGA, PanCancer Atlas)",
     "cancerTypeId": "brca", "allSampleCount": 1084, "referenceGenome": "hg19"},
]
PROFILES = [
    {"molecularProfileId": "luad_tcga_pan_can_atlas_2018_rna_seq_v2_mrna",
     "name": "mRNA expression (RNA Seq V2 RSEM)", "molecularAlterationType": "MRNA_EXPRESSION",
     "datatype": "CONTINUOUS"},
    {"molecularProfileId": "luad_tcga_pan_can_atlas_2018_mutations",
     "name": "Mutations", "molecularAlterationType": "MUTATION_EXTENDED", "datatype": "MAF"},
]


def test_filter_studies_by_cancer_type():
    luad = client.filter_studies(STUDIES, "lung adenocarcinoma")
    assert len(luad) == 1
    assert luad[0]["studyId"] == "luad_tcga_pan_can_atlas_2018"
    assert luad[0]["sampleCount"] == 566


def test_filter_studies_by_abbrev():
    assert len(client.filter_studies(STUDIES, "LUAD")) == 1   # matches cancerTypeId, case-insensitive
    assert len(client.filter_studies(STUDIES, "zzz")) == 0


def test_slim_profiles():
    p = client.slim_profiles(PROFILES)
    assert p[0]["alterationType"] == "MRNA_EXPRESSION"
    assert {x["alterationType"] for x in p} == {"MRNA_EXPRESSION", "MUTATION_EXTENDED"}
