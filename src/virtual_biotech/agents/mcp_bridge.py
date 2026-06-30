"""Bridge the FastMCP data servers into in-process Claude Agent SDK MCP servers.

The Agent SDK runs tools through `create_sdk_mcp_server` (in-process, no subprocess/IPC). Rather than
redefining every tool, we wrap each FastMCP tool: the SDK tool reuses the FastMCP tool's name,
description, and JSON-schema parameters, and its handler calls the FastMCP tool's underlying function
directly (`FunctionTool.fn`). This means the agents call exactly the same tested tool code the
explorer and unit tests exercise.

SDK MCP server tools are exposed to the model as `mcp__<server>__<tool>`; `tool_names_for` returns
those fully-qualified names for `ClaudeAgentOptions.allowed_tools`.
"""
from __future__ import annotations

import importlib
import json
from functools import lru_cache
from typing import Any

# server name -> dotted path of its FastMCP `mcp` object (same registry the explorer uses)
SERVER_MODULES = {
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


def _resolve(value):
    """Resolve an awaitable to its value, working whether or not a loop is already running.

    FastMCP's list_tools/get_tool are async; we may need them from sync code or from inside an
    event loop (e.g. during BaseAgent.run), so we run the coroutine in a dedicated worker thread.
    """
    if not hasattr(value, "__await__"):
        return value
    import asyncio
    import threading
    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["value"] = asyncio.run(value)
        except BaseException as e:  # noqa: BLE001
            box["error"] = e

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


@lru_cache(maxsize=None)
def _fastmcp_tools(server_name: str) -> tuple:
    """Return the FastMCP FunctionTool objects for a server (resolved once, then cached)."""
    mcp = importlib.import_module(SERVER_MODULES[server_name]).mcp
    proto_tools = _resolve(mcp.list_tools())          # protocol tools carry the names
    if isinstance(proto_tools, dict):
        proto_tools = list(proto_tools.values())
    function_tools = [_resolve(mcp.get_tool(pt.name)) for pt in proto_tools]
    return tuple(function_tools)


def _make_handler(fn):
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await fn(**args)
            text = json.dumps(result, default=str)
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:  # surface tool errors to the model rather than crashing the turn
            return {"content": [{"type": "text", "text": f"tool error: {type(e).__name__}: {e}"}],
                    "is_error": True}
    return handler


def build_sdk_server(server_name: str):
    """Create an in-process SDK MCP server config wrapping all of a FastMCP server's tools."""
    from claude_agent_sdk import create_sdk_mcp_server, tool

    sdk_tools = []
    for ft in _fastmcp_tools(server_name):
        schema = getattr(ft, "parameters", None) or {"type": "object", "properties": {}}
        handler = _make_handler(ft.fn)
        sdk_tools.append(tool(ft.name, ft.description or ft.name, schema)(handler))
    return create_sdk_mcp_server(name=server_name, tools=sdk_tools)


def tool_names_for(server_name: str) -> list[str]:
    """Fully-qualified `mcp__<server>__<tool>` names for allowed_tools."""
    return [f"mcp__{server_name}__{ft.name}" for ft in _fastmcp_tools(server_name)]


def build_servers(server_names) -> dict:
    """Map several FastMCP server names to SDK MCP server configs."""
    return {name: build_sdk_server(name) for name in server_names}
