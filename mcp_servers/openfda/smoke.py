"""Live check.  Usage: python -m mcp_servers.openfda.smoke [DRUG]"""
import asyncio, json, sys
from . import client

async def main(drug):
    print(json.dumps(client.parse_counts(await client.top_reactions(drug, limit=5)), indent=2))
    print("total:", client.total_reports(await client.report_count(drug)))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "adalimumab"))
