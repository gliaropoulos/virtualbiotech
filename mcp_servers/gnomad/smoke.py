"""Live check.  Usage: python -m mcp_servers.gnomad.smoke [SYMBOL]"""
import asyncio, json, sys
from . import client

async def main(sym):
    print(json.dumps(client.summarize_constraint(await client.gene_constraint(sym)), indent=2))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "OSMR"))
