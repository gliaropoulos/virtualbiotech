"""CELLxGENE Census MCP server — cell-type expression for the Single-Cell Atlas agent.

API-based (no local download), via the cellxgene-census package. Degrades gracefully if the package
is not installed. Run: python -m mcp_servers.cellxgene.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="cellxgene",
    instructions=(
        "Query the CELLxGENE Census (100M+ harmonized single-cell profiles). "
        "get_celltype_expression returns mean expression of a gene per cell type, optionally "
        "filtered to a tissue or disease — for cell-type-specific expression and disease context."
    ),
)


def _env(summary: str, data_, preview=None) -> dict:
    return {"summary": summary, "data": data_, "preview": preview}


@mcp.tool
async def get_celltype_expression(
    gene: Annotated[str, Field(description="Gene symbol (feature_name), e.g. 'OSMR'")],
    tissue: Annotated[str | None, Field(description="Optional tissue_general filter, e.g. 'lung'")] = None,
    disease: Annotated[str | None, Field(description="Optional disease filter, e.g. 'ulcerative colitis'")] = None,
) -> dict:
    """Return mean expression of a gene per cell type from the Census, ranked high to low.

    Optionally restrict to a tissue and/or disease. Use to identify which cell types express a
    target and how that differs by tissue or disease state.
    """
    if not client.is_available():
        return _env(
            "cellxgene-census not installed. Run `pip install cellxgene-census`.",
            {"available": False},
        )
    rows = client.query_celltype_expression(gene, tissue=tissue, disease=disease)
    if not rows:
        return _env(f"No Census cells for '{gene}'"
                    + (f" in {tissue}" if tissue else "") + ".", {"gene": gene, "found": False})
    summary = client.summarize_by_celltype(rows)
    return _env(
        f"{gene}: expression across {len(summary)} cell type(s)"
        + (f" in {tissue}" if tissue else "") + ".",
        {"gene": gene, "byCellType": summary}, preview=summary[:5],
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
