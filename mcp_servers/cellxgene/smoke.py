"""Live check (needs cellxgene-census).  Usage: python -m mcp_servers.cellxgene.smoke [GENE]"""
import json, sys
from . import client
g = sys.argv[1] if len(sys.argv) > 1 else "OSMR"
print("available:", client.is_available())
rows = client.query_celltype_expression(g, tissue="lung")
print(json.dumps(client.summarize_by_celltype(rows)[:10], indent=2) if rows else "no data")
