"""Live check.  Usage: python -m mcp_servers.dailymed.smoke [DRUG]"""
import asyncio, json, sys
from . import client

async def main(drug):
    label = client.first_label(await client.fetch_label(drug))
    print("boxed warning:", client.has_boxed_warning(label) if label else "no label")
    if label:
        print(json.dumps(list(client.extract_sections(label).keys()), indent=2))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "adalimumab"))
