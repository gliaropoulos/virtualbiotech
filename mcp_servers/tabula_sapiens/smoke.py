"""Live check (needs local data).  Usage: python -m mcp_servers.tabula_sapiens.smoke [GENE]"""
import json, sys
from . import data
g = sys.argv[1] if len(sys.argv) > 1 else "OSMR"
print("available:", data.is_available())
print(json.dumps(data.compute_gene_features(g), indent=2) if data.is_available() else "no data")
