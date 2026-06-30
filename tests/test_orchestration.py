"""Topology tests for the agent registry, prompts, and CSO dry-run flow (no API key needed)."""
import tempfile
from pathlib import Path

import pytest

from virtual_biotech.agents import registry
from virtual_biotech.agents.base import BaseAgent
from virtual_biotech.common.workspace import Session
from virtual_biotech.orchestration.cso import CSO
from virtual_biotech.prompts import available, load_prompt


def test_registry_has_eleven_agents():
    assert len(registry.REGISTRY) == 11
    assert len(registry.scientists()) == 8  # eight scientist agents


def test_every_agent_has_a_prompt():
    for spec in registry.REGISTRY.values():
        assert spec.prompt_name in available()
        assert len(load_prompt(spec.prompt_name)) > 100


def test_support_agents_use_haiku():
    for key in ("chief_of_staff", "scientific_reviewer"):
        assert "haiku" in registry.get(key).model


def test_permission_separation():
    # clinical trialist sees clinical tools, not single-cell servers
    ct = registry.get("clinical_trialist")
    assert "clinicaltrials" in ct.mcp_servers
    assert "cellxgene" not in ct.mcp_servers
    # CSO has no MCP servers (orchestrates only)
    assert registry.get("cso").mcp_servers == ()


def test_base_agent_build_options():
    opts = BaseAgent.from_key("statistical_genetics").build_options()
    assert "sonnet" in opts["model"]
    assert "open_targets" in opts["mcp_servers"]
    assert opts["system_prompt"].startswith("# System Prompt")


@pytest.mark.asyncio
async def test_cso_dry_run_produces_audit_trace():
    with tempfile.TemporaryDirectory() as tmp:
        sess = Session(root=Path(tmp))
        cso = CSO(session=sess, dry_run=True)
        report = await cso.handle("Assess OSMR genetic and clinical trial evidence in ulcerative colitis")
        assert "dry-run synthesis" in report
        events = [e["event"] for e in sess.read_trace()]
        # full Figure 1C flow recorded
        for step in ("brief.request", "decompose", "dispatch", "review.request", "synthesize", "report"):
            assert step in events
