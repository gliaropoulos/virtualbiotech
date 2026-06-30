"""Async client + parsers for the OpenFDA drug adverse-event (FAERS) endpoint.

Docs: https://open.fda.gov/apis/drug/event/ . An optional API key (env OPENFDA_API_KEY) raises rate
limits. Parsers are pure and unit-tested against the documented response shape.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

ENDPOINT = "https://api.fda.gov/drug/event.json"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)"}


def _drug_filter(drug: str) -> str:
    # Match the drug as generic or brand name in the openfda block.
    d = drug.strip().lower()
    return f'(patient.drug.openfda.generic_name:"{d}" OR patient.drug.openfda.brand_name:"{d}")'


async def _get(params: dict[str, Any]) -> dict[str, Any]:
    key = os.getenv("OPENFDA_API_KEY")
    if key:
        params["api_key"] = key
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(ENDPOINT, params=params)
        resp.raise_for_status()
        return resp.json()


async def top_reactions(drug: str, limit: int = 10) -> dict[str, Any]:
    """Counts of MedDRA reaction terms for a drug (the most useful safety-signal view)."""
    return await _get({
        "search": _drug_filter(drug),
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": limit,
    })


async def report_count(drug: str, serious_only: bool = False) -> dict[str, Any]:
    search = _drug_filter(drug)
    if serious_only:
        search += ' AND serious:"1"'
    return await _get({"search": search, "limit": 1})


# ---- pure parsers ------------------------------------------------------------

def parse_counts(resp: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"term": r.get("term"), "count": r.get("count")} for r in resp.get("results", [])]


def total_reports(resp: dict[str, Any]) -> int:
    return int(((resp.get("meta", {}) or {}).get("results", {}) or {}).get("total", 0))
