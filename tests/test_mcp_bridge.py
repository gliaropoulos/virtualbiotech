"""Tests for the FastMCP -> Agent SDK bridge and agent tool wiring (no Claude CLI needed)."""
import pytest

pytest.importorskip("claude_agent_sdk")

from virtual_biotech.agents import mcp_bridge
from virtual_biotech.agents.base import BaseAgent


def test_tool_names_are_namespaced():
    names = mcp_bridge.tool_names_for("open_targets")
    assert "mcp__open_targets__search_entities" in names
    assert all(n.startswith("mcp__open_targets__") for n in names)


def test_build_sdk_server_returns_config():
    cfg = mcp_bridge.build_sdk_server("gnomad")
    assert cfg is not None                       # McpSdkServerConfig (a dict-like config)


@pytest.mark.asyncio
async def test_bridged_handler_calls_real_tool():
    # depmap returns a graceful "not installed" payload -> proves the handler reaches the real fn.
    ft = mcp_bridge._fastmcp_tools("depmap")[0]
    handler = mcp_bridge._make_handler(ft.fn)
    result = await handler({"gene": "OSMR"})
    assert result["content"][0]["type"] == "text"
    assert "DepMap data not installed" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_bridged_handler_reports_errors_gracefully():
    async def boom(**kw):
        raise ValueError("nope")
    result = await mcp_bridge._make_handler(boom)({"x": 1})
    assert result.get("is_error") is True
    assert "ValueError" in result["content"][0]["text"]


def test_agent_allowed_tools_include_mcp_and_standard():
    agent = BaseAgent.from_key("statistical_genetics")
    allowed = agent.allowed_tool_names()
    assert "mcp__open_targets__get_target_genetic_evidence" in allowed
    assert "mcp__gnomad__get_gene_constraint" in allowed
    assert "WebSearch" in allowed and "WebFetch" in allowed


def test_build_servers_for_an_agent():
    servers = mcp_bridge.build_servers(BaseAgent.from_key("clinical_trialist").spec.mcp_servers)
    assert set(servers) == {"clinicaltrials", "pubmed", "cbioportal"}
