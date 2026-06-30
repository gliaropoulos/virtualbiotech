"""Tahoe-100M MCP server — drug-perturbation hallmark scores for the Functional Genomics agent.

Data-gated: requires data/tahoe/tahoe100m_pseudobulk_lfc.parquet. Run:
python -m mcp_servers.tahoe.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import data
from virtual_biotech.science import perturbation as pert

mcp = FastMCP(
    name="tahoe",
    instructions=(
        "Tahoe-100M drug-perturbation transcriptomics. get_drug_hallmark_scores returns six "
        "efficacy-oriented signature scores (apoptosis, proliferation suppression, DNA-damage "
        "response, stress, resistance, cell-cycle arrest) for a drug across cancer cell lines. "
        "list_hallmarks describes the gene sets."
    ),
)


def _env(summary: str, data_, preview=None) -> dict:
    return {"summary": summary, "data": data_, "preview": preview}


@mcp.tool
async def list_hallmarks() -> dict:
    """List the six hallmark signatures, their direction coefficients, and gene-set sizes."""
    rows = [
        {"name": hm.name, "direction": hm.direction,
         "nGenes": len(hm.genes) + len(hm.opposite_genes)}
        for hm in pert.HALLMARKS.values()
    ]
    return _env(f"{len(rows)} hallmark signatures.", rows)


@mcp.tool
async def get_drug_hallmark_scores(
    drug: Annotated[str, Field(description="Drug/compound name as in the Tahoe atlas")],
    cell_line: Annotated[str | None, Field(description="Restrict to one cell line; omit for all")] = None,
) -> dict:
    """Compute hallmark signature scores for a drug perturbation.

    Returns per-cell-line scores and the mean across lines. Positive scores indicate the expected
    efficacy direction (for 'resistance', positive indicates a resistance mechanism). Non-significant
    LFCs (adjusted p >= 0.05) are zeroed before scoring, per the paper.
    """
    if not data.is_available():
        return _env(
            "Tahoe data not installed. Run `python scripts/setup_data.py --dataset tahoe`.",
            {"available": False},
        )
    records = data.load_drug_records(drug, cell_line)
    if not records:
        return _env(f"No Tahoe profiles for drug '{drug}'"
                    + (f" in {cell_line}." if cell_line else "."), {"drug": drug, "found": False})
    result = data.score_drug(records)
    result["drug"] = drug
    return _env(
        f"{drug}: hallmark scores over {result['nProfiles']} profile(s).",
        result, preview=result["meanAcrossLines"],
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
