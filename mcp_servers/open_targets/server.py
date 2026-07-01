"""Open Targets Platform MCP server.

Backbone data source feeding the statistical genetics, pharmacologist, target biologist, and
bio-pathways agents. Tools cover entity search, target details + tractability + safety liabilities,
target-disease association / genetic-evidence breakdown, and known drugs / mechanisms of action.

Run:  python -m mcp_servers.open_targets.server
"""
from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from . import client

mcp = FastMCP(
    name="open_targets",
    instructions=(
        "Open Targets Platform (v4). Resolve a gene symbol to an Ensembl ID with "
        "search_entities first, then call target tools with that Ensembl ID. "
        "get_target_genetic_evidence returns the genetic_association score used to judge genetic "
        "support; get_target_known_drugs returns clinical precedence and mechanisms of action."
    ),
)


def _env(summary: str, data, preview=None) -> dict:
    return {"summary": summary, "data": data, "preview": preview}


@mcp.tool
async def search_entities(
    query: Annotated[str, Field(description="Free text, e.g. a gene symbol 'OSMR', disease, or drug name")],
    entity: Annotated[str | None, Field(description="Restrict to 'target', 'disease', or 'drug'")] = None,
) -> dict:
    """Search Open Targets for targets, diseases, or drugs and resolve names to platform IDs.

    Use this first to turn a gene symbol into an Ensembl gene ID (e.g. 'OSMR' -> 'ENSG00000145623')
    or a disease name into an EFO ID, which the other tools require. Returns ranked hits with their
    id, entity type, and key attributes.
    """
    data = await client.search(query, entity=entity)
    hits = (data.get("search", {}) or {}).get("hits", [])
    slim = [{"id": h.get("id"), "entity": h.get("entity"), "name": h.get("name")} for h in hits[:10]]
    target = client.first_target_hit(data)
    msg = f"{len(hits)} hit(s) for '{query}'."
    if target:
        msg += f" Top target: {target['symbol']} ({target['ensemblId']})."
    return _env(msg, slim, preview=target)


@mcp.tool
async def get_target_details(
    ensembl_id: Annotated[str, Field(description="Ensembl gene ID, e.g. 'ENSG00000145623'")],
) -> dict:
    """Retrieve core biology for a target: approved symbol/name, biotype, subcellular localization,
    tractable modalities (small molecule / antibody / etc.), and known safety liabilities.

    Feeds the target biologist (modality feasibility) and bio-pathways/safety reasoning.
    """
    data = await client.target_details(ensembl_id)
    s = client.summarize_target(data)
    mods = ", ".join(s["tractableModalities"]) or "none reported"
    return _env(
        f"{s['symbol']} ({s['biotype']}); tractable modalities: {mods}; "
        f"{len(s['safetyLiabilities'])} safety liabilities.",
        s, preview={"symbol": s["symbol"], "modalities": s["tractableModalities"]},
    )


@mcp.tool
async def get_target_genetic_evidence(
    ensembl_id: Annotated[str, Field(description="Ensembl gene ID")],
    disease_id: Annotated[str | None, Field(description="Optional EFO disease ID to filter to one disease")] = None,
    size: Annotated[int, Field(description="Max associated diseases to scan", ge=1, le=200)] = 50,
) -> dict:
    """Assess genetic support for a target by extracting the genetic_association datatype score
    across associated diseases (optionally filtered to one disease).

    Returns a per-disease breakdown (overall association score + genetic-association score) and a
    binary hasGeneticEvidence flag, mirroring the genetic-evidence indicator used in the paper's
    trial-outcome analysis.
    """
    data = await client.target_associated_diseases(ensembl_id, size=size)
    ge = client.genetic_evidence(data, disease_id=disease_id)
    n = len(ge["diseases"])
    return _env(
        f"{ge['symbol']}: hasGeneticEvidence={ge['hasGeneticEvidence']} across {n} disease(s).",
        ge, preview={"hasGeneticEvidence": ge["hasGeneticEvidence"]},
    )


@mcp.tool
async def get_target_known_drugs(
    ensembl_id: Annotated[str, Field(description="Ensembl gene ID")],
    size: Annotated[int, Field(description="Max known-drug rows", ge=1, le=200)] = 50,
) -> dict:
    """List drugs and clinical candidates acting on this target, with mechanism of action, max
    clinical phase, status, and indication — i.e. clinical precedence for the pharmacologist.
    """
    data = await client.target_known_drugs(ensembl_id, size=size)
    kd = client.summarize_known_drugs(data, limit=size)
    return _env(
        f"{kd['symbol']}: {kd['count']} known drug entries.", kd,
        preview=kd["drugs"][:5],
    )


@mcp.tool
async def get_disease_details(
    efo_id: Annotated[str, Field(description="EFO disease ID, e.g. 'EFO_0000729' (ulcerative colitis)")],
) -> dict:
    """Retrieve disease name, description, and therapeutic areas for an EFO ID."""
    data = await client.disease_details(efo_id)
    d = data.get("disease") or {}
    return _env(
        f"{d.get('name')} ({efo_id}).",
        {"id": d.get("id"), "name": d.get("name"), "description": d.get("description"),
         "therapeuticAreas": [ta.get("name") for ta in (d.get("therapeuticAreas") or [])]},
    )


# ---- granular genetics tools (L2G, credible sets, QTL colocalization) ---------

@mcp.tool
async def get_gwas_credible_set_evidence(
    ensembl_id: Annotated[str, Field(description="Ensembl gene ID, e.g. 'ENSG00000145623'")],
    efo_id: Annotated[str, Field(description="EFO disease ID, e.g. 'EFO_0000729' (ulcerative colitis)")],
    size: Annotated[int, Field(description="Max credible-set evidence rows", ge=1, le=200)] = 25,
) -> dict:
    """Retrieve GWAS credible-set evidence linking a target to a disease, ranked by L2G score.

    Each row is credible-set-derived evidence whose causal gene is (predicted to be) this target: it
    carries the L2G-linked evidence score, the lead variant (id + rsID), the association
    p-value / beta / odds ratio, and the study. Pass the returned lead variant id to get_variant for
    annotation, or to get_credible_set to drill into fine-mapping posterior probabilities, L2G
    predictions, and QTL colocalization.
    """
    data = await client.disease_gwas_evidence(ensembl_id, efo_id, size=size)
    s = client.genetics.summarize_gwas_evidence(data)
    return _env(
        f"{s['count']} GWAS credible-set evidence row(s) for the target in {s['disease']}; "
        f"top L2G={s['topL2G']} (lead variant {s['topVariant']}).",
        s, preview={"topL2G": s["topL2G"], "topVariant": s["topVariant"]},
    )


@mcp.tool
async def get_credible_set(
    study_locus_id: Annotated[str, Field(description="Study-locus (credible set) ID from GWAS evidence")],
) -> dict:
    """Retrieve one fine-mapped credible set in full: the finemapping method, lead variant, the 95%
    credible-set variants with their posterior probabilities, the L2G gene predictions, and QTL
    colocalization rows (H4 and CLPP).

    This is where fine-mapping confidence lives — e.g. a lead variant with posterior probability
    ~0.9997 indicates a well-resolved causal signal; high H4/CLPP indicate a GWAS signal that
    colocalizes with a molecular QTL.
    """
    data = await client.credible_set(study_locus_id)
    s = client.genetics.summarize_credible_set(data)
    top_member = s.get("topMember") or {}
    top_coloc = s.get("topColoc") or {}
    msg = (f"Credible set {s['studyLocusId']} ({s['finemappingMethod']}): "
           f"{s['nCredibleSetVariants']} variants; top posterior "
           f"{top_member.get('posteriorProbability')}.")
    if s.get("topL2G"):
        msg += f" Top L2G: {s['topL2G']['symbol']}={s['topL2G']['score']}."
    if top_coloc:
        msg += f" Top coloc H4={top_coloc.get('h4')}, CLPP={top_coloc.get('clpp')}."
    return _env(msg, s, preview={"topMember": top_member, "topL2G": s.get("topL2G")})


@mcp.tool
async def get_variant(
    variant_id: Annotated[str, Field(description="Variant ID, e.g. '5_38953040_G_A' (chr_pos_ref_alt)")],
) -> dict:
    """Retrieve annotation for a variant: rsID(s), location, alleles, most severe consequence, and
    population allele frequencies. Useful for characterizing a credible set's lead variant.
    """
    data = await client.variant(variant_id)
    s = client.genetics.summarize_variant(data)
    return _env(
        f"{s['id']} ({', '.join(s['rsIds'] or []) or 'no rsID'}); "
        f"consequence: {s['mostSevereConsequence']}.",
        s, preview={"rsIds": s["rsIds"], "consequence": s["mostSevereConsequence"]},
    )


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
