"""Granular Open Targets *Genetics* queries + shaping (L2G, credible sets, QTL colocalization).

Open Targets merged Open Targets Genetics into the Platform, exposing the evidence through the
`gwas_credible_sets` datasource and the `credibleSet` entity. These tools give the statistical
genetics agent the fine-grained signals the paper relies on:

* **L2G** (locus-to-gene): the ML score assigning a credible set's causal gene.
* **Credible sets** (fine-mapping): the variants in the 95% credible set with posterior
  probabilities (e.g. rs395157 at PP 0.9997 in the OSMR/UC example).
* **QTL colocalization**: H4 / CLPP between a GWAS credible set and molecular-QTL signals.

Query strings are centralized here so field paths can be validated against the live schema and
adjusted without touching tool logic. The shaping helpers are pure and unit-tested.
Schema ref: https://platform-docs.opentargets.org (GraphQL, `credibleSet` / `disease.evidences`).
"""
from __future__ import annotations

from typing import Any

# Target–disease GWAS credible-set evidence: each row is a credible set linking the target to the
# disease, carrying its L2G score, lead variant, study, and association stats.
DISEASE_GWAS_EVIDENCE = """
query GwasEvidence($efoId: String!, $ensemblId: String!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    evidences(ensemblIds: [$ensemblId], datasourceIds: ["gwas_credible_sets"], size: $size) {
      count
      rows {
        score
        variant { id rsIds }
        variantRsId
        pValueMantissa
        pValueExponent
        beta
        oddsRatio
        studyId
        literature
      }
    }
  }
}
"""

# One credible set in full: fine-mapping method, lead variant, 95% credible-set members with
# posterior probabilities, L2G predictions, and colocalization rows (H4 / CLPP).
CREDIBLE_SET = """
query CredibleSet($studyLocusId: String!) {
  credibleSet(studyLocusId: $studyLocusId) {
    studyLocusId
    finemappingMethod
    credibleSetIndex
    pValueMantissa
    pValueExponent
    beta
    variant { id rsIds }
    study { id traitFromSource projectId nSamples }
    locus {
      count
      rows {
        variant { id rsIds }
        posteriorProbability
        pValueMantissa
        pValueExponent
        is95CredibleSet
      }
    }
    l2GPredictions {
      count
      rows { target { id approvedSymbol } score }
    }
    colocalisation {
      count
      rows {
        otherStudyLocus { studyLocusId study { id traitFromSource } }
        colocalisationMethod
        h3
        h4
        clpp
        numberColocalisingVariants
      }
    }
  }
}
"""

VARIANT = """
query Variant($variantId: String!) {
  variant(variantId: $variantId) {
    id
    rsIds
    chromosome
    position
    referenceAllele
    alternateAllele
    mostSevereConsequence { id label }
    alleleFrequencies { populationName alleleFrequency }
  }
}
"""


# ---- pure shaping helpers ----------------------------------------------------

def summarize_gwas_evidence(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten disease→GWAS-credible-set evidence rows for one target into L2G-centric records.

    `Evidence` (gwas_credible_sets datasource) exposes the credible-set-derived association score
    (used as the L2G-linked evidence score), the lead `variant` object, the study, and stats. The
    lead variant id feeds get_variant / credible-set drill-down.
    """
    disease = data.get("disease") or {}
    ev = disease.get("evidences") or {}
    rows = []
    for r in ev.get("rows", []):
        variant = r.get("variant") or {}
        rs = r.get("variantRsId") or ((variant.get("rsIds") or [None])[0])
        rows.append({
            "l2gScore": r.get("score"),
            "variantId": variant.get("id"),
            "rsId": rs,
            "pValue": _pvalue(r.get("pValueMantissa"), r.get("pValueExponent")),
            "beta": r.get("beta"),
            "oddsRatio": r.get("oddsRatio"),
            "studyId": r.get("studyId"),
        })
    rows.sort(key=lambda x: (x["l2gScore"] is None, -(x["l2gScore"] or 0)))
    best = rows[0] if rows else None
    return {
        "disease": disease.get("name"),
        "diseaseId": disease.get("id"),
        "count": ev.get("count", len(rows)),
        "topL2G": best["l2gScore"] if best else None,
        "topVariant": best["variantId"] if best else None,
        "rows": rows,
    }


def summarize_credible_set(data: dict[str, Any]) -> dict[str, Any]:
    """Fine-mapping detail: lead variant, credible-set members w/ posterior probs, L2G, coloc."""
    cs = data.get("credibleSet") or {}
    lead = cs.get("variant") or {}
    locus = cs.get("locus") or {}
    members = [
        {
            "variantId": (m.get("variant") or {}).get("id"),
            "rsIds": (m.get("variant") or {}).get("rsIds"),
            "posteriorProbability": m.get("posteriorProbability"),
            "in95": m.get("is95CredibleSet"),
        }
        for m in locus.get("rows", [])
    ]
    members.sort(key=lambda m: (m["posteriorProbability"] is None,
                                -(m["posteriorProbability"] or 0)))
    l2g = [
        {"symbol": (r.get("target") or {}).get("approvedSymbol"),
         "ensemblId": (r.get("target") or {}).get("id"), "score": r.get("score")}
        for r in (cs.get("l2GPredictions") or {}).get("rows", [])
    ]
    l2g.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    coloc = [
        {
            "otherStudyLocusId": (c.get("otherStudyLocus") or {}).get("studyLocusId"),
            "otherTrait": ((c.get("otherStudyLocus") or {}).get("study") or {}).get("traitFromSource"),
            "method": c.get("colocalisationMethod"),
            "h4": c.get("h4"),
            "clpp": c.get("clpp"),
            "nColocalising": c.get("numberColocalisingVariants"),
        }
        for c in (cs.get("colocalisation") or {}).get("rows", [])
    ]
    coloc.sort(key=lambda x: (x["h4"] is None, -(x["h4"] or 0)))
    return {
        "studyLocusId": cs.get("studyLocusId"),
        "finemappingMethod": cs.get("finemappingMethod"),
        "study": cs.get("study"),
        "leadVariant": {"id": lead.get("id"), "rsIds": lead.get("rsIds")},
        "pValue": _pvalue(cs.get("pValueMantissa"), cs.get("pValueExponent")),
        "beta": cs.get("beta"),
        "nCredibleSetVariants": locus.get("count", len(members)),
        "topMember": members[0] if members else None,
        "members": members,
        "l2g": l2g,
        "topL2G": l2g[0] if l2g else None,
        "colocalisation": coloc,
        "topColoc": coloc[0] if coloc else None,
    }


def summarize_variant(data: dict[str, Any]) -> dict[str, Any]:
    v = data.get("variant") or {}
    return {
        "id": v.get("id"),
        "rsIds": v.get("rsIds"),
        "chromosome": v.get("chromosome"),
        "position": v.get("position"),
        "ref": v.get("referenceAllele"),
        "alt": v.get("alternateAllele"),
        "mostSevereConsequence": (v.get("mostSevereConsequence") or {}).get("label"),
        "alleleFrequencies": v.get("alleleFrequencies"),
    }


def _pvalue(mantissa, exponent) -> float | None:
    if mantissa is None or exponent is None:
        return None
    try:
        return float(mantissa) * (10 ** float(exponent))
    except (TypeError, ValueError):
        return None
