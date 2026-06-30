"""Live check (needs local data).  Usage: python -m mcp_servers.tahoe.smoke [DRUG]"""
import json, sys
from . import data
d = sys.argv[1] if len(sys.argv) > 1 else "vorinostat"
recs = data.load_drug_records(d)
print("available:", data.is_available())
print(json.dumps(data.score_drug(recs)["meanAcrossLines"], indent=2) if recs else "no data / drug")
