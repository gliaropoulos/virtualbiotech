"""Interactive explorer for the Virtual Biotech MCP tool layer.

Lets you poke at every data tool with REAL data, no API key or agent runtime needed — just network
for the public-API servers. This is the fastest way to test the platform yourself before the
conversational agent layer is wired.

Examples:
    python scripts/explore.py servers
    python scripts/explore.py tools clinicaltrials
    python scripts/explore.py call clinicaltrials get_clinical_trial_details nct_id=NCT06137183
    python scripts/explore.py call open_targets search_entities query=OSMR entity=target
    python scripts/explore.py call gnomad get_gene_constraint symbol=OSMR
    python scripts/explore.py                       # interactive REPL

Data-gated servers (tabula_sapiens, tahoe, depmap) return a friendly "data not installed" message
until you download their datasets; cellxgene streams (needs `pip install -e '.[singlecell]'`).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Running as `python scripts/explore.py` puts `scripts/` on sys.path, not the repo root.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# server name -> dotted path of its FastMCP `mcp` object
SERVERS = {
    "clinicaltrials": "mcp_servers.clinicaltrials.server",
    "open_targets": "mcp_servers.open_targets.server",
    "pubmed": "mcp_servers.pubmed.server",
    "openfda": "mcp_servers.openfda.server",
    "dailymed": "mcp_servers.dailymed.server",
    "gnomad": "mcp_servers.gnomad.server",
    "cbioportal": "mcp_servers.cbioportal.server",
    "tabula_sapiens": "mcp_servers.tabula_sapiens.server",
    "tahoe": "mcp_servers.tahoe.server",
    "depmap": "mcp_servers.depmap.server",
    "cellxgene": "mcp_servers.cellxgene.server",
}


def _load(server: str):
    import importlib
    if server not in SERVERS:
        raise SystemExit(f"unknown server '{server}'. Known: {', '.join(SERVERS)}")
    return importlib.import_module(SERVERS[server]).mcp


def parse_kwargs(pairs: list[str]) -> dict:
    """Parse key=value CLI args, casting ints/floats/bools/null; everything else stays a string."""
    out: dict = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"argument '{p}' must be key=value")
        k, v = p.split("=", 1)
        out[k] = _coerce(v)
    return out


def _coerce(v: str):
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def _render(result) -> str:
    """FastMCP returns a CallToolResult; pull out the structured payload if present."""
    data = getattr(result, "structured_content", None) or getattr(result, "data", None)
    if data is None:
        blocks = getattr(result, "content", [])
        texts = [getattr(b, "text", "") for b in blocks]
        return "\n".join(t for t in texts if t)
    return json.dumps(data, indent=2, default=str)


async def list_tools(server: str) -> None:
    from fastmcp import Client
    async with Client(_load(server)) as c:
        for t in await c.list_tools():
            params = ", ".join((t.inputSchema or {}).get("properties", {}).keys())
            print(f"  {t.name}({params})")
            if t.description:
                print(f"      {t.description.strip().splitlines()[0]}")


async def call_tool(server: str, tool: str, kwargs: dict) -> None:
    from fastmcp import Client
    async with Client(_load(server)) as c:
        result = await c.call_tool(tool, kwargs)
        print(_render(result))


def list_servers() -> None:
    print("Available MCP servers:")
    for name in SERVERS:
        print(f"  {name}")
    print("\nUse:  python scripts/explore.py tools <server>")
    print("      python scripts/explore.py call <server> <tool> key=value ...")


async def repl() -> None:
    print("Virtual Biotech explorer. Commands: servers | tools <s> | call <s> <tool> k=v ... | quit")
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = (await loop.run_in_executor(None, input, "vb> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        parts = line.split()
        cmd, rest = parts[0], parts[1:]
        try:
            if cmd in ("quit", "exit"):
                return
            elif cmd == "servers":
                list_servers()
            elif cmd == "tools" and rest:
                await list_tools(rest[0])
            elif cmd == "call" and len(rest) >= 2:
                await call_tool(rest[0], rest[1], parse_kwargs(rest[2:]))
            else:
                print("usage: servers | tools <server> | call <server> <tool> k=v ... | quit")
        except SystemExit as e:
            print(e)
        except Exception as e:  # keep the REPL alive on tool/network errors
            print(f"error: {type(e).__name__}: {e}")


def main(argv: list[str]) -> None:
    if not argv:
        asyncio.run(repl())
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "servers":
        list_servers()
    elif cmd == "tools" and rest:
        asyncio.run(list_tools(rest[0]))
    elif cmd == "call" and len(rest) >= 2:
        asyncio.run(call_tool(rest[0], rest[1], parse_kwargs(rest[2:])))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
