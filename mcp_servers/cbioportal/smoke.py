"""Live check.  Usage: python -m mcp_servers.cbioportal.smoke [KEYWORD]"""
import asyncio, json, sys
from . import client

async def main(kw):
    print(json.dumps(client.filter_studies(await client.all_studies(), kw)[:5], indent=2))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "lung adenocarcinoma"))
