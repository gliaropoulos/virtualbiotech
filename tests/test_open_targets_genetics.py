"""Offline tests for Open Targets granular genetics shaping (L2G, credible sets, QTL coloc).

Fixtures mirror the documented Platform GraphQL schema and use the OSMR / ulcerative colitis example
from the paper (lead variant rs395157, L2G 0.970, strong pQTL colocalization).
"""
import pytest

from mcp_servers.open_targets import genetics

GWAS_EVIDENCE = {"disease": {"id": "EFO_0000729", "name": "ulcerative colitis", "evidences": {
    "count": 2, "rows": [
        {"score": 0.61, "studyLocusId": "SL_other", "variantId": "5_1_A_T",
         "variantRsId": "rs999", "pValueMantissa": 2.0, "pValueExponent": -6, "beta": 0.03,
         "oddsRatio": 1.03, "studyId": "GCST_x"},
        {"score": 0.970, "studyLocusId": "SL_osmr", "variantId": "5_38953040_G_A",
         "variantRsId": "rs395157", "pValueMantissa": 2.68, "pValueExponent": -10, "beta": 0.0865,
         "oddsRatio": 1.09, "studyId": "GCST_liu"},
    ]}}}

CREDIBLE_SET = {"credibleSet": {
    "studyLocusId": "SL_osmr", "finemappingMethod": "SuSiE-inf", "credibleSetIndex": 1,
    "pValueMantissa": 2.68, "pValueExponent": -10, "beta": 0.0865,
    "variant": {"id": "5_38953040_G_A", "rsIds": ["rs395157"]},
    "study": {"id": "GCST_liu", "traitFromSource": "Ulcerative colitis", "projectId": "GCST",
              "nSamples": 375508},
    "locus": {"count": 3, "rows": [
        {"variant": {"id": "5_38953040_G_A", "rsIds": ["rs395157"]},
         "posteriorProbability": 0.9997, "pValueMantissa": 2.68, "pValueExponent": -10,
         "is95CredibleSet": True},
        {"variant": {"id": "5_38900000_C_T", "rsIds": ["rs123"]},
         "posteriorProbability": 0.0002, "is95CredibleSet": True},
        {"variant": {"id": "5_38800000_A_G", "rsIds": ["rs456"]},
         "posteriorProbability": 0.0001, "is95CredibleSet": False},
    ]},
    "l2GPredictions": {"count": 2, "rows": [
        {"target": {"id": "ENSG00000145623", "approvedSymbol": "OSMR"}, "score": 0.970},
        {"target": {"id": "ENSG00000000001", "approvedSymbol": "NEARBY"}, "score": 0.12},
    ]},
    "colocalisation": {"count": 1, "rows": [
        {"otherStudyLocus": {"studyLocusId": "SL_pqtl", "study": {"id": "eqtlgen",
                                                                  "traitFromSource": "OSMR pQTL"}},
         "colocalisationMethod": "COLOC", "h3": 0.01, "h4": 0.98, "clpp": 0.99,
         "numberColocalisingVariants": 5},
    ]}}}

VARIANT = {"variant": {
    "id": "5_38953040_G_A", "rsIds": ["rs395157"], "chromosome": "5", "position": 38953040,
    "referenceAllele": "G", "alternateAllele": "A",
    "mostSevereConsequence": {"id": "SO_1", "label": "intron_variant"},
    "alleleFrequencies": [{"populationName": "nfe", "alleleFrequency": 0.42}]}}


def test_gwas_evidence_sorted_by_l2g():
    s = genetics.summarize_gwas_evidence(GWAS_EVIDENCE)
    assert s["disease"] == "ulcerative colitis"
    assert s["count"] == 2
    assert s["topL2G"] == 0.970
    assert s["topLocus"] == "SL_osmr"
    assert s["rows"][0]["rsId"] == "rs395157"        # highest L2G first
    assert s["rows"][0]["pValue"] == pytest.approx(2.68e-10)


def test_credible_set_finemapping_and_coloc():
    s = genetics.summarize_credible_set(CREDIBLE_SET)
    assert s["finemappingMethod"] == "SuSiE-inf"
    assert s["leadVariant"]["rsIds"] == ["rs395157"]
    assert s["topMember"]["posteriorProbability"] == pytest.approx(0.9997)
    assert s["topMember"]["variantId"] == "5_38953040_G_A"
    assert s["topL2G"]["symbol"] == "OSMR" and s["topL2G"]["score"] == 0.970
    assert s["topColoc"]["h4"] == pytest.approx(0.98)
    assert s["topColoc"]["clpp"] == pytest.approx(0.99)
    assert s["pValue"] == pytest.approx(2.68e-10)


def test_credible_set_members_sorted_by_posterior():
    s = genetics.summarize_credible_set(CREDIBLE_SET)
    pps = [m["posteriorProbability"] for m in s["members"]]
    assert pps == sorted(pps, reverse=True)          # descending posterior probability


def test_variant_summary():
    s = genetics.summarize_variant(VARIANT)
    assert s["rsIds"] == ["rs395157"]
    assert s["chromosome"] == "5" and s["position"] == 38953040
    assert s["mostSevereConsequence"] == "intron_variant"


def test_pvalue_helper_handles_missing():
    assert genetics._pvalue(None, -10) is None
    assert genetics._pvalue(1.0, 0) == pytest.approx(1.0)


def test_empty_evidence():
    s = genetics.summarize_gwas_evidence({"disease": {"evidences": {"count": 0, "rows": []}}})
    assert s["count"] == 0 and s["topL2G"] is None and s["rows"] == []
