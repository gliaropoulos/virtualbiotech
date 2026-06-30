"""cBioPortal MCP server — oncology study discovery + clinicogenomic metadata.

Feeds the clinical trialist agent for oncology targets (prognostic biomarkers, survival cohorts;
e.g. the TCGA PanCancer Atlas LUAD cohort used in the B7-H3 case study). Heavy survival modeling is
done in analysis/b7h3_luad. Run:  python -m mcp_servers.cbioportal.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="cbioportal",
    instructions=(
        "Discover cancer genomics studies and their molecular profiles. find_cancer_studies "
        "locates cohorts by cancer type (e.g. 'lung adenocarcinoma' -> luad_tcga_pan_can_atlas_2018); "
        "get_molecular_profiles lists the expression/mutation/CNA profiles available for downstream "
        "biomarker-stratified survival analysis."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def find_cancer_studies(
    keyword: Annotated[str, Field(description="Cancer type or study term, e.g. 'lung adenocarcinoma' or 'LUAD'")],
) -> dict:
    """Find cBioPortal studies matching a cancer type or keyword.

    Returns study IDs, names, cancer types, and sample counts. Use the studyId with
    get_molecular_profiles and the analysis layer for biomarker-stratified survival.
    """
    matches = client.filter_studies(await client.all_studies(), keyword)
    return _env(
        f"{len(matches)} study(ies) matching '{keyword}'.", matches, preview=matches[:5],
    )


@mcp.tool
async def get_study_details(
    study_id: Annotated[str, Field(description="cBioPortal study ID, e.g. 'luad_tcga_pan_can_atlas_2018'")],
) -> dict:
    """Retrieve metadata for a single study (name, cancer type, sample count, reference genome)."""
    s = client.slim_study(await client.study_details(study_id))
    return _env(f"{s['name']} — {s['sampleCount']} samples.", s)


@mcp.tool
async def get_molecular_profiles(
    study_id: Annotated[str, Field(description="cBioPortal study ID")],
) -> dict:
    """List the molecular profiles (mRNA expression, mutations, CNA, etc.) available for a study,
    which downstream analysis uses to pull gene-level data for biomarker stratification.
    """
    profiles = client.slim_profiles(await client.molecular_profiles(study_id))
    kinds = sorted({p["alterationType"] for p in profiles if p["alterationType"]})
    return _env(
        f"{len(profiles)} molecular profile(s) for {study_id}; alteration types: {', '.join(kinds)}.",
        profiles, preview=profiles[:5],
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
