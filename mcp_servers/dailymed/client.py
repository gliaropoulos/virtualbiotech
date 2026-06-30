"""Async client + parsers for FDA structured drug labeling.

Label content (boxed/black-box warnings, warnings & cautions, contraindications, adverse reactions)
is the Structured Product Labeling (SPL) that DailyMed publishes, served as JSON by the openFDA
drug/label endpoint (https://open.fda.gov/apis/drug/label/). We also expose the DailyMed v2 SPL
discovery service for set-id lookup. Parsers are pure and unit-tested.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

LABEL_ENDPOINT = "https://api.fda.gov/drug/label.json"
DAILYMED_SPLS = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)"}

# SPL section fields most relevant to safety assessment.
SAFETY_SECTIONS = (
    "boxed_warning",
    "warnings_and_cautions",
    "warnings",
    "contraindications",
    "adverse_reactions",
)


def _drug_filter(drug: str) -> str:
    d = drug.strip().lower()
    return f'(openfda.generic_name:"{d}" OR openfda.brand_name:"{d}")'


async def fetch_label(drug: str) -> dict[str, Any]:
    """Fetch the most recent structured label for a drug from openFDA."""
    params = {"search": _drug_filter(drug), "limit": 1}
    key = os.getenv("OPENFDA_API_KEY")
    if key:
        params["api_key"] = key
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(LABEL_ENDPOINT, params=params)
        resp.raise_for_status()
        return resp.json()


async def find_spls(drug: str) -> dict[str, Any]:
    """Look up DailyMed SPL documents (set-ids) for a drug via the DailyMed v2 service."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(DAILYMED_SPLS, params={"drug_name": drug})
        resp.raise_for_status()
        return resp.json()


# ---- pure parsers ------------------------------------------------------------

def first_label(resp: dict[str, Any]) -> dict[str, Any] | None:
    results = resp.get("results") or []
    return results[0] if results else None


def label_openfda_names(label: dict[str, Any]) -> dict[str, Any]:
    of = label.get("openfda", {}) or {}
    return {
        "generic_name": of.get("generic_name", []),
        "brand_name": of.get("brand_name", []),
        "manufacturer_name": of.get("manufacturer_name", []),
    }


def has_boxed_warning(label: dict[str, Any]) -> bool:
    return bool(label.get("boxed_warning"))


def extract_sections(label: dict[str, Any], sections=SAFETY_SECTIONS) -> dict[str, str]:
    """Return requested SPL sections as flattened text (openFDA stores each as a list of strings)."""
    out: dict[str, str] = {}
    for sec in sections:
        val = label.get(sec)
        if val:
            out[sec] = "\n".join(val) if isinstance(val, list) else str(val)
    return out


def parse_spl_setids(resp: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"setid": d.get("setid"), "title": d.get("title"), "published": d.get("published_date")}
        for d in (resp.get("data") or [])
    ]
