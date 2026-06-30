"""DepMap MCP server — CRISPR knockout essentiality for the Functional Genomics agent.

Data-gated: requires data/depmap/CRISPRGeneEffect.csv (see scripts/setup_data.py). Tools degrade
gracefully with a clear message when the dataset is absent. Run: python -m mcp_servers.depmap.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import data

mcp = FastMCP(
    name="depmap",
    instructions=(
        "DepMap CRISPR gene-effect (Chronos). get_gene_essentiality summarizes how strongly cell "
        "lines depend on a gene (more negative = stronger dependency; common-essential ~ median "
        "<= -0.5). Use to judge whether a target is essential and how selective that dependency is."
    ),
)


def _env(summary: str, data_, preview=None) -> dict:
    return {"summary": summary, "data": data_, "preview": preview}


def _unavailable(tool: str) -> dict:
    return _env(
        "DepMap data not installed. Run `python scripts/setup_data.py --dataset depmap`.",
        {"available": False, "tool": tool},
    )


@mcp.tool
async def get_gene_essentiality(
    gene: Annotated[str, Field(description="HGNC gene symbol, e.g. 'OSMR'")],
) -> dict:
    """Summarize a gene's CRISPR knockout dependency across DepMap cell lines.

    Returns mean/median gene effect, the fraction of lines that depend on the gene, the fraction
    strongly dependent, and a common-essential flag. Strongly negative, broadly shared dependency
    implies a potentially toxic (pan-essential) target; selective dependency is more druggable.
    """
    if not data.is_available():
        return _unavailable("get_gene_essentiality")
    values = data.load_gene_effect(gene)
    if not values:
        return _env(f"Gene '{gene}' not found in DepMap matrix.", {"gene": gene, "found": False})
    summary = data.summarize_gene_effect(values)
    summary["gene"] = gene
    return _env(
        f"{gene}: median effect {summary['medianEffect']}, "
        f"{summary['fractionDependent']:.0%} of lines dependent, "
        f"commonEssential={summary['commonEssential']}.",
        summary, preview={"medianEffect": summary["medianEffect"],
                          "commonEssential": summary["commonEssential"]},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
