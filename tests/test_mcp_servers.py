"""Shared harness: every implemented MCP server imports, registers tools, and is wired correctly.

These tests need FastMCP installed; they skip cleanly if it is absent so the pure-logic suite still
runs anywhere.
"""
import importlib

import pytest

pytest.importorskip("fastmcp")

# MCP servers that have a FastMCP `server.py` with registered tools.
IMPLEMENTED_SERVERS = ["clinicaltrials", "open_targets", "pubmed", "openfda", "cbioportal",
                       "dailymed", "gnomad",
                       "depmap", "tahoe", "tabula_sapiens", "cellxgene"]


async def _tool_names(server_module) -> set[str]:
    """Introspect registered tool names (FastMCP list_tools may be sync or async)."""
    tools = server_module.mcp.list_tools()
    if hasattr(tools, "__await__"):
        tools = await tools
    if isinstance(tools, dict):
        return set(tools.keys())
    return {t.name for t in tools}


@pytest.mark.parametrize("name", IMPLEMENTED_SERVERS)
def test_server_module_imports(name):
    mod = importlib.import_module(f"mcp_servers.{name}.server")
    assert mod.mcp.name == name


@pytest.mark.parametrize("name", IMPLEMENTED_SERVERS)
async def test_server_registers_tools(name):
    mod = importlib.import_module(f"mcp_servers.{name}.server")
    names = await _tool_names(mod)
    assert names, f"{name} registered no tools"


async def test_expected_tools_present():
    expected = {
        "clinicaltrials": {"get_clinical_trial_details", "search_clinical_trials",
                           "get_trial_adverse_events"},
        "open_targets": {"search_entities", "get_target_details", "get_target_genetic_evidence",
                         "get_target_known_drugs", "get_disease_details"},
        "pubmed": {"search_pubmed", "fetch_abstract", "verify_nct_in_article"},
        "openfda": {"get_top_adverse_reactions", "get_report_counts"},
        "cbioportal": {"find_cancer_studies", "get_study_details", "get_molecular_profiles"},
        "dailymed": {"get_boxed_warning", "get_label_safety_sections", "find_dailymed_spls"},
        "gnomad": {"get_gene_constraint"},
        "depmap": {"get_gene_essentiality"},
        "tahoe": {"list_hallmarks", "get_drug_hallmark_scores"},
        "tabula_sapiens": {"get_celltype_specificity", "get_expression_heterogeneity"},
        "cellxgene": {"get_celltype_expression"},
    }
    for name, want in expected.items():
        mod = importlib.import_module(f"mcp_servers.{name}.server")
        got = await _tool_names(mod)
        assert want <= got, f"{name} missing tools: {want - got}"


def test_every_referenced_server_has_a_package():
    """Each MCP server named in the agent registry must have a real package directory."""
    from pathlib import Path

    from virtual_biotech.agents import registry

    root = Path(__file__).resolve().parents[1] / "mcp_servers"
    referenced = {s for spec in registry.REGISTRY.values() for s in spec.mcp_servers}
    for name in referenced:
        assert (root / name).is_dir(), f"registry references missing server package: {name}"


def test_implemented_servers_are_a_subset_of_referenced():
    from virtual_biotech.agents import registry

    referenced = {s for spec in registry.REGISTRY.values() for s in spec.mcp_servers}
    assert set(IMPLEMENTED_SERVERS) <= referenced
