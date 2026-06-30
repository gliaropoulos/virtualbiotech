"""One-off live check of the ClinicalTrials.gov client (no API key required).

Usage:  python -m mcp_servers.clinicaltrials.smoke [NCT_ID]
Default NCT is the OSMRbeta UC trial (NCT06137183) from case study 3.
"""
from __future__ import annotations

import asyncio
import json
import sys

from . import client


async def main(nct_id: str) -> None:
    study = await client.fetch_study(nct_id)
    summary = client.summarize_study(study)
    print(json.dumps(summary, indent=2)[:2000])
    ae = client.extract_adverse_events(study)
    print("\nAdverse events posted:", ae is not None)


if __name__ == "__main__":
    nct = sys.argv[1] if len(sys.argv) > 1 else "NCT06137183"
    asyncio.run(main(nct))
