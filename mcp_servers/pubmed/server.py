"""PubMed MCP server (NCBI E-utilities).

Level-2 evidence source in the clinical trialist cascade and the literature tool for every
scientist agent. Run:  python -m mcp_servers.pubmed.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="pubmed",
    instructions=(
        "Search and retrieve biomedical literature. For trial-results curation, search by NCT ID "
        "first, then fetch abstracts and call verify_nct_in_article to confirm the NCT ID actually "
        "appears in the article before trusting it."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def search_pubmed(
    query: Annotated[str, Field(description="PubMed query, e.g. an NCT ID, gene, drug, or boolean term")],
    retmax: Annotated[int, Field(description="Max results", ge=1, le=50)] = 10,
) -> dict:
    """Search PubMed and return matching articles with title, journal, date, authors, DOI, and URL.

    Returns lightweight summaries; use fetch_abstract for full abstract text. When curating a trial,
    search the NCT ID directly (e.g. 'NCT06137183') to find the results publication.
    """
    pmids = client.parse_pmids(await client.esearch(query, retmax=retmax))
    if not pmids:
        return _env(f"No PubMed results for '{query}'.", [])
    summaries = client.parse_summaries(await client.esummary(pmids))
    return _env(f"{len(summaries)} article(s) for '{query}'.", summaries, preview=summaries[:3])


@mcp.tool
async def fetch_abstract(
    pmid: Annotated[str, Field(description="PubMed ID, e.g. '39438660'")],
) -> dict:
    """Fetch the abstract text for a PubMed article, plus any NCT identifiers mentioned in it."""
    text = await client.efetch_abstract(pmid)
    ncts = client.find_nct_ids(text)
    return _env(
        f"Abstract for PMID {pmid} ({len(text)} chars); NCT IDs mentioned: {ncts or 'none'}.",
        {"pmid": pmid, "abstract": text, "nctIds": ncts},
        preview={"nctIds": ncts},
    )


@mcp.tool
async def verify_nct_in_article(
    pmid: Annotated[str, Field(description="PubMed ID to check")],
    nct_id: Annotated[str, Field(description="NCT identifier that must be present, e.g. 'NCT06137183'")],
) -> dict:
    """Confirm a specific NCT ID appears in an article's text — the mandatory verification step in
    the clinical trialist evidence cascade. Returns a boolean plus all NCT IDs found.
    """
    text = await client.efetch_abstract(pmid)
    ok = client.verify_nct(text, nct_id)
    return _env(
        f"PMID {pmid} {'CONFIRMS' if ok else 'does NOT confirm'} {nct_id.upper()}.",
        {"pmid": pmid, "nctId": nct_id.upper(), "verified": ok, "allNctIds": client.find_nct_ids(text)},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
