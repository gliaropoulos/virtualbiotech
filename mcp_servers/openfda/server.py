"""OpenFDA MCP server — empirical drug-safety signals for the FDA Safety Officer agent.

Run:  python -m mcp_servers.openfda.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="openfda",
    instructions=(
        "Query FDA FAERS adverse-event reports by drug/substance. get_top_adverse_reactions ranks "
        "reaction terms; get_report_counts gives total and serious report volumes. Use to ground "
        "mechanistic safety reasoning in real post-market signals."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def get_top_adverse_reactions(
    drug: Annotated[str, Field(description="Generic or brand drug name, e.g. 'adalimumab'")],
    limit: Annotated[int, Field(description="Number of top reaction terms", ge=1, le=50)] = 10,
) -> dict:
    """Return the most frequently reported adverse-reaction terms (MedDRA) for a drug, with counts.

    This is the primary safety-signal view: it surfaces the dominant reported toxicities for a drug
    sharing the target/mechanism under evaluation.
    """
    counts = client.parse_counts(await client.top_reactions(drug, limit=limit))
    return _env(
        f"Top {len(counts)} reported reactions for '{drug}'.", counts, preview=counts[:5],
    )


@mcp.tool
async def get_report_counts(
    drug: Annotated[str, Field(description="Generic or brand drug name")],
) -> dict:
    """Return total and serious FAERS report counts for a drug (a coarse exposure/severity gauge)."""
    total = client.total_reports(await client.report_count(drug))
    serious = client.total_reports(await client.report_count(drug, serious_only=True))
    frac = round(serious / total, 3) if total else None
    return _env(
        f"'{drug}': {total} reports, {serious} serious ({frac if frac is not None else 'n/a'}).",
        {"drug": drug, "totalReports": total, "seriousReports": serious, "seriousFraction": frac},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
