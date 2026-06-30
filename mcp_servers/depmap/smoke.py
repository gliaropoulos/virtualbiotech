"""Live check (needs local data).  Usage: python -m mcp_servers.depmap.smoke [GENE]"""
import json, sys
from . import data
g = sys.argv[1] if len(sys.argv) > 1 else "OSMR"
vals = data.load_gene_effect(g)
print("available:", data.is_available())
print(json.dumps(data.summarize_gene_effect(vals or []), indent=2) if vals else "no data / gene")
