"""gnomAD MCP server — gene constraint metrics for the Statistical Genetics agent.

Run:  python -m mcp_servers.gnomad.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="gnomad",
    instructions=(
        "gnomAD gene-level constraint. get_gene_constraint returns pLI and LOEUF (oe_lof_upper) "
        "with an interpretation of loss-of-function intolerance — useful for judging whether a "
        "target is dosage-sensitive / essential, which informs both target validation and safety."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def get_gene_constraint(
    symbol: Annotated[str, Field(description="HGNC gene symbol, e.g. 'OSMR'")],
    dataset: Annotated[str, Field(description="gnomAD dataset id, e.g. 'gnomad_r4'")] = "gnomad_r4",
    reference_genome: Annotated[str, Field(description="'GRCh38' or 'GRCh37'")] = "GRCh38",
) -> dict:
    """Return gnomAD constraint metrics for a gene: pLI, LOEUF (oe_lof_upper), observed/expected LoF,
    and missense/LoF z-scores, with a plain-language LoF-intolerance interpretation.

    Low LOEUF (< ~0.35) flags a gene that is highly intolerant to loss of function — often essential
    or haploinsufficient — which bears on both target validation and on-target safety risk.
    """
    data = await client.gene_constraint(symbol, dataset=dataset, reference_genome=reference_genome)
    s = client.summarize_constraint(data)
    return _env(
        f"{s['symbol']}: pLI={s['pLI']}, LOEUF={s['LOEUF']} — {s['lofInterpretation']}.",
        s, preview={"pLI": s["pLI"], "LOEUF": s["LOEUF"]},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
