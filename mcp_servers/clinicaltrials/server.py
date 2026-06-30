"""ClinicalTrials.gov MCP server.

Reference implementation that establishes the pattern for every other Virtual Biotech
MCP server: each tool is a typed async function with a thorough docstring (FastMCP
introspects these into the schema the model sees) and returns a `tool_result` envelope
of {summary, data, preview} so agents can triage quickly before pulling full payloads.

Run:  python -m mcp_servers.clinicaltrials.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="clinicaltrials",
    instructions=(
        "Tools for the ClinicalTrials.gov v2 registry. Use get_clinical_trial_details first "
        "for any known NCT ID; use search_clinical_trials to discover trials by condition, "
        "intervention, or target/gene term. get_trial_adverse_events returns posted safety "
        "results when available."
    ),
)


def _envelope(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def get_clinical_trial_details(
    nct_id: Annotated[str, Field(description="National Clinical Trial identifier, e.g. 'NCT06137183'")],
) -> dict:
    """Retrieve the full record for one clinical trial by NCT ID.

    Returns trial title, status, phase, study type, enrollment, conditions, interventions,
    eligibility criteria, primary/secondary outcome definitions, the `whyStopped` field (for
    terminated trials), and whether posted results / adverse events are available. This is the
    Level-1 source in the clinical trialist agent's evidence cascade — always call it first.
    """
    study = await client.fetch_study(nct_id)
    summary = client.summarize_study(study)
    status = summary.get("overallStatus")
    phases = ",".join(summary.get("phases") or []) or "n/a"
    text = (
        f"{summary.get('nctId')}: {summary.get('title')} — status={status}, phase={phases}, "
        f"enrollment={summary.get('enrollment')}. "
        f"Results posted: {summary.get('hasResults')}."
    )
    if summary.get("whyStopped"):
        text += f" Stopped because: {summary['whyStopped']}"
    return _envelope(text, summary, preview={"nctId": summary["nctId"], "status": status})


@mcp.tool
async def search_clinical_trials(
    query: Annotated[str | None, Field(description="Free-text term, e.g. a gene/target like 'OSMR' or a drug")] = None,
    condition: Annotated[str | None, Field(description="Disease/condition, e.g. 'ulcerative colitis'")] = None,
    intervention: Annotated[str | None, Field(description="Drug or intervention name")] = None,
    phase: Annotated[str | None, Field(description="Trial phase filter, e.g. 'PHASE2' or 'PHASE3'")] = None,
    status: Annotated[str | None, Field(description="Overall status, e.g. 'TERMINATED', 'COMPLETED'")] = None,
    page_size: Annotated[int, Field(description="Max results (<=100)", ge=1, le=100)] = 20,
) -> dict:
    """Search ClinicalTrials.gov for trials matching a target/gene, condition, drug, phase, or status.

    Use this to find prior clinical precedence for a target or pathway, or to assemble a cohort of
    trials for large-scale analysis. Returns a lightweight list (NCT ID, title, status, phase) — call
    get_clinical_trial_details for any trial you want to analyze in depth.
    """
    raw = await client.search_studies(
        query, condition=condition, intervention=intervention,
        phase=phase, status=status, page_size=page_size,
    )
    studies = raw.get("studies", [])
    rows = [client.summarize_study(s) for s in studies]
    slim = [
        {"nctId": r["nctId"], "title": r["title"], "status": r["overallStatus"], "phases": r["phases"]}
        for r in rows
    ]
    return _envelope(
        f"Found {len(slim)} trial(s) (page size {page_size}).",
        slim,
        preview=slim[:5],
    )


@mcp.tool
async def get_trial_adverse_events(
    nct_id: Annotated[str, Field(description="NCT identifier of a trial with posted results")],
) -> dict:
    """Retrieve posted adverse-event data (serious and other events, by arm) for a trial, if available.

    Many trials have no posted AE data; in that case `data` is null and the agent should fall back to
    PubMed / press releases (evidence cascade levels 2-3). When present, returns serious-event groups,
    other-event groups, the frequency threshold, and arm-level event group definitions for computing
    organ-system AE rates.
    """
    study = await client.fetch_study(nct_id)
    ae = client.extract_adverse_events(study)
    if ae is None:
        return _envelope(f"No posted adverse-event results for {nct_id}.", None)
    n_serious = len(ae.get("seriousEventGroups") or [])
    return _envelope(
        f"{nct_id} has posted adverse-event data ({n_serious} serious-event entries).", ae,
        preview={"frequencyThreshold": ae.get("frequencyThreshold")},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
