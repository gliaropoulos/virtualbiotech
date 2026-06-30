"""Async client + parsers for the gnomAD GraphQL API.

Endpoint: https://gnomad.broadinstitute.org/api (POST). Provides gene-level constraint metrics —
pLI and LOEUF (oe_lof_upper), the standard measures of intolerance to loss-of-function variation
the statistical genetics agent uses to gauge whether a gene is essential / dosage-sensitive.
Parsers are pure and unit-tested. Schema: https://gnomad.broadinstitute.org/api (GraphiQL).
"""
from __future__ import annotations

from typing import Any

import httpx

ENDPOINT = "https://gnomad.broadinstitute.org/api"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "virtual-biotech/0.1 (research)", "Content-Type": "application/json"}

GENE_CONSTRAINT = """
query GeneConstraint($symbol: String!, $dataset: DatasetId!, $ref: ReferenceGenomeId!) {
  gene(gene_symbol: $symbol, reference_genome: $ref) {
    gene_id
    symbol
    chrom
    gnomad_constraint {
      pli
      oe_lof
      oe_lof_lower
      oe_lof_upper
      oe_mis
      mis_z
      lof_z
      obs_lof
      exp_lof
    }
    variants(dataset: $dataset) {
      variant_id
      consequence
    }
  }
}
"""


async def execute(query: str, variables: dict[str, Any], endpoint: str = ENDPOINT) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as c:
        resp = await c.post(endpoint, json={"query": query, "variables": variables})
        resp.raise_for_status()
        body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"gnomAD GraphQL errors: {body['errors']}")
    return body.get("data", {})


async def gene_constraint(symbol: str, dataset: str = "gnomad_r4",
                          reference_genome: str = "GRCh38") -> dict[str, Any]:
    return await execute(GENE_CONSTRAINT,
                         {"symbol": symbol, "dataset": dataset, "ref": reference_genome})


# ---- pure parsers ------------------------------------------------------------

def _loeuf_interpretation(loeuf: float | None) -> str:
    if loeuf is None:
        return "unknown"
    # Conventional gnomAD guidance: low LOEUF => strong LoF-intolerance.
    if loeuf < 0.35:
        return "highly LoF-intolerant (likely haploinsufficient / essential)"
    if loeuf < 0.6:
        return "LoF-intolerant"
    return "LoF-tolerant"


def summarize_constraint(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten the gene constraint block and add an interpretation of LOEUF."""
    gene = data.get("gene") or {}
    c = gene.get("gnomad_constraint") or {}
    loeuf = c.get("oe_lof_upper")
    return {
        "symbol": gene.get("symbol"),
        "geneId": gene.get("gene_id"),
        "chrom": gene.get("chrom"),
        "pLI": c.get("pli"),
        "LOEUF": loeuf,
        "oe_lof": c.get("oe_lof"),
        "mis_z": c.get("mis_z"),
        "lof_z": c.get("lof_z"),
        "obs_lof": c.get("obs_lof"),
        "exp_lof": c.get("exp_lof"),
        "lofInterpretation": _loeuf_interpretation(loeuf),
    }


def count_lof_variants(data: dict[str, Any]) -> int:
    gene = data.get("gene") or {}
    variants = gene.get("variants") or []
    lof_terms = {"frameshift_variant", "stop_gained", "splice_donor_variant",
                 "splice_acceptor_variant"}
    return sum(1 for v in variants if v.get("consequence") in lof_terms)
