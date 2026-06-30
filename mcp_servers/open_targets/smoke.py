"""Live check of the Open Targets client.  Usage: python -m mcp_servers.open_targets.smoke [SYMBOL]"""
from __future__ import annotations

import asyncio
import json
import sys

from . import client


async def main(symbol: str) -> None:
    found = client.first_target_hit(await client.search(symbol, entity="target"))
    print("resolved:", found)
    if not found:
        return
    eid = found["ensemblId"]
    print(json.dumps(client.summarize_target(await client.target_details(eid)), indent=2))
    print(json.dumps(client.genetic_evidence(await client.target_associated_diseases(eid)), indent=2)[:1500])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "OSMR"))
