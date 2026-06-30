"""Async client + parsers for the NCBI E-utilities (PubMed).

esearch -> PMIDs, esummary -> structured metadata (JSON), efetch -> abstract text. The parsing
helpers are pure and unit-tested against the documented E-utilities response shapes. An optional
NCBI API key (env NCBI_API_KEY) raises the rate limit but is not required.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)"}

_NCT_RE = re.compile(r"\bNCT0\d{7}\b", re.IGNORECASE)


def _params(extra: dict[str, Any]) -> dict[str, Any]:
    p = {"retmode": "json", **extra}
    key = os.getenv("NCBI_API_KEY")
    if key:
        p["api_key"] = key
    return p


async def _get(path: str, params: dict[str, Any], *, json_mode: bool = True) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.get(f"{BASE}/{path}", params=params)
        resp.raise_for_status()
        return resp.json() if json_mode else resp.text


async def esearch(term: str, retmax: int = 10) -> dict[str, Any]:
    return await _get("esearch.fcgi", _params({"db": "pubmed", "term": term, "retmax": retmax}))


async def esummary(pmids: list[str]) -> dict[str, Any]:
    return await _get("esummary.fcgi", _params({"db": "pubmed", "id": ",".join(pmids)}))


async def efetch_abstract(pmid: str) -> str:
    params = {"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "text"}
    key = os.getenv("NCBI_API_KEY")
    if key:
        params["api_key"] = key
    return await _get("efetch.fcgi", params, json_mode=False)


# ---- pure parsers ------------------------------------------------------------

def parse_pmids(esearch_json: dict[str, Any]) -> list[str]:
    return list((esearch_json.get("esearchresult", {}) or {}).get("idlist", []))


def parse_summaries(esummary_json: dict[str, Any]) -> list[dict[str, Any]]:
    result = esummary_json.get("result", {}) or {}
    out = []
    for uid in result.get("uids", []):
        rec = result.get(uid, {})
        doi = next((a["value"] for a in rec.get("articleids", []) if a.get("idtype") == "doi"), None)
        out.append({
            "pmid": uid,
            "title": rec.get("title"),
            "journal": rec.get("fulljournalname") or rec.get("source"),
            "pubdate": rec.get("pubdate"),
            "authors": [a.get("name") for a in rec.get("authors", [])][:5],
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })
    return out


def find_nct_ids(text: str) -> list[str]:
    """All distinct NCT identifiers mentioned in a block of text (case-insensitive)."""
    return sorted({m.upper() for m in _NCT_RE.findall(text or "")})


def verify_nct(text: str, nct_id: str) -> bool:
    """True if the given NCT ID appears in the article text (the cascade's verification step)."""
    return nct_id.upper() in find_nct_ids(text)
