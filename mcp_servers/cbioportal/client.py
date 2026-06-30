"""Async client + parsers for the cBioPortal REST API (v2).

Docs: https://www.cbioportal.org/api/swagger-ui/ . This server scopes to discovery + metadata
(studies, molecular profiles, gene-panel/clinical attributes); heavy survival modeling for case
studies lives in analysis/b7h3_luad with lifelines. Parsers are pure and unit-tested.
"""
from __future__ import annotations

from typing import Any

import httpx

BASE = "https://www.cbioportal.org/api"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)", "Accept": "application/json"}


async def _get(path: str, params: dict[str, Any] | None = None, base: str = BASE) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(f"{base}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


async def all_studies() -> list[dict[str, Any]]:
    return await _get("/studies", {"pageSize": 10000, "direction": "ASC"})


async def study_details(study_id: str) -> dict[str, Any]:
    return await _get(f"/studies/{study_id}")


async def molecular_profiles(study_id: str) -> list[dict[str, Any]]:
    return await _get(f"/studies/{study_id}/molecular-profiles")


# ---- pure parsers ------------------------------------------------------------

def filter_studies(studies: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    """Filter studies whose name/cancer type/id contains the keyword (case-insensitive)."""
    k = keyword.lower()
    out = []
    for s in studies:
        hay = " ".join(str(s.get(f, "")) for f in ("studyId", "name", "cancerTypeId")).lower()
        if k in hay:
            out.append(slim_study(s))
    return out


def slim_study(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "studyId": s.get("studyId"),
        "name": s.get("name"),
        "cancerTypeId": s.get("cancerTypeId"),
        "sampleCount": s.get("allSampleCount"),
        "referenceGenome": s.get("referenceGenome"),
    }


def slim_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "molecularProfileId": p.get("molecularProfileId"),
            "name": p.get("name"),
            "alterationType": p.get("molecularAlterationType"),
            "datatype": p.get("datatype"),
        }
        for p in profiles
    ]
