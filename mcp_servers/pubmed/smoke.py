"""Live check.  Usage: python -m mcp_servers.pubmed.smoke [QUERY]"""
import asyncio, json, sys
from . import client

async def main(q):
    pmids = client.parse_pmids(await client.esearch(q, retmax=3))
    print("pmids:", pmids)
    if pmids:
        print(json.dumps(client.parse_summaries(await client.esummary(pmids)), indent=2)[:1500])

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "NCT06137183"))
