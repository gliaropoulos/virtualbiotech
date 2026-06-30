"""Tabula Sapiens MCP server — cell-type specificity & expression heterogeneity features.

Serves the Single-Cell Atlas agent (off-target safety + target prioritization). Data-gated:
requires data/tabula_sapiens/tabula_sapiens_v2.h5ad. Run:
python -m mcp_servers.tabula_sapiens.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import data

mcp = FastMCP(
    name="tabula_sapiens",
    instructions=(
        "Tabula Sapiens v2 healthy reference (27 tissues). get_celltype_specificity returns a "
        "gene's tau index (0 ubiquitous .. 1 cell-type-specific); get_expression_heterogeneity "
        "returns the bimodality coefficient (>0.555 suggests two subpopulations). Both inform "
        "off-target safety and target selectivity."
    ),
)


def _env(summary: str, data_, preview=None) -> dict:
    return {"summary": summary, "data": data_, "preview": preview}


def _gene_features(gene: str):
    if not data.is_available():
        return _env(
            "Tabula Sapiens data not installed. Run "
            "`python scripts/setup_data.py --dataset tabula_sapiens`.",
            {"available": False},
        ), None
    feats = data.compute_gene_features(gene)
    if feats is None:
        return _env("Tabula Sapiens requires the `anndata` package (pip install anndata).",
                    {"available": False}), None
    if not feats.get("found"):
        return _env(f"Gene '{gene}' not found in the atlas.", {"gene": gene, "found": False}), None
    return None, feats


@mcp.tool
async def get_celltype_specificity(
    gene: Annotated[str, Field(description="HGNC gene symbol, e.g. 'OSMR'")],
) -> dict:
    """Return the tau cell-type-specificity index for a gene (global + per-tissue), with the
    cell-type-specific vs broadly-expressed classification (threshold tau = 0.69).

    High tau means expression concentrated in few cell types — favorable for a targeted therapy and
    lower off-target risk; low tau means broad expression and higher on-target/off-tumor risk.
    """
    early, feats = _gene_features(gene)
    if early:
        return early
    return _env(
        f"{gene}: tau={feats['tau']} ({feats['specificity']}) over {feats['nTissues']} tissue(s).",
        {k: feats[k] for k in ("gene", "tau", "specificity", "nTissues", "perTissue")},
        preview={"tau": feats["tau"], "specificity": feats["specificity"]},
    )


@mcp.tool
async def get_expression_heterogeneity(
    gene: Annotated[str, Field(description="HGNC gene symbol")],
) -> dict:
    """Return the bimodality coefficient for a gene across expressing cells (global + per-tissue).

    BC > 0.555 suggests distinct expressing subpopulations — relevant for biomarker-defined
    endotypes and for understanding heterogeneous target expression.
    """
    early, feats = _gene_features(gene)
    if early:
        return early
    return _env(
        f"{gene}: bimodality={feats['bimodalityCoefficient']} (bimodal={feats['bimodal']}).",
        {"gene": feats["gene"], "bimodalityCoefficient": feats["bimodalityCoefficient"],
         "bimodal": feats["bimodal"], "perTissue": feats["perTissue"]},
        preview={"bimodalityCoefficient": feats["bimodalityCoefficient"]},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
