"""Live smoke test of the granular Open Targets genetics tools (L2G, credible sets, QTL coloc).

Walks the full statistical-genetics flow against the live GraphQL API:
    resolve gene + disease  ->  GWAS credible-set evidence (L2G ranked)
                            ->  top credible set (fine-mapping posterior probs + QTL coloc)
                            ->  lead variant annotation

Usage:
    python -m mcp_servers.open_targets.smoke_genetics                  # OSMR / ulcerative colitis
    python -m mcp_servers.open_targets.smoke_genetics OSMR EFO_0000729
    python -m mcp_servers.open_targets.smoke_genetics IL23R EFO_0003767

Requires network to api.platform.opentargets.org. Confirms the live field paths match the shaping
helpers (the genetics schema is the most likely part of Open Targets to drift between releases).
"""
from __future__ import annotations

import asyncio
import json
import sys

from . import client, genetics


def _dump(label: str, obj) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(obj, indent=2, default=str)[:2200])


async def main(symbol: str, efo_id: str) -> None:
    # 1) resolve the gene symbol -> Ensembl ID
    hit = client.first_target_hit(await client.search(symbol, entity="target"))
    if not hit:
        print(f"Could not resolve gene '{symbol}'.")
        return
    ensembl_id = hit["ensemblId"]
    print(f"Resolved {symbol} -> {ensembl_id}; disease {efo_id}")

    # 2) GWAS credible-set evidence (L2G ranked)
    ev = genetics.summarize_gwas_evidence(
        await client.disease_gwas_evidence(ensembl_id, efo_id, size=25))
    _dump("GWAS credible-set evidence (top by L2G)",
          {"disease": ev["disease"], "count": ev["count"], "topL2G": ev["topL2G"],
           "topVariant": ev["topVariant"], "rows": ev["rows"][:3]})
    if not ev["topVariant"]:
        print("\nNo GWAS credible-set evidence for this target/disease; stopping.")
        return

    # 3) annotate the top L2G lead variant (guarded so a schema mismatch is reported, not fatal)
    try:
        v = genetics.summarize_variant(await client.variant(ev["topVariant"]))
        _dump("Lead variant annotation", v)
    except Exception as e:  # noqa: BLE001
        print(f"\n(get_variant not validated: {type(e).__name__}: {e})")

    # 4) fine-mapping + QTL colocalization for the lead variant's credible set
    try:
        cs = genetics.summarize_credible_set(await client.credible_set(ev["topVariant"]))
        _dump("Credible set (fine-mapping + coloc)",
              {"studyLocusId": cs["studyLocusId"], "finemappingMethod": cs["finemappingMethod"],
               "topMember": cs["topMember"], "topL2G": cs["topL2G"], "topColoc": cs["topColoc"]})
    except Exception as e:  # noqa: BLE001
        print(f"\n(get_credible_set not validated: {type(e).__name__}: {e})")


if __name__ == "__main__":
    args = sys.argv[1:]
    sym = args[0] if len(args) > 0 else "OSMR"
    efo = args[1] if len(args) > 1 else "EFO_0000729"  # ulcerative colitis
    asyncio.run(main(sym, efo))
