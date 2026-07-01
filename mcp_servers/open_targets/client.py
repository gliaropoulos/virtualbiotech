"""Async client + response-shaping helpers for the Open Targets v4 GraphQL API.

Separated from the FastMCP tool layer so the (pure) parsing helpers are unit-testable without
network or FastMCP. The single `execute()` function performs the POST; everything else transforms
already-fetched JSON.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import queries
from . import genetics

ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {
    "User-Agent": "virtual-biotech/0.1 (research)",
    "Content-Type": "application/json",
}


async def execute(
    query: str, variables: dict[str, Any], endpoint: str = ENDPOINT
) -> dict[str, Any]:
    """Run a GraphQL query and return the `data` object (raising on GraphQL errors)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.post(endpoint, json={"query": query, "variables": variables})
        body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"Open Targets GraphQL errors: {body['errors']}")
    resp.raise_for_status()
    return body.get("data", {})


# ---- high-level calls --------------------------------------------------------


async def search(query_string: str, entity: str | None = None, **kw) -> dict[str, Any]:
    entities = [entity] if entity else None
    return await execute(
        queries.SEARCH, {"q": query_string, "entities": entities}, **kw
    )


async def target_details(ensembl_id: str, **kw) -> dict[str, Any]:
    return await execute(queries.TARGET_DETAILS, {"ensemblId": ensembl_id}, **kw)


async def target_associated_diseases(
    ensembl_id: str, size: int = 25, **kw
) -> dict[str, Any]:
    return await execute(
        queries.TARGET_ASSOCIATED_DISEASES,
        {"ensemblId": ensembl_id, "size": size},
        **kw,
    )


async def target_known_drugs(ensembl_id: str, size: int = 25, **kw) -> dict[str, Any]:
    return await execute(
        queries.TARGET_KNOWN_DRUGS, {"ensemblId": ensembl_id, "size": size}, **kw
    )


async def disease_details(efo_id: str, **kw) -> dict[str, Any]:
    return await execute(queries.DISEASE_DETAILS, {"efoId": efo_id}, **kw)


# ---- granular genetics (L2G, credible sets, QTL colocalization) ---------------


async def disease_gwas_evidence(
    ensembl_id: str, efo_id: str, size: int = 25, **kw
) -> dict[str, Any]:
    return await execute(
        genetics.DISEASE_GWAS_EVIDENCE,
        {"ensemblId": ensembl_id, "efoId": efo_id, "size": size},
        **kw,
    )


async def credible_set(study_locus_id: str, **kw) -> dict[str, Any]:
    return await execute(genetics.CREDIBLE_SET, {"studyLocusId": study_locus_id}, **kw)


async def variant(variant_id: str, **kw) -> dict[str, Any]:
    return await execute(genetics.VARIANT, {"variantId": variant_id}, **kw)


# ---- pure response-shaping helpers (unit-tested) -----------------------------


def first_target_hit(search_data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first target hit (id + symbol) from a search response, or None."""
    for hit in (search_data.get("search", {}) or {}).get("hits", []):
        if hit.get("entity") == "target":
            obj = hit.get("object") or {}
            return {
                "ensemblId": hit.get("id"),
                "symbol": obj.get("approvedSymbol"),
                "name": hit.get("name"),
            }
    return None


def summarize_target(data: dict[str, Any]) -> dict[str, Any]:
    t = data.get("target") or {}
    tract = t.get("tractability") or []
    return {
        "ensemblId": t.get("id"),
        "symbol": t.get("approvedSymbol"),
        "name": t.get("approvedName"),
        "biotype": t.get("biotype"),
        "subcellularLocations": [
            s.get("location") for s in (t.get("subcellularLocations") or [])
        ],
        "tractableModalities": sorted(
            {m.get("modality") for m in tract if m.get("value")}
        ),
        "safetyLiabilities": [
            s.get("event") for s in (t.get("safetyLiabilities") or [])
        ],
    }


def genetic_evidence(
    assoc_data: dict[str, Any], disease_id: str | None = None
) -> dict[str, Any]:
    """Extract the genetic_association datatype score for a target (optionally one disease).

    Mirrors the paper's binary genetic-evidence indicator: whether any target-disease pair has a
    direct genetic association in Open Targets.
    """
    t = assoc_data.get("target") or {}
    rows = (t.get("associatedDiseases") or {}).get("rows", [])
    out = []
    for r in rows:
        d = r.get("disease") or {}
        if disease_id and d.get("id") != disease_id:
            continue
        gen = next(
            (
                s["score"]
                for s in (r.get("datatypeScores") or [])
                if s.get("id") == "genetic_association"
            ),
            0.0,
        )
        out.append(
            {
                "diseaseId": d.get("id"),
                "disease": d.get("name"),
                "overallScore": r.get("score"),
                "geneticAssociationScore": gen,
            }
        )
    has_genetic = any(
        r["geneticAssociationScore"] and r["geneticAssociationScore"] > 0 for r in out
    )
    return {
        "symbol": t.get("approvedSymbol"),
        "hasGeneticEvidence": has_genetic,
        "diseases": out,
    }


def _clinical_stage_to_phase(stage: str | None) -> int | None:
    if not stage or not stage.startswith("PHASE_"):
        return None
    phase = stage.removeprefix("PHASE_")
    if phase == "1_2":
        return 1
    try:
        return int(phase)
    except ValueError:
        return None


def _format_status(status: str | None) -> str | None:
    if not status:
        return None
    return status.replace("_", " ").title()


def summarize_known_drugs(
    data: dict[str, Any], limit: int | None = None
) -> dict[str, Any]:
    t = data.get("target") or {}
    dc = t.get("drugAndClinicalCandidates") or {}
    candidate_rows = dc.get("rows", [])
    if limit is not None:
        candidate_rows = candidate_rows[:limit]
    rows = []
    for r in candidate_rows:
        drug = r.get("drug") or {}
        moa_rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []
        diseases = r.get("diseases") or []
        reports = r.get("clinicalReports") or []
        disease_names = [
            (d.get("disease") or {}).get("name") or d.get("diseaseFromSource")
            for d in diseases
            if (d.get("disease") or {}).get("name") or d.get("diseaseFromSource")
        ]
        status = next(
            (
                rep.get("trialOverallStatus")
                for rep in reports
                if rep.get("trialOverallStatus")
            ),
            None,
        )
        rows.append(
            {
                "drug": drug.get("name"),
                "modality": drug.get("drugType"),
                "moa": moa_rows[0].get("mechanismOfAction") if moa_rows else None,
                "maxPhase": _clinical_stage_to_phase(
                    r.get("maxClinicalStage") or drug.get("maximumClinicalStage")
                ),
                "status": _format_status(status),
                "disease": disease_names[0] if disease_names else None,
            }
        )
    return {
        "symbol": t.get("approvedSymbol"),
        "count": dc.get("count", 0),
        "drugs": rows,
    }
