"""Thin async client over the ClinicalTrials.gov v2 REST API.

Kept separate from the MCP tool layer so it can be unit-tested without FastMCP.
Docs: https://clinicaltrials.gov/data-api/api
"""
from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://clinicaltrials.gov/api/v2"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)", "Accept": "application/json"}


async def fetch_study(nct_id: str, base_url: str = BASE_URL) -> dict[str, Any]:
    """Fetch the full study record for a single NCT ID."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(f"{base_url}/studies/{nct_id}")
        resp.raise_for_status()
        return resp.json()


async def search_studies(
    query: str | None = None,
    *,
    condition: str | None = None,
    intervention: str | None = None,
    phase: str | None = None,
    status: str | None = None,
    page_size: int = 20,
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    """Search studies. Maps friendly args to the v2 query.* parameters."""
    params: dict[str, Any] = {"pageSize": min(page_size, 100), "format": "json"}
    if query:
        params["query.term"] = query
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention
    if phase:
        params["filter.advanced"] = f"AREA[Phase]{phase}"
    if status:
        params["filter.overallStatus"] = status
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(f"{base_url}/studies", params=params)
        resp.raise_for_status()
        return resp.json()


# ---- response shaping helpers ------------------------------------------------

def summarize_study(study: dict[str, Any]) -> dict[str, Any]:
    """Flatten the deeply nested v2 record into the fields agents care about."""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    arms = proto.get("armsInterventionsModule", {})
    elig = proto.get("eligibilityModule", {})
    outcomes = proto.get("outcomesModule", {})
    cond = proto.get("conditionsModule", {})
    results = study.get("resultsSection", {})

    return {
        "nctId": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "overallStatus": status.get("overallStatus"),
        "whyStopped": status.get("whyStopped"),
        "startDate": (status.get("startDateStruct") or {}).get("date"),
        "phases": design.get("phases"),
        "studyType": design.get("studyType"),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "conditions": cond.get("conditions"),
        "interventions": [
            {"type": i.get("type"), "name": i.get("name")}
            for i in arms.get("interventions", [])
        ],
        "eligibilityCriteria": elig.get("eligibilityCriteria"),
        "primaryOutcomes": outcomes.get("primaryOutcomes"),
        "secondaryOutcomes": outcomes.get("secondaryOutcomes"),
        "hasResults": bool(results),
        "adverseEventsPosted": "adverseEventsModule" in results,
    }


def extract_adverse_events(study: dict[str, Any]) -> dict[str, Any] | None:
    """Return the posted adverse-events module if present, else None."""
    ae = study.get("resultsSection", {}).get("adverseEventsModule")
    if not ae:
        return None
    return {
        "frequencyThreshold": ae.get("frequencyThreshold"),
        "seriousEventGroups": ae.get("seriousEvents"),
        "otherEventGroups": ae.get("otherEvents"),
        "eventGroups": ae.get("eventGroups"),
    }
